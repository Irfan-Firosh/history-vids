from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import pytest
from PIL import Image

from studio.shots import Shot
from tools.render.assemble import MAX_PNG_OVERLAY_CUES, assemble, concat_file, render_shots


def _make_image(path: Path, color: tuple[int, int, int] = (200, 30, 30)) -> Path:
    """A tiny synthetic still — no downloads, no real assets, encodes in milliseconds."""
    Image.new("RGB", (64, 36), color=color).save(path)
    return path


def _make_wav(path: Path, duration: float = 0.3, rate: int = 8000) -> Path:
    """A tiny silent WAV built with the stdlib `wave` module — no ffmpeg call needed for the
    fixture itself, keeping these tests hermetic."""
    n_frames = int(duration * rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * n_frames)
    return path


def _stream_types(path: Path) -> set[str]:
    """Which codec_types ffprobe reports in `path` — used to prove the wav was actually muxed."""
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(proc.stdout)
    return {s["codec_type"] for s in data["streams"]}


# --- brief's tests, verbatim (Step 1) ---


def test_concat_file_quotes_paths_so_spaces_and_apostrophes_cannot_break_it(tmp_path):
    a = tmp_path / "seg one.mp4"
    b = tmp_path / "it's two.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    out = concat_file([a, b], tmp_path / "list.txt")
    text = out.read_text()
    assert text.count("file ") == 2
    # An unescaped apostrophe terminates the quoted string and corrupts the demuxer list.
    assert "it'\\''s two.mp4" in text or "it\\'s two.mp4" in text


def test_concat_file_rejects_an_empty_segment_list(tmp_path):
    with pytest.raises(ValueError, match="no segments"):
        concat_file([], tmp_path / "list.txt")


def test_png_overlay_ceiling_is_low_enough_to_stay_fast():
    # Benchmarked on M2: ~0.011 s/frame per serially chained overlay. At 50 overlays an 8-minute
    # video is already ~2 hours, so the fallback must refuse anything larger.
    assert MAX_PNG_OVERLAY_CUES <= 50


# --- the Shot -> render_segment adapter this task owns ---


