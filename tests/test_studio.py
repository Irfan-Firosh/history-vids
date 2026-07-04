"""Unit tests for studio pure logic (storyboard, locked style, Ken-Burns filter, Gemini helpers)."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from studio import DEMO_STORYBOARD, huggingface, scene_filter
from studio.captions import cue_timings, split_caption_cues
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
    CALLOUT_ANALYSIS_SYSTEM_PROMPT,
    QUERY_SYSTEM_PROMPT,
    SCRIPT_SYSTEM_PROMPT,
    build_callout_analysis_user_prompt,
    build_query_user_prompt,
    build_script_user_prompt,
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


# ── key-fact callout renderer (whitespace placement, no black box) ─────────────
def test_pick_callout_zone_finds_whitespace_and_flags_busy(tmp_path):
    from PIL import Image

    from tools import studio_poc

    white = tmp_path / "white.png"
    Image.new("RGB", (1024, 576), (245, 242, 235)).save(white)
    res_white = studio_poc._pick_callout_zone(white)
    assert res_white is not None  # clean near-white frame → a zone
    assert res_white[4] is False  # is_busy should be False

    busy = tmp_path / "busy.png"
    Image.effect_noise((1024, 576), 128).convert("RGB").save(busy)
    res_busy = studio_poc._pick_callout_zone(busy)
    assert res_busy is not None  # we still return a zone
    assert res_busy[4] is True  # is_busy should be True


def test_make_emphasis_png_is_transparent_and_boxless(tmp_path):
    from PIL import Image

    from tools import studio_poc

    base = tmp_path / "base.png"
    Image.new("RGB", (1024, 576), (245, 242, 235)).save(base)
    out = tmp_path / "emph.png"
    studio_poc.make_emphasis_png("18,000 miles", out, base)
    im = Image.open(out).convert("RGBA")
    assert out.stat().st_size > 0 and im.size == (studio_poc.W, studio_poc.H)
    assert im.getpixel((5, 5))[3] == 0  # corner fully transparent → no black box slapped over image


def test_make_emphasis_png_renders_wobbly_card_when_whitespace_is_busy(tmp_path):
    # A busy frame has no clean zone → render a wobbly paper card behind the text for readability.
    from PIL import Image

    from tools import studio_poc

    busy = tmp_path / "busy.png"
    Image.effect_noise((1024, 576), 128).convert("RGB").save(busy)
    out = tmp_path / "emph.png"
    studio_poc.make_emphasis_png("May 27", out, busy)
    im = Image.open(out).convert("RGBA")
    opaque = sum(im.getchannel("A").histogram()[201:])  # alpha > 200 pixel count
    # the filled wobbly card is translucent/opaque, so the count is higher than text-only strokes.
    assert opaque > 60000


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


def test_parse_json_block_ignores_trailing_extra_data():
    # Local models sometimes append a second object / commentary after the storyboard.
    text = '{"title": "T", "scenes": [1, 2]}\n{"stray": true}\nextra prose'
    assert parse_json_block(text) == {"title": "T", "scenes": [1, 2]}


def test_parse_json_block_repairs_malformed_local_model_json():
    # Local models emit slightly-broken JSON: a missing comma between fields, and an unescaped inner
    # quote inside a string (the exact "Expecting ',' delimiter" failure). Both must be salvaged.
    assert parse_json_block('{"title": "T" "scenes": []}') == {"title": "T", "scenes": []}
    assert parse_json_block('{"queries": ["the "lost" fleet", "tsushima"]}')["queries"][1] == (
        "tsushima"
    )


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


def test_scene_started_records_callout_and_intense(tmp_path):
    # The manifest labels "callout frames" — emphasis + intense land in run.json for the dashboard.
    import json

    from studio.run_log import RunRecorder

    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="agnes", voice_provider="cartesia", scene_count=1,
    )
    rec.scene_started(
        0, "concept", "a route map", emphasis="18,000 miles", intense=True, frame_count=2
    )
    s0 = json.loads((rec.dir / "run.json").read_text())["scenes"][0]
    assert s0["emphasis"] == "18,000 miles" and s0["intense"] is True
    assert s0["frame_count"] == 2  # fire spot → dashboard shows both frames


def test_boost_intense_beats_adds_roughly_1_5x_more_fire_spots():
    from tools.make_script import _boost_intense_beats

    # 20 beats, 4 flagged by the analysis pass → target round(4 * 1.5) = 6 fire spots.
    scenes = [{"narration": "x" * (i + 1), "intense": i in (0, 1, 2, 3)} for i in range(20)]
    _boost_intense_beats(scenes)
    intense = [i for i, s in enumerate(scenes) if s["intense"]]
    assert len(intense) == 6  # 1.5x the original 4
    assert {0, 1, 2, 3} <= set(intense)  # never un-flags the LLM's picks
    # the two promoted beats are the longest-narration not-yet-flagged ones (19 and 18).
    assert {18, 19} <= set(intense)


def test_boost_intense_beats_is_capped_and_noop_when_none_flagged():
    from tools.make_script import _boost_intense_beats

    none = [{"narration": "abc", "intense": False} for _ in range(10)]
    _boost_intense_beats(none)
    assert not any(s["intense"] for s in none)  # 0 * 1.5 = 0 → stays empty

    many = [{"narration": "abc", "intense": i < 8} for i in range(10)]
    _boost_intense_beats(many)  # round(8*1.5)=12 capped at 50% of 10 = 5 → already 8, so no change
    assert sum(s["intense"] for s in many) == 8


def test_frame_prompt_makes_extra_frames_clearly_distinct():
    from tools.studio_poc import _frame_prompt

    base = "a caveman by a fire. flat cartoon style."
    assert _frame_prompt(base, 0) == base  # frame 0 is the untouched base image
    v1 = _frame_prompt(base, 1)
    assert base in v1 and "variation 1" in v1
    assert "DIFFERENT" in v1 and "near-duplicate" in v1  # forces a real cut, not a copy


def test_set_callouts_records_the_flashed_plan(tmp_path):
    # The dashboard shows WHICH callouts render, on which scene's frame, and when.
    import json

    from studio.run_log import RunRecorder

    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="agnes", voice_provider="cartesia", scene_count=3,
    )
    rec.set_callouts([("Tsushima", 1, 12.3456), ("1905", 5, 62.0)])
    callouts = json.loads((rec.dir / "run.json").read_text())["callouts"]
    assert callouts == [
        {"text": "Tsushima", "scene_index": 1, "start_sec": 12.346},
        {"text": "1905", "scene_index": 5, "start_sec": 62.0},
    ]


def test_run_recorder_load_preserves_existing_manifest(tmp_path):
    # approve/regenerate run as separate processes → they must re-open, not reset, the manifest.
    from studio.run_log import RunRecorder

    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="agnes", voice_provider="say", scene_count=2,
    )
    rec.scene_started(0, "character", "a lone figure")
    rec.pending_approval()
    reloaded = RunRecorder.load(tmp_path, rec.run_id)
    assert reloaded.manifest.status == "pending_approval"
    assert [s.image_prompt for s in reloaded.manifest.scenes] == ["a lone figure"]


def test_storyboard_from_dict_reads_emphasis_and_intense_with_defaults():
    scenes = [
        {"narration": "n", "image_prompt": "p", "emphasis": " 1905 ", "intense": True},
        {"narration": "n2", "image_prompt": "p2"},  # both absent → "" / False
    ]
    sb = storyboard_from_dict({"title": "T", "scenes": scenes})
    assert sb.scenes[0].emphasis == "1905" and sb.scenes[0].intense is True
    assert sb.scenes[1].emphasis == "" and sb.scenes[1].intense is False


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


def test_callout_analysis_prompt_encodes_selection_criteria():
    p = CALLOUT_ANALYSIS_SYSTEM_PROMPT.lower()
    assert "proper names" in p and "numbers" in p  # prefer names + hard numbers
    assert "reject" in p  # reject vague/common words
    assert "appear in that beat's narration" in p and "never invent" in p  # grounded, no invention
    assert "intense" in p  # also flags dramatic beats
    schema = CALLOUT_ANALYSIS_SYSTEM_PROMPT
    assert '"callouts"' in schema and '"intense"' in schema  # returns both lists


def test_build_callout_analysis_user_prompt_lists_indexed_beats():
    out = build_callout_analysis_user_prompt(
        [{"beat": 0, "narration": "The admiral Hugh Ogden gave the order."},
         {"beat": 1, "narration": "Nothing much happened."}]
    )
    assert "[0] The admiral Hugh Ogden" in out and "[1] Nothing much" in out


def test_apply_callout_analysis_maps_callouts_and_intense(monkeypatch):
    from tools.make_script import LLMScriptProvider

    prov = LLMScriptProvider(research=None)
    monkeypatch.setattr(
        prov, "_chat",
        lambda system, user, temp=None:
        '{"callouts": [{"beat": 1, "text": " Hugh Ogden "}, {"beat": 9, "text": "x"}], '
        '"intense": [0, 2]}',
    )
    data = {"scenes": [{"narration": "a"}, {"narration": "b"}, {"narration": "c"}]}
    prov._apply_callout_analysis(data)
    scenes = data["scenes"]
    assert scenes[1]["emphasis"] == "Hugh Ogden"  # mapped + trimmed
    assert scenes[0]["emphasis"] == "" and scenes[2]["emphasis"] == ""  # other beats stay clear
    assert scenes[0]["intense"] is True and scenes[2]["intense"] is True
    assert data["scenes"][1]["intense"] is False  # out-of-range beat 9 ignored, no crash


def test_apply_callout_analysis_degrades_gracefully_on_llm_failure(monkeypatch):
    from studio.llm import LLMError
    from tools.make_script import LLMScriptProvider

    prov = LLMScriptProvider(research=None)

    def boom(system, user, temp=None):
        raise LLMError("endpoint down")

    monkeypatch.setattr(prov, "_chat", boom)
    data = {"scenes": [{"narration": "a"}, {"narration": "b"}]}
    prov._apply_callout_analysis(data)  # must not raise
    assert all(s["emphasis"] == "" and s["intense"] is False for s in data["scenes"])


def test_build_script_user_prompt_includes_topic_brief_and_target_band():
    out = build_script_user_prompt(
        "ancient sleep", "[1] a real study", 8, min_minutes=6, max_minutes=9
    )
    assert "ancient sleep" in out and "[1] a real study" in out
    assert "8 beats" in out and "6-9 minute" in out  # beat count + target duration band


# ── caption cues (short timed subtitles) ───────────────────────────────────────
def test_split_caption_cues_keeps_chunks_short():
    text = "You stir before dawn, the cold air biting as the fire crackles for the first time."
    cues = split_caption_cues(text, max_words=7, max_chars=42)
    assert len(cues) >= 2  # long sentence → multiple cues, not one wall of text
    assert all(len(c) <= 42 and len(c.split()) <= 7 for c in cues)
    assert " ".join(cues).split() == text.split()  # no words lost


def test_split_caption_cues_empty():
    assert split_caption_cues("") == []


def test_cue_timings_cover_full_duration_in_order():
    cues = ["one two", "three four five", "six"]
    spans = cue_timings(cues, 9.0)
    assert len(spans) == 3
    assert spans[0][0] == 0.0 and spans[-1][1] == 9.0  # covers [0, dur]
    assert all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))  # contiguous
    assert all(s < e for s, e in spans)  # forward


def test_cue_timings_weights_longer_cues_with_more_time():
    short, long = cue_timings(["hi", "a much longer caption here"], 10.0)
    assert (long[1] - long[0]) > (short[1] - short[0])  # longer text → more screen time


def test_cue_timings_empty_or_zero():
    assert cue_timings([], 5.0) == []
    assert cue_timings(["x"], 0.0) == []


# ── storyboard parsing ─────────────────────────────────────────────────────────
def test_storyboard_from_dict_ignores_legacy_cutaways_key():
    # Old saved scripts may still carry a "cutaways" key — it's simply ignored (back-compatible).
    scene = {"narration": "n", "image_prompt": "p", "cutaways": ["a question mark"]}
    sb = storyboard_from_dict({"title": "T", "scenes": [scene]})
    assert sb.scenes[0].narration == "n" and not hasattr(sb.scenes[0], "cutaways")


# ── HuggingFace helpers (pure) ─────────────────────────────────────────────────
def test_hf_endpoints_try_router_then_classic():
    router, classic = huggingface.endpoints("org/model")
    assert router.startswith("https://router.huggingface.co") and router.endswith("org/model")
    assert "api-inference.huggingface.co" in classic and classic.endswith("org/model")


def test_hf_request_body_is_text_to_image():
    assert huggingface.request_body("hi") == {"inputs": "hi"}
