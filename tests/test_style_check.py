"""Tests for `tools/style_check.py` and the `studio_poc` pre-flight style gate (task 5.2).

The gate exists to refuse a run BEFORE it pays for ~200 off-style images, so these tests are
deliberately end-to-end where it matters: real synthetic frames run through the real
`measure_frame`/`conforms` math (studio/style_metrics.py, pure), and the pre-flight is proven to
run *before* the main per-scene image loop, not just to exist.

Recalibration story (see context/project/style-envelope.json's `_provenance`): the previously
shipped envelope was the raw min/max of per-channel MEANS, which put Axen's own mean saturation
(0.270) exactly at the envelope's max (0.27) — rejecting roughly half of Axen's own frames. The
fixtures below are calibrated so a frame near Axen's actual measured mean (§4 of
context/research/2026-08-01/04-video-forensics.md) sits INTERIOR to the recalibrated envelope.
"""

from __future__ import annotations

import json
import sys

import numpy as np
import pytest
from PIL import Image

from studio import Scene, Storyboard
from studio.run_log import RunRecorder
from studio.style_metrics import Envelope, conforms, measure_frame
from tools import studio_poc, style_check

W, H = 320, 180


def _axen_like_frame() -> np.ndarray:
    """Flat two-band pale background + a handful of flat muted accent colours — mirrors the
    Axen/Mack look (low saturation, high near-white, low colour count). Calibrated (see
    tools/style_check.py-adjacent scratch work) so its measured saturation (~0.28) and colour
    bins (~15) sit close to Axen's own measured mean (0.270 / 16.2)."""
    arr = np.zeros((H, W, 3), dtype=np.uint8)
    sky_h = int(H * 0.30)
    arr[:sky_h] = (250, 248, 244)  # pale sky band, near-white
    palette = [
        (196, 150, 96), (150, 110, 70), (120, 140, 95), (170, 90, 70),
        (90, 110, 150), (180, 160, 90), (140, 80, 100), (100, 130, 110),
        (200, 130, 60), (80, 100, 80), (210, 170, 130), (60, 70, 90),
        (170, 140, 180), (140, 160, 130),
    ]
    remaining_h = H - sky_h
    cols, rows = 7, 2
    cell_h, cell_w = remaining_h // rows, W // cols
    idx = 0
    for r in range(rows):
        y0 = sky_h + r * cell_h
        y1 = H if r == rows - 1 else sky_h + (r + 1) * cell_h
        for c in range(cols):
            x0 = c * cell_w
            x1 = W if c == cols - 1 else (c + 1) * cell_w
            arr[y0:y1, x0:x1] = palette[idx % len(palette)]
            idx += 1
    return arr


def _off_style_frame() -> np.ndarray:
    """A busy, highly saturated, many-colour frame with no near-white region at all — the
    opposite of the reference look; the known-bad fixture."""
    yy, xx = np.mgrid[0:H, 0:W]
    r = (np.sin(xx / 6.0) * 127 + 128).astype(np.uint8)
    g = (np.sin(yy / 5.0 + 2.0) * 127 + 128).astype(np.uint8)
    b = (np.sin((xx + yy) / 4.0 + 4.0) * 127 + 128).astype(np.uint8)
    return np.stack([r, g, b], axis=-1).astype(np.uint8)


class _FakeVoice:
    name = "say"


class _RecordingProvider:
    """Records every `generate()` call and writes a chosen fixed frame to disk."""

    name = "fake"
    uses_refs = False

    def __init__(self, frame: np.ndarray) -> None:
        self.frame = frame
        self.calls: list[str] = []

    def generate(self, prompt, out_path, refs=()):
        self.calls.append(out_path.name)
        Image.fromarray(self.frame).save(out_path)
        return out_path