def test_render_shots_maps_image_key_and_duration_through_render_segment(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    _make_image(image_dir / "img_0.png", color=(200, 30, 30))
    _make_image(image_dir / "img_1.png", color=(30, 30, 200))
    shots = [
        Shot(beat_index=0, sub_index=0, start=0.0, end=0.2, image_key="img_0.png"),
        Shot(beat_index=1, sub_index=0, start=0.2, end=0.5, image_key="img_1.png"),
    ]

    segments = render_shots(shots, image_dir, tmp_path / "segments", width=64, height=36, fps=10)

    assert len(segments) == 2
    assert all(s.exists() and s.stat().st_size > 0 for s in segments)
    # Distinct image bytes/durations -> distinct content-hash cache keys, in shot order.
    assert segments[0] != segments[1]


def test_render_shots_reuses_the_segment_cache_on_a_second_call(tmp_path):
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    _make_image(image_dir / "img_0.png")
    shots = [Shot(beat_index=0, sub_index=0, start=0.0, end=0.2, image_key="img_0.png")]
    out_dir = tmp_path / "segments"

    first = render_shots(shots, image_dir, out_dir, width=64, height=36, fps=10)
    second = render_shots(shots, image_dir, out_dir, width=64, height=36, fps=10)

    assert first == second
    assert first[0].exists()


# --- assemble(): stream-copy proof, real libass burn, and the no-libass refusal ---


def test_assemble_stream_copies_video_when_there_are_no_caption_cues(tmp_path, monkeypatch):
    monkeypatch.delenv("FFMPEG_BIN", raising=False)
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    _make_image(image_dir / "a.png", color=(200, 30, 30))
    _make_image(image_dir / "b.png", color=(30, 200, 30))
    shots = [
        Shot(beat_index=0, sub_index=0, start=0.0, end=0.2, image_key="a.png"),
        Shot(beat_index=1, sub_index=0, start=0.2, end=0.4, image_key="b.png"),
    ]
    segments = render_shots(shots, image_dir, tmp_path / "segments", width=64, height=36, fps=10)
    wav = _make_wav(tmp_path / "narration.wav", duration=0.4)

    recorded: dict[str, list[str]] = {}
    real_run = subprocess.run

    def spy(cmd, **kwargs):
        recorded["cmd"] = cmd
        return real_run(cmd, **kwargs)

    monkeypatch.setattr("tools.render.assemble.subprocess.run", spy)

    out = assemble(
        segments, wav, [], tmp_path / "final.mp4",
        work_dir=tmp_path / "work", width=64, height=36, fps=10,
    )

    assert out.exists()
    assert out.stat().st_size > 0
    cmd = recorded["cmd"]
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert "libx264" not in cmd
    assert _stream_types(out) == {"video", "audio"}


def test_assemble_burns_subtitles_via_libass_in_a_single_pass(tmp_path, monkeypatch):
    monkeypatch.setenv("FFMPEG_BIN", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    _make_image(image_dir / "a.png")
    shots = [Shot(beat_index=0, sub_index=0, start=0.0, end=0.3, image_key="a.png")]
    segments = render_shots(shots, image_dir, tmp_path / "segments", width=64, height=36, fps=10)
    wav = _make_wav(tmp_path / "narration.wav", duration=0.3)
    cues = [("hello world", 0.0, 0.3)]

    recorded: dict[str, list[str]] = {}
    real_run = subprocess.run

    def spy(cmd, **kwargs):
        recorded["cmd"] = cmd
        return real_run(cmd, **kwargs)

    monkeypatch.setattr("tools.render.assemble.subprocess.run", spy)

    out = assemble(
        segments, wav, cues, tmp_path / "final.mp4",
        work_dir=tmp_path / "work", width=64, height=36, fps=10,
    )

    assert out.exists()
    assert out.stat().st_size > 0
    cmd = recorded["cmd"]
    assert any("subtitles=" in a for a in cmd)
    assert "libx264" in cmd  # burning captions is the one path that must re-encode
    assert _stream_types(out) == {"video", "audio"}


def test_assemble_refuses_rather_than_silently_dropping_captions(tmp_path, monkeypatch):
    """This assembler burns captions with ZERO PNG-overlay nodes by design (that's the whole
    point of the rebuild) — it has no slow-path renderer to fall back to at all. So when the
    active ffmpeg lacks libass it must refuse outright, even with a single cue far under
    MAX_PNG_OVERLAY_CUES, rather than silently emitting a video with no captions."""
    monkeypatch.setattr("tools.render.assemble.subtitle_backend", lambda **_kw: "png_overlay")
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    _make_image(image_dir / "a.png")
    shots = [Shot(beat_index=0, sub_index=0, start=0.0, end=0.2, image_key="a.png")]
    segments = render_shots(shots, image_dir, tmp_path / "segments", width=64, height=36, fps=10)
    wav = _make_wav(tmp_path / "narration.wav", duration=0.2)
    cues = [("only one cue", 0.0, 0.2)]  # far under MAX_PNG_OVERLAY_CUES

    with pytest.raises(RuntimeError, match="libass"):
        assemble(
            segments, wav, cues, tmp_path / "final.mp4",
            work_dir=tmp_path / "work", width=64, height=36, fps=10,
        )


def test_assemble_raises_when_cue_count_exceeds_the_ceiling_and_no_libass(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.render.assemble.subtitle_backend", lambda **_kw: "png_overlay")
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    _make_image(image_dir / "a.png")
    shots = [Shot(beat_index=0, sub_index=0, start=0.0, end=0.2, image_key="a.png")]
    segments = render_shots(shots, image_dir, tmp_path / "segments", width=64, height=36, fps=10)
    wav = _make_wav(tmp_path / "narration.wav", duration=0.2)
    cues = [(f"cue {i}", 0.0, 0.01) for i in range(MAX_PNG_OVERLAY_CUES + 1)]

    with pytest.raises(RuntimeError, match=str(MAX_PNG_OVERLAY_CUES)):
        assemble(
            segments, wav, cues, tmp_path / "final.mp4",
            work_dir=tmp_path / "work", width=64, height=36, fps=10,
        )
