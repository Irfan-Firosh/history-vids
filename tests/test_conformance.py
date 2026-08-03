"""L5 acceptance gate: does our measured output match the Axen reference?

`measure_video` is proven against SYNTHETIC video only — clips built here with ffmpeg's `lavfi`
color source and `concat` filter, at known cut timestamps. That proves the detector recovers a
known answer; it does NOT prove a real render conforms. The shot rate a real render produces
depends on the punctuation density of the generated script (see
context/research/2026-08-01/04-video-forensics.md and the shot-planner measurements in the task
brief) — a synthetic or fixture script can bracket Axen's ~23.5 changes/min by 8 points either way.
A meaningful conformance run needs `tools/conformance.py` pointed at a real encoded
`result/<channel>/poc/runs/<run>/video.mp4` from this pipeline, not a clip built in this file.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from tools.conformance import TARGETS, MotionReport, measure_video

_FPS = 10
_SIZE = "160x90"


def _concat_clip(tmp_path: Path, colors: list[str], seg_sec: float, fps: int = _FPS) -> Path:
    """A video made of `colors`, each held for `seg_sec` — one known hard cut per boundary."""
    out = tmp_path / "clip.mp4"
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y"]
    for color in colors:
        cmd += ["-f", "lavfi", "-i", f"color=c={color}:s={_SIZE}:d={seg_sec}:r={fps}"]
    n = len(colors)
    inputs = "".join(f"[{i}:v]" for i in range(n))
    cmd += [
        "-filter_complex", f"{inputs}concat=n={n}:v=1:a=0[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def test_targets_match_the_measured_axen_reference():
    assert TARGETS["cuts_per_min"] == (16.0, 18.0)
    assert TARGETS["frozen_pct"][0] >= 94.6
    assert TARGETS["median_shot_sec"] == (0.9, 4.6)


def test_report_flags_a_slideshow_that_cuts_too_slowly():
    r = MotionReport(cuts_per_min=6.5, frozen_pct=99.0, median_shot_sec=9.2,
                     p10_shot_sec=8.0, p90_shot_sec=10.0)
    assert not r.ok
    assert any("cuts_per_min" in f for f in r.failures)


def test_report_passes_when_every_value_sits_inside_targets():
    r = MotionReport(cuts_per_min=17.0, frozen_pct=96.0, median_shot_sec=2.2,
                     p10_shot_sec=0.9, p90_shot_sec=4.6)
    assert r.ok
    assert r.failures == ()


def test_measure_video_recovers_a_known_cut_count_and_shot_length(tmp_path):
    # 4 one-second segments -> exactly 3 hard cuts, each shot exactly 1.0s long.
    clip = _concat_clip(tmp_path, ["red", "blue", "green", "yellow"], seg_sec=1.0)

    report = measure_video(clip, fps=_FPS)

    # 3 cuts over a 4-second clip = 45 cuts/min.
    assert report.cuts_per_min == 45.0
    assert abs(report.median_shot_sec - 1.0) < 0.05
    assert abs(report.p10_shot_sec - 1.0) < 0.05
    assert abs(report.p90_shot_sec - 1.0) < 0.05


def test_measure_video_reports_zero_cuts_and_fully_frozen_on_a_static_clip(tmp_path):
    clip = _concat_clip(tmp_path, ["red"], seg_sec=2.0)

    report = measure_video(clip, fps=_FPS)

    assert report.cuts_per_min == 0.0
    assert report.frozen_pct == 100.0
    assert abs(report.median_shot_sec - 2.0) < 0.05