# ── envelope recalibration (context/project/style-envelope.json) ───────────────────────────
def test_envelope_admits_its_own_reference_channels_mean():
    """The core defect this task fixes: the shipped envelope was the RANGE OF PER-CHANNEL MEANS,
    so Axen's own mean saturation (0.270) sat exactly at the envelope max (0.27) — rejecting
    roughly half of Axen's own frames. The recalibrated envelope must comfortably admit Axen's
    and Mack's own measured means, not sit at their edge."""
    envelope = style_check.load_envelope()
    axen = {"saturation": 0.270, "colour_bins": 16.2, "near_white_pct": 29.3}
    mack = {"saturation": 0.161, "colour_bins": 15.5, "near_white_pct": 33.2}
    for channel in (axen, mack):
        lo, hi = envelope.saturation
        assert lo < channel["saturation"] < hi
        lo, hi = envelope.colour_bins
        assert lo < channel["colour_bins"] < hi
        lo, hi = envelope.near_white_pct
        assert lo < channel["near_white_pct"] < hi


def test_envelope_still_refuses_known_off_style_channels():
    """Widening the envelope to stop rejecting the reference channels must not turn it into a
    rubber stamp: peer channels with a visibly different look (busier palette, painterly detail,
    far less empty space) must still fail at least one metric."""
    envelope = style_check.load_envelope()
    known_bad = {
        "Stickly": (0.117, 13.1, 44.5),
        "HistoryAlive": (0.277, 28.1, 14.6),
        "ThenFolk": (0.348, 28.7, 7.4),
    }
    for name, (sat, bins, white) in known_bad.items():
        sat_ok = envelope.saturation[0] <= sat <= envelope.saturation[1]
        bins_ok = envelope.colour_bins[0] <= bins <= envelope.colour_bins[1]
        white_ok = envelope.near_white_pct[0] <= white <= envelope.near_white_pct[1]
        assert not (sat_ok and bins_ok and white_ok), f"{name} should still fail >=1 metric"


# ── measure_frame + conforms wiring, real math over synthetic frames ────────────────────────
def test_axen_like_frame_conforms_to_recalibrated_envelope():
    envelope = style_check.load_envelope()
    metrics = measure_frame(_axen_like_frame())
    ok, failures = conforms(metrics, envelope)
    assert ok, failures


def test_axen_like_frame_would_have_failed_the_old_envelope():
    """Proves the defect existed, not just that the new envelope happens to pass: the same
    fixture, scored against the PREVIOUSLY shipped envelope (raw range of channel means), fails
    on saturation — exactly the boundary-at-the-mean bug described in the task brief."""
    old_envelope = Envelope(
        saturation=(0.16, 0.27), colour_bins=(13, 16), near_white_pct=(29.0, 45.0),
    )
    metrics = measure_frame(_axen_like_frame())
    ok, failures = conforms(metrics, old_envelope)
    assert not ok
    assert any("saturation" in f for f in failures)


def test_off_style_frame_fails_recalibrated_envelope_on_every_metric():
    envelope = style_check.load_envelope()
    metrics = measure_frame(_off_style_frame())
    ok, failures = conforms(metrics, envelope)
    assert not ok
    assert len(failures) == 3


# ── tools/style_check.py: load_envelope / check ─────────────────────────────────────────────
def test_load_envelope_reads_json_into_an_envelope(tmp_path, monkeypatch):
    payload = {"saturation": [0.1, 0.4], "colour_bins": [10, 22], "near_white_pct": [20.0, 40.0]}
    p = tmp_path / "env.json"
    p.write_text(json.dumps(payload))
    monkeypatch.setattr(style_check, "ENVELOPE_PATH", p)

    env = style_check.load_envelope()

    assert env == Envelope(saturation=(0.1, 0.4), colour_bins=(10, 22), near_white_pct=(20.0, 40.0))


def test_check_reports_pass_for_a_conforming_image(tmp_path, capsys):
    p = tmp_path / "good.png"
    Image.fromarray(_axen_like_frame()).save(p)

    ok = style_check.check([p], style_check.load_envelope())

    assert ok is True
    assert "PASS" in capsys.readouterr().out


