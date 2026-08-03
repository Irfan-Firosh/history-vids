"""`tools/reassemble.py` must render through the render_shots/assemble path (per-shot cached
segments + a single libass burn) — never through `tools.studio_poc.render_video`, the retired
single-filtergraph renderer this whole rebuild replaces (measured ~12.8h for an 8-minute video,
see tools/render/assemble.py's module docstring). Reassemble reuses images already on disk (it
never generates new ones), so its Shot schedule is driven by how many frames actually exist per
beat (`count_frames`), not by a fresh render count.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from tools import reassemble as ra

_FFMPEG_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")


def _fake_voice_factory(duration: float):
    """A deterministic stand-in for `tools.studio_poc.CartesiaTimestampVoice` — writes a real
    silent wav via ffmpeg lavfi (no network, no real TTS call) and returns word timings spread
    evenly across it, so downstream beat-alignment/caption code has real numbers to chew on."""

    class _FakeVoice:
        name = "cartesia-sse"

        def synthesize(self, text: str, out_path: Path):
            words = text.split()
            subprocess.run(
                ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
                 "-i", "anullsrc=r=44100:cl=mono", "-t", f"{duration}", str(out_path)],
                check=True, capture_output=True,
            )
            n = len(words)
            step = duration / n
            starts = [round(i * step, 3) for i in range(n)]
            ends = [round((i + 1) * step, 3) for i in range(n)]
            return words, starts, ends

    return _FakeVoice


def _write_storyboard(path: Path) -> None:
    path.write_text(json.dumps({
        "title": "t",
        "style": "s",
        "scenes": [
            {"narration": "One two three four.", "image_prompt": "p", "shot_type": "character"},
            {"narration": "Five six seven eight nine ten.", "image_prompt": "q",
             "shot_type": "wide"},
        ],
    }))


def test_reassemble_builds_shots_from_frames_on_disk_and_renders_via_render_shots_and_assemble(
    tmp_path, monkeypatch
):
    """The Shot schedule must come from what's ACTUALLY on disk (beat 0 has 1 frame, beat 1 has 2 —
    count_frames), contiguous and monotonic across the whole clip, and the video must be produced
    by calling `render_shots` + `assemble` — never the retired `render_video`."""
    images_dir = tmp_path / "images"
    images_dir.mkdir()
    Image.new("RGB", (64, 36), (200, 30, 30)).save(images_dir / "img_0.png")
    Image.new("RGB", (64, 36), (30, 200, 30)).save(images_dir / "img_1.png")
    Image.new("RGB", (64, 36), (30, 30, 200)).save(images_dir / "img_1_1.png")

    sb_path = tmp_path / "storyboard.json"
    _write_storyboard(sb_path)

    monkeypatch.setattr(ra, "CartesiaTimestampVoice", _fake_voice_factory(6.0))

    captured: dict = {}

    def fake_render_shots(shots, image_dir, out_dir, *, width, height, fps):
        captured["shots"] = shots
        captured["image_dir"] = image_dir
        return [out_dir / f"seg_{i}.mp4" for i in range(len(shots))]

    def fake_assemble(segments, wav, cues, out, *, work_dir, width, height, fps):
        captured["segments"] = segments
        captured["cues"] = cues
        out.write_bytes(b"fake-video")
        return out

    monkeypatch.setattr(ra, "render_shots", fake_render_shots)
    monkeypatch.setattr(ra, "assemble", fake_assemble)

    out_path = tmp_path / "video_v2.mp4"
    result = ra.reassemble(sb_path, images_dir, out_path)

    assert result == out_path
    assert out_path.is_file()

    shots = captured["shots"]
    assert [(s.beat_index, s.sub_index, s.image_key) for s in shots] == [
        (0, 0, "img_0.png"),
        (1, 0, "img_1.png"),
        (1, 1, "img_1_1.png"),
    ]
    # Contiguous, monotonic spans covering the whole 6s clip — no gaps, no overlaps.
    assert shots[0].start == 0.0
    for a, b in zip(shots, shots[1:], strict=False):
        assert b.start == a.end
    assert shots[-1].end == pytest.approx(6.0, abs=1e-6)

    assert captured["image_dir"] == images_dir
    assert captured["cues"]  # real word timings produced non-empty caption cues


def test_reassemble_never_calls_the_retired_render_video(tmp_path, monkeypatch):
    """Belt-and-suspenders: even if `render_shots`/`assemble` were left un-mocked, the module must
    not hold a reference to `render_video` at all anymore."""
    assert not hasattr(ra, "render_video")


@pytest.mark.integration
def test_reassemble_end_to_end_with_real_ffmpeg(tmp_path, monkeypatch):
    """No mocks on the render path: real render_shots -> real render_segment -> real assemble,
    against tiny synthetic stills and a short silent wav. Proves the actual wiring (not just the
    primitives) produces a playable mp4 with both audio and video streams."""
    if not _FFMPEG_FULL.is_file():
        pytest.skip(f"ffmpeg-full not found at {_FFMPEG_FULL}; brew install ffmpeg-full")
    monkeypatch.setenv("FFMPEG_BIN", str(_FFMPEG_FULL))
    monkeypatch.setattr(ra, "W", 320)
    monkeypatch.setattr(ra, "H", 180)
    monkeypatch.setattr(ra, "FPS", 10)
    monkeypatch.setattr(ra, "CartesiaTimestampVoice", _fake_voice_factory(6.0))

    images_dir = tmp_path
    Image.new("RGB", (320, 180), (200, 30, 30)).save(images_dir / "img_0.png")
    Image.new("RGB", (320, 180), (30, 200, 30)).save(images_dir / "img_1.png")

    sb_path = tmp_path / "storyboard.json"
    _write_storyboard(sb_path)

    out = ra.reassemble(sb_path, images_dir, tmp_path / "video_v2.mp4")

    assert out.exists() and out.stat().st_size > 0
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(out)],
        capture_output=True, text=True, check=True,
    )
    stream_types = {s["codec_type"] for s in json.loads(proc.stdout)["streams"]}
    assert stream_types == {"video", "audio"}

    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert float(dur) == pytest.approx(6.0, abs=0.5)
