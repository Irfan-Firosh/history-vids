"""Unit tests for studio pure logic (storyboard, locked style, Ken-Burns filter, Gemini helpers)."""

from __future__ import annotations


import pytest

from studio import scene_filter
from studio.kenburns import MOTIONS, motion_for_index


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