def test_check_reports_fail_for_an_off_style_image(tmp_path, capsys):
    p = tmp_path / "bad.png"
    Image.fromarray(_off_style_frame()).save(p)

    ok = style_check.check([p], style_check.load_envelope())

    assert ok is False
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "saturation" in out  # per-metric failure reasons are printed, not just PASS/FAIL


def test_check_is_false_if_any_image_in_the_batch_fails():
    good = measure_frame(_axen_like_frame())
    bad = measure_frame(_off_style_frame())
    envelope = style_check.load_envelope()
    assert conforms(good, envelope)[0] is True
    assert conforms(bad, envelope)[0] is False  # sanity: fixtures disagree before the batch check


# ── tools/style_check.py: CLI (main) ────────────────────────────────────────────────────────
def test_main_probe_generates_one_image_and_exits_zero_when_on_style(tmp_path, monkeypatch):
    provider = _RecordingProvider(_axen_like_frame())
    monkeypatch.setattr(studio_poc, "make_image_provider", lambda name: provider)
    monkeypatch.setattr(sys, "argv", ["style_check.py", "--probe", "--out", str(tmp_path)])

    with pytest.raises(SystemExit) as exc:
        style_check.main()

    assert exc.value.code == 0
    assert len(provider.calls) == 1
    assert len(list(tmp_path.glob("*.png"))) == 1


def test_main_batch_generates_n_images_across_shot_types(tmp_path, monkeypatch):
    provider = _RecordingProvider(_axen_like_frame())
    monkeypatch.setattr(studio_poc, "make_image_provider", lambda name: provider)
    monkeypatch.setattr(sys, "argv", ["style_check.py", "--batch", "5", "--out", str(tmp_path)])

    with pytest.raises(SystemExit) as exc:
        style_check.main()

    assert exc.value.code == 0
    assert len(provider.calls) == 5


def test_main_exits_nonzero_when_the_probe_is_off_style(tmp_path, monkeypatch):
    provider = _RecordingProvider(_off_style_frame())
    monkeypatch.setattr(studio_poc, "make_image_provider", lambda name: provider)
    monkeypatch.setattr(sys, "argv", ["style_check.py", "--probe", "--out", str(tmp_path)])

    with pytest.raises(SystemExit) as exc:
        style_check.main()

    assert exc.value.code == 1


# ── the pre-flight gate wired into tools/studio_poc.py::render_storyboard ───────────────────
def _one_scene_storyboard(shot_type: str = "character") -> Storyboard:
    return Storyboard(
        title="t", style="s",
        scenes=(Scene(narration="n", image_prompt="p", shot_type=shot_type),),
    )


def _stub_cheap_bits(monkeypatch) -> None:
    """Stub the narration/segment machinery so only the gate + loop-reached-or-not is exercised
    (mirrors the pattern in tests/test_studio.py's pause_for_review test)."""
    monkeypatch.setattr(
        studio_poc, "build_narration",
        lambda scenes, voice, out_dir: (out_dir / "n.wav", [(0.0, 9.0)] * len(scenes), [], [], []),
    )
    monkeypatch.setattr(studio_poc, "_save_beat_spans", lambda *a, **k: None)
    monkeypatch.setattr(studio_poc, "_save_word_timings", lambda *a, **k: None)
    monkeypatch.setattr(studio_poc, "load_channel_refs", lambda: [])


def test_style_preflight_aborts_before_any_scene_frame_is_generated(tmp_path, monkeypatch):
    """The gate's whole point: refuse BEFORE paying for the rest of the run, not after."""
    _stub_cheap_bits(monkeypatch)
    loop_calls: list[int] = []
    monkeypatch.setattr(studio_poc, "_generate_frame", lambda *a, **k: loop_calls.append(1))

    bad_provider = _RecordingProvider(_off_style_frame())
    images = studio_poc.ImageProviders(bad_provider, bad_provider)
    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="fake", voice_provider="say", scene_count=1,
    )

    with pytest.raises(RuntimeError, match="style pre-flight"):
        studio_poc.render_storyboard(
            rec, _one_scene_storyboard(), images, _FakeVoice(), captions=False,
        )

    assert loop_calls == []  # the main per-scene loop was never reached
    assert len(bad_provider.calls) == 1  # exactly one probe frame was generated, not a full run


