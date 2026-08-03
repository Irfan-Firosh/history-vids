"""End-to-end assembler tests with synthetic images and silent audio — no API calls, no network.

Two layers, both zero-cost:

1. `test_full_assembly_from_shots_to_mp4` exercises the low-level building blocks directly
   (shot-plan -> segment -> concat -> subtitle): `studio.shots.plan_shots`,
   `tools.render.segments.render_segment`, `tools.render.assemble.assemble`.
2. `test_assemble_video_end_to_end_with_real_ffmpeg` exercises the actual PRODUCTION call site,
   `tools.studio_poc._assemble_video` (what `render_storyboard`/`assemble_storyboard` call), against
   real images and real ffmpeg — proving the specific `image_timeline` + `render_segment` +
   `assemble` wiring in that function is correct, not just the primitives it calls.

Together these are the "L4" gate that would have caught the 12.8-hour single-pass filtergraph
before it ever ran against a real script. Scenes come from a committed fixture
(`tests/fixtures/golden_run/storyboard.json`); the per-shot images are tiny synthetic PIL stills
generated on the fly (never reference frames), and the narration is a silent lavfi-generated wav —
so the whole test costs nothing and touches no network.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from studio import Scene, Storyboard, storyboard_from_dict
from studio.narration import caption_timeline
from studio.shots import plan_shots
from tools.render.assemble import assemble
from tools.render.segments import render_segment

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "golden_run"

#: The only local ffmpeg build with libass (the default Homebrew `ffmpeg` lacks it — see
#: tools/render/ffmpeg.py). Skip rather than error on a machine without this exact build, so the
#: suite stays green on CI/other developers' machines instead of failing on a missing binary.
_FFMPEG_FULL = Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


def _require_ffmpeg_full(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point FFMPEG_BIN at the libass-capable build, explicitly — never depend on whatever
    FFMPEG_BIN happens to be exported in the ambient shell (see tools/render/ffmpeg.py)."""
    if not _FFMPEG_FULL.is_file():
        pytest.skip(f"ffmpeg-full not found at {_FFMPEG_FULL}; brew install ffmpeg-full")
    monkeypatch.setenv("FFMPEG_BIN", str(_FFMPEG_FULL))


@pytest.mark.integration
def test_full_assembly_from_shots_to_mp4(tmp_path, monkeypatch):
    _require_ffmpeg_full(monkeypatch)

    data = json.loads((FIXTURE_DIR / "storyboard.json").read_text())
    scenes = storyboard_from_dict(data).scenes
    beat_spans = [(0.0, 4.0), (4.0, 8.0)]
    shots = plan_shots(beat_spans, scenes, words_per_shot=4)
    assert len(shots) >= 4

    for i, shot in enumerate(shots):
        img = tmp_path / shot.image_key
        Image.new("RGB", (640, 360), (240 - i * 8, 238, 230)).save(img)

    segs = []
    for shot in shots:
        seg, cached = render_segment(
            tmp_path / shot.image_key, shot.duration, tmp_path / "segs",
            width=640, height=360, fps=15,
        )
        assert cached is False
        segs.append(seg)

    # Second pass must hit the cache.
    _, cached_again = render_segment(
        tmp_path / shots[0].image_key, shots[0].duration, tmp_path / "segs",
        width=640, height=360, fps=15,
    )
    assert cached_again is True

    wav = tmp_path / "narration.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=mono", "-t", "8", str(wav)],
        check=True, capture_output=True,
    )

    cues = caption_timeline(beat_spans, [s.narration for s in scenes])
    out = assemble(
        segs, wav, cues, tmp_path / "video.mp4",
        work_dir=tmp_path / "work", width=640, height=360, fps=15,
    )

    assert out.exists() and out.stat().st_size > 0
    assert _probe_duration(out) == pytest.approx(8.0, abs=0.5)


@pytest.mark.integration
def test_assemble_video_end_to_end_with_real_ffmpeg(tmp_path, monkeypatch):
    """`_assemble_video` is the function `render_storyboard`/`assemble_storyboard` actually call —
    the test above proves the primitives work, this proves ITS specific wiring (image_timeline +
    render_segment + assemble, run-dir layout, manifest stats) is correct end to end, with no
    mocks. Runs at a tiny resolution/fps (module globals monkeypatched) to stay fast."""
    _require_ffmpeg_full(monkeypatch)
    from tools import studio_poc as sp

    monkeypatch.setattr(sp, "W", 320)
    monkeypatch.setattr(sp, "H", 180)
    monkeypatch.setattr(sp, "FPS", 10)

    rec = sp.RunRecorder.create(
        tmp_path, title="t", images_provider="placeholder", voice_provider="say",
        scene_count=2, run_id="r",
    )
    Image.new("RGB", (320, 180), (200, 30, 30)).save(rec.dir / "img_0.png")
    Image.new("RGB", (320, 180), (30, 30, 200)).save(rec.dir / "img_1.png")

    wav = rec.dir / "narration.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=mono", "-t", "9", str(wav)],
        check=True, capture_output=True,
    )

    sb = Storyboard(title="t", style="s", scenes=(
        Scene(narration="They ran through the smoke.", image_prompt="p", shot_type="character"),
        Scene(narration="Nobody came back that night.", image_prompt="q", shot_type="wide"),
    ))
    beat_spans = [(0.0, 4.5), (4.5, 9.0)]
    frames_per_beat = [1, 1]

    out = sp._assemble_video(rec, sb, wav, beat_spans, frames_per_beat, [], True)

    assert out.exists() and out.stat().st_size > 0
    assert _probe_duration(out) == pytest.approx(9.0, abs=0.5)
    assert rec.manifest.status == "completed"
    assert rec.manifest.stats.shots == 2
    assert rec.manifest.stats.images_generated == 2  # both fresh, nothing cached yet
    assert rec.manifest.stats.images_cached == 0
    assert rec.manifest.stats.subtitle_backend == "libass"
