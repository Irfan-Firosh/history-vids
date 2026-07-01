"""Unit tests for studio pure logic (storyboard, locked style, Ken-Burns filter, Gemini helpers)."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from studio import DEMO_STORYBOARD, huggingface, scene_filter
from studio.gemini import (
    DEFAULT_IMAGE_MODEL,
    GeminiError,
    build_request,
    endpoint,
    parse_image,
)
from studio.kenburns import MOTIONS, motion_for_index
from studio.llm import (
    LLMError,
    build_chat_request,
    chat_endpoint,
    extract_message,
    parse_json_block,
)
from studio.research import ResearchSource, format_research_brief
from studio.script_prompt import (
    QUERY_SYSTEM_PROMPT,
    SCRIPT_SYSTEM_PROMPT,
    build_query_user_prompt,
)
from studio.storyboard import storyboard_from_dict
from studio.style import LOCKED_STYLE, styled_prompt
from studio.types import Scene, Storyboard, shot_uses_character


# ── style ─────────────────────────────────────────────────────────────────────
def test_styled_prompt_appends_locked_style():
    out = styled_prompt("a cave at dawn")
    assert out.startswith("a cave at dawn")
    assert LOCKED_STYLE in out  # every image shares one style → consistency


def test_styled_prompt_is_stable_across_scenes():
    a = styled_prompt("scene one")
    b = styled_prompt("scene two")
    assert a.removeprefix("scene one") == b.removeprefix("scene two")  # identical style tail


def test_styled_prompt_character_ref_locks_to_one_reference_figure():
    out = styled_prompt("a lone figure with a torch", use_character_ref=True)
    assert "reference image" in out and "Exactly one white-headed stick person" in out
    wide = styled_prompt("three people walking in snow", use_character_ref=True, shot_type="wide")
    assert "small simple group of white-headed stick people" in wide


# ── scene filter (static hard-cut default; optional Ken-Burns) ─────────────────
def test_static_is_the_default_and_has_no_motion():
    vf = scene_filter()  # default
    assert "zoompan" not in vf  # static = no motion
    assert "scale=1920:1080" in vf and "crop=1920:1080" in vf
    assert vf.endswith("format=yuv420p")


def test_unknown_motion_falls_back_to_static():
    assert "zoompan" not in scene_filter("nonsense")  # not a real motion → static


def test_optional_kenburns_has_output_size_and_frames():
    vf = scene_filter("zoom_in", 1920, 1080, duration_sec=4.0, fps=30)
    assert "zoompan=" in vf and "s=1920x1080" in vf and "d=120" in vf  # 4s*30
    assert vf.endswith("format=yuv420p")


@pytest.mark.parametrize("motion", MOTIONS)
def test_every_optional_motion_builds_valid_filter(motion):
    vf = scene_filter(motion, duration_sec=3.0, fps=30)
    assert "zoompan=" in vf and "d=90" in vf
    if motion.startswith("pan"):
        assert "on/90" in vf  # pans are driven by the output frame index


def test_motion_rotation_cycles():
    assert [motion_for_index(i) for i in range(len(MOTIONS) + 1)][-1] == MOTIONS[0]


def test_frames_never_zero():
    assert "d=1" in scene_filter("zoom_in", duration_sec=0.0, fps=30)


# ── storyboard ────────────────────────────────────────────────────────────────
def test_demo_storyboard_is_well_formed():
    sb = DEMO_STORYBOARD
    assert isinstance(sb, Storyboard) and len(sb.scenes) >= 4
    assert all(isinstance(s, Scene) and s.narration and s.image_prompt for s in sb.scenes)
    assert all(s.motion == "static" or s.motion in MOTIONS for s in sb.scenes)
    assert sb.style == LOCKED_STYLE


def test_scene_is_frozen():
    s = DEMO_STORYBOARD.scenes[0]
    with pytest.raises(ValidationError):
        s.narration = "mutated"  # type: ignore[misc]


# ── shot types (drive reference conditioning) ──────────────────────────────────
def test_scene_defaults_to_character_shot():
    assert Scene(narration="a", image_prompt="b").shot_type == "character"


def test_shot_uses_character_only_for_character_and_wide():
    assert shot_uses_character("character") and shot_uses_character("wide")
    assert not shot_uses_character("concept") and not shot_uses_character("map")


def test_invalid_shot_type_is_rejected():
    with pytest.raises(ValidationError):
        Scene(narration="a", image_prompt="b", shot_type="banana")  # type: ignore[arg-type]


def test_demo_storyboard_tags_every_scene_with_a_valid_shot():
    valid = ("character", "wide", "concept", "map")
    assert all(s.shot_type in valid for s in DEMO_STORYBOARD.scenes)


# ── Gemini request/response helpers (pure, offline — no quota spend) ────────────
def test_build_request_text_only_has_16x9_and_image_modality():
    body = build_request("hello")
    assert body["contents"][0]["parts"] == [{"text": "hello"}]
    assert body["generationConfig"]["responseModalities"] == ["IMAGE"]
    assert body["generationConfig"]["imageConfig"]["aspectRatio"] == "16:9"


def test_build_request_appends_reference_images_as_inline_png():
    body = build_request("hi", ["QUJD", "REVG"])
    parts = body["contents"][0]["parts"]
    assert parts[0] == {"text": "hi"}
    assert [p["inlineData"]["data"] for p in parts[1:]] == ["QUJD", "REVG"]
    assert all(p["inlineData"]["mimeType"] == "image/png" for p in parts[1:])


def test_build_request_can_omit_aspect_ratio_for_reference_sheets():
    assert "imageConfig" not in build_request("x", aspect_ratio=None)["generationConfig"]


def test_parse_image_decodes_inline_png():
    raw = b"\x89PNG\r\n fake-bytes"
    resp = {"candidates": [{"content": {"parts": [
        {"inlineData": {"mimeType": "image/png", "data": base64.b64encode(raw).decode()}}
    ]}}]}
    assert parse_image(resp) == raw


def test_parse_image_billing_error_is_not_retryable():
    resp = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED",
                      "message": "Your prepayment credits are depleted."}}
    with pytest.raises(GeminiError) as ei:
        parse_image(resp)
    assert ei.value.is_billing and not ei.value.is_retryable


def test_parse_image_transient_429_is_retryable():
    resp = {"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "rate limit hit"}}
    with pytest.raises(GeminiError) as ei:
        parse_image(resp)
    assert ei.value.is_retryable and not ei.value.is_billing


def test_parse_image_raises_when_no_image_returned():
    resp = {"candidates": [{"content": {"parts": [{"text": "I can't draw that"}]}}]}
    with pytest.raises(GeminiError) as ei:
        parse_image(resp)
    assert ei.value.status == "NO_IMAGE"


def test_endpoint_targets_generate_content():
    assert endpoint(DEFAULT_IMAGE_MODEL, "KEY").endswith(
        "gemini-2.5-flash-image:generateContent?key=KEY"
    )


# ── LLM script helpers (pure, offline) ─────────────────────────────────────────
def test_chat_endpoint_appends_path_without_double_slash():
    assert chat_endpoint("https://x.test/api/") == "https://x.test/api/chat/completions"
    assert chat_endpoint("https://x.test/api") == "https://x.test/api/chat/completions"


def test_build_chat_request_has_system_and_user_messages():
    body = build_chat_request("gpt-oss:120b", "be brief", "hello", temperature=0.3, max_tokens=100)
    assert body["model"] == "gpt-oss:120b" and body["stream"] is False
    assert body["temperature"] == 0.3 and body["max_tokens"] == 100
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]


def test_extract_message_returns_content():
    resp = {"choices": [{"message": {"role": "assistant", "content": "hi there"}}]}
    assert extract_message(resp) == "hi there"


def test_extract_message_raises_on_api_error():
    with pytest.raises(LLMError):
        extract_message({"error": {"message": "model not found"}})


def test_extract_message_raises_on_malformed():
    with pytest.raises(LLMError):
        extract_message({"weird": True})


def test_parse_json_block_handles_fenced_and_prose():
    text = 'Sure! Here it is:\n```json\n{"title": "T", "scenes": []}\n```\nHope that helps.'
    assert parse_json_block(text) == {"title": "T", "scenes": []}


def test_parse_json_block_handles_bare_object_with_prose():
    assert parse_json_block('blah {"a": 1} trailing')["a"] == 1


def test_parse_json_block_raises_when_no_json():
    with pytest.raises(LLMError):
        parse_json_block("no object here")


# ── research brief (pure) ──────────────────────────────────────────────────────
def test_format_research_brief_numbers_and_cites_sources():
    srcs = [
        ResearchSource(title="Sleep study", url="http://a", snippet="5.7-7 hrs", published="2015"),
        ResearchSource(title="Leisure study", url="http://b", snippet="foragers 20 hrs"),
    ]
    brief = format_research_brief(srcs)
    assert "[1] Sleep study (2015)" in brief and "http://a" in brief
    assert "[2] Leisure study" in brief and "http://b" in brief


def test_format_research_brief_truncates_long_snippets():
    brief = format_research_brief([ResearchSource(title="T", url="u", snippet="x" * 900)])
    assert "…" in brief and len(brief) < 900


def test_format_research_brief_handles_empty():
    assert format_research_brief([]) == "(no sources retrieved)"


# ── storyboard from LLM JSON ───────────────────────────────────────────────────
def test_storyboard_from_dict_builds_validated_storyboard():
    scenes = [
        {"narration": "You wake up.", "image_prompt": "a stick figure", "shot_type": "character"},
        {"narration": "A simple map.", "image_prompt": "a flat world map", "shot_type": "map"},
    ]
    sb = storyboard_from_dict({"title": "Why You Feel Behind", "scenes": scenes})
    assert sb.title == "Why You Feel Behind" and len(sb.scenes) == 2
    assert sb.scenes[1].shot_type == "map" and sb.scenes[0].motion == "static"
    assert sb.style == LOCKED_STYLE  # default style applied


def test_storyboard_from_dict_defaults_shot_type_to_character():
    data = {"title": "T", "scenes": [{"narration": "n", "image_prompt": "p"}]}
    assert storyboard_from_dict(data).scenes[0].shot_type == "character"


def test_storyboard_from_dict_rejects_invalid_shot_type():
    bad = {"narration": "n", "image_prompt": "p", "shot_type": "banana"}
    with pytest.raises(ValidationError):
        storyboard_from_dict({"title": "T", "scenes": [bad]})


def test_storyboard_from_dict_requires_scenes():
    with pytest.raises(ValueError):
        storyboard_from_dict({"title": "T", "scenes": []})


# ── script prompts (the moat — encode tone + factual constraints) ──────────────
def test_script_system_prompt_encodes_tone_and_constraints():
    p = SCRIPT_SYSTEM_PROMPT.lower()
    assert "calm" in p and "philosophical" in p  # narration tone
    assert "curiosity" in p and "title" in p  # engaging title
    assert "only facts" in p and "never invent" in p  # no hallucinated citations
    assert "shot_type" in p and "json" in p  # structured output
    assert "text-free" in p  # images never carry drawn text (diffusion garbles it)
    # brainrot-tuned credibility must NOT tip into a lecture — hard anti-academic guardrail
    assert "historiography" in p and "professor" in p  # banned register + "not a professor" rail
    assert "nobody actually agrees" in p  # mystery/debate used as a hook, capped
    assert "at most once or twice" in p  # the cap that keeps debate framing rare
    # characters must look true to their culture/era, but only via simple crude markers
    assert "true to their" in p and "shaggy hair" in p and "fur wrap" in p
    assert "only humans are stick figures" in p


def test_query_system_prompt_seeks_evidence_and_disagreement():
    q = QUERY_SYSTEM_PROMPT.lower()
    assert "concrete evidence" in q  # the physical thing, not the method name
    assert "contested" in q or "argue" in q  # surface genuine disagreements
    assert "looked" in q and "hairstyle" in q  # also research how the people actually looked
    user = build_query_user_prompt("Battle of Tsushima", 6)
    assert "disagree" in user.lower() and "6" in user
    assert "looked like" in user.lower()  # at least one appearance query


def test_build_query_user_prompt_includes_topic_and_count():
    out = build_query_user_prompt("ancient sleep", 5)
    assert "ancient sleep" in out and "5" in out


# ── HuggingFace helpers (pure) ─────────────────────────────────────────────────
def test_hf_endpoints_try_router_then_classic():
    router, classic = huggingface.endpoints("org/model")
    assert router.startswith("https://router.huggingface.co") and router.endswith("org/model")
    assert "api-inference.huggingface.co" in classic and classic.endswith("org/model")


def test_hf_request_body_is_text_to_image():
    assert huggingface.request_body("hi") == {"inputs": "hi"}