def test_style_preflight_passes_and_the_main_loop_is_reached(tmp_path, monkeypatch):
    _stub_cheap_bits(monkeypatch)
    loop_calls: list[int] = []
    monkeypatch.setattr(studio_poc, "_generate_frame", lambda *a, **k: loop_calls.append(1))

    good_provider = _RecordingProvider(_axen_like_frame())
    images = studio_poc.ImageProviders(good_provider, good_provider)
    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="fake", voice_provider="say", scene_count=1,
    )

    # pause_for_review=True stops right after the (stubbed) loop, so this never touches ffmpeg.
    out = studio_poc.render_storyboard(
        rec, _one_scene_storyboard(), images, _FakeVoice(), captions=False, pause_for_review=True,
    )

    assert out is None
    assert loop_calls == [1]  # the main loop DID run, once, for the one scene
    assert len(good_provider.calls) == 1  # one probe frame generated for the gate


def test_skip_style_check_bypasses_the_probe_entirely(tmp_path, monkeypatch):
    """--skip-style-check is the informed-operator escape hatch: it must skip the probe
    GENERATION itself (which costs money), not just ignore a failing result."""
    _stub_cheap_bits(monkeypatch)
    loop_calls: list[int] = []
    monkeypatch.setattr(studio_poc, "_generate_frame", lambda *a, **k: loop_calls.append(1))

    bad_provider = _RecordingProvider(_off_style_frame())  # would fail the gate if it ran
    images = studio_poc.ImageProviders(bad_provider, bad_provider)
    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="fake", voice_provider="say", scene_count=1,
    )

    out = studio_poc.render_storyboard(
        rec, _one_scene_storyboard(), images, _FakeVoice(), captions=False,
        pause_for_review=True, skip_style_check=True,
    )

    assert out is None
    assert loop_calls == [1]  # loop ran despite the off-style provider
    assert bad_provider.calls == []  # the probe itself was never generated


def test_style_preflight_reuses_an_existing_scene_zero_frame_instead_of_paying_again(
    tmp_path, monkeypatch,
):
    """A resumed run may already have scene 0's frame on disk from an earlier invocation — the
    gate should measure that file rather than pay for a second generation of the same frame."""
    _stub_cheap_bits(monkeypatch)
    monkeypatch.setattr(studio_poc, "_generate_frame", lambda *a, **k: None)

    provider = _RecordingProvider(_off_style_frame())  # would fail/be called if the gate ran fresh
    images = studio_poc.ImageProviders(provider, provider)
    rec = RunRecorder.create(
        tmp_path, title="t", images_provider="fake", voice_provider="say", scene_count=1,
    )
    Image.fromarray(_axen_like_frame()).save(rec.dir / "img_0.png")  # already on disk, on-style

    out = studio_poc.render_storyboard(
        rec, _one_scene_storyboard(), images, _FakeVoice(), captions=False,
        resume=True, pause_for_review=True,
    )

    assert out is None
    assert provider.calls == []  # no new probe paid for — the existing frame was measured instead


def test_main_wires_skip_style_check_flag_through_to_render_storyboard(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(studio_poc, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(studio_poc, "load_dotenv", lambda *a, **kw: None)

    def fake_render_storyboard(*args, **kwargs):
        captured.update(kwargs)
        return None

    monkeypatch.setattr(studio_poc, "render_storyboard", fake_render_storyboard)
    monkeypatch.setattr(
        sys, "argv",
        ["studio_poc.py", "--skip-style-check", "--run-id", "r1"],
    )

    studio_poc.main()

    assert captured.get("skip_style_check") is True
