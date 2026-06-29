"""Unit tests for studio pure logic (storyboard, locked style, Ken-Burns filter, Gemini helpers)."""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from studio import DEMO_STORYBOARD, scene_filter
from studio.gemini import (
    DEFAULT_IMAGE_MODEL,
    GeminiError,
    build_request,
    endpoint,
    parse_image,
)
from studio.kenburns import MOTIONS, motion_for_index
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
