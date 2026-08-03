"""L5 acceptance gate: measure our own rendered output against the Axen reference (side-effecting).

Extracts frames from an encoded video with ffmpeg, computes the mean absolute inter-frame
difference on a downscaled grayscale copy, and classifies each sampled interval as a hard cut
(>26.0), frozen/held (<2.0), or in-motion. From that it derives `cuts_per_min`, `frozen_pct`, and
the shot-duration distribution, and compares the result to Axen's measured numbers in
context/research/2026-08-01/04-video-forensics.md.

Two cut-rate definitions exist in that forensics sample and they are NOT interchangeable:
  - FULL_CUT only: 16.6 cuts/min — an abrupt, whole-frame replacement. This detector's
    frame-difference threshold measures exactly this kind of change.
  - All visual changes (FULL_CUT + FG_SWAP): 23.5/min, median shot 2.20s (p10 0.90 / p90 4.60).
    FG_SWAP is a foreground-only swap over a held background; it does not necessarily move the
    whole-frame mean difference past the hard-cut threshold, so this detector does not count it
    as a cut.

TARGETS mixes both on purpose, matching the plan's Global Constraints: `cuts_per_min` (16-18) is
the FULL_CUT-only band; `median_shot_sec` (0.9-4.6) is the ALL-CHANGES p10/p90 band, because that
is the distribution Axen's 2.20s median actually comes from. A render that adds foreground swaps
(out of scope for this task; see the plan's §7 deferral) would still only move `cuts_per_min` on
FULL_CUT boundaries, so a real Axen-shaped render could show correct FULL_CUT-only cuts_per_min
while its median_shot_sec drifts toward the high end of the ALL-CHANGES band, since this detector
does not treat a FG_SWAP as a shot boundary at all. That gap is inherent to mixing the two
definitions in one TARGETS dict — flagged here, not resolved, because resolving it means adding a
second, gentler FG_SWAP threshold, which needs its own calibration pass against real FG_SWAP
frames, not synthetic ones.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from pydantic import BaseModel, ConfigDict

#: Downscaled analysis resolution. Cut/frozen classification needs whole-frame mean difference,
#: not per-pixel fidelity — this keeps ffmpeg decode + numpy diff cheap even on an 8-minute render.
_ANALYSIS_WIDTH = 160
_ANALYSIS_HEIGHT = 90
_FRAME_BYTES = _ANALYSIS_WIDTH * _ANALYSIS_HEIGHT

#: Mean absolute inter-frame difference thresholds, on a 0-255 grayscale scale. Verified against
#: synthetic clips in tests/test_conformance.py: solid-colour hard cuts measure 47-150, held
#: (unchanging) frames measure 0.0, even after libx264 crf=18 compression.
HARD_CUT_THRESHOLD = 26.0
FROZEN_THRESHOLD = 2.0

#: Axen reference bands. See the module docstring for which cut-rate definition each key uses.
TARGETS: dict[str, tuple[float, float]] = {
    "cuts_per_min": (16.0, 18.0),
    "frozen_pct": (94.6, 100.0),
    "median_shot_sec": (0.9, 4.6),
}


class MotionReport(BaseModel):
    """How an encoded video's shot rhythm measures against the Axen reference."""

    model_config = ConfigDict(frozen=True)

    cuts_per_min: float
    frozen_pct: float
    median_shot_sec: float
    p10_shot_sec: float
    p90_shot_sec: float

    @property
    def failures(self) -> tuple[str, ...]:
        """Which TARGETS bands this report falls outside of, human-readable."""
        fails: list[str] = []
        checks = (
            ("cuts_per_min", self.cuts_per_min, TARGETS["cuts_per_min"]),
            ("frozen_pct", self.frozen_pct, TARGETS["frozen_pct"]),
            ("median_shot_sec", self.median_shot_sec, TARGETS["median_shot_sec"]),
        )
        for name, value, (low, high) in checks:
            if not low <= value <= high:
                fails.append(f"{name} {value:.2f} outside target {low}-{high}")
        return tuple(fails)

    @property
    def ok(self) -> bool:
        """False when any measured value falls outside its TARGETS band."""
        return not self.failures

    def summary(self) -> str:
        return (
            f"{self.cuts_per_min:.1f} cuts/min · {self.frozen_pct:.1f}% frozen · "
            f"median shot {self.median_shot_sec:.2f}s "
            f"(p10 {self.p10_shot_sec:.2f} / p90 {self.p90_shot_sec:.2f})"
        )


def _extract_gray_frames(path: Path, fps: int) -> np.ndarray:
    """Decode `path` to grayscale frames at `fps`, downscaled to the analysis resolution.

    Streams raw frames over ffmpeg's stdout rather than writing PNGs to disk — an 8-minute render
    at 10 fps is ~4800 frames, and round-tripping that many files is pure overhead a mean-diff
    computation doesn't need.
    """
    cmd = [
        "ffmpeg", "-nostdin", "-v", "error", "-i", str(path),
        "-vf", f"fps={fps},scale={_ANALYSIS_WIDTH}:{_ANALYSIS_HEIGHT},format=gray",
        "-f", "rawvideo", "-pix_fmt", "gray", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, check=True)
    n_frames = len(proc.stdout) // _FRAME_BYTES
    if n_frames < 2:
        raise ValueError(f"{path}: decoded {n_frames} frame(s) at {fps}fps, need at least 2")
    return np.frombuffer(
        proc.stdout[: n_frames * _FRAME_BYTES], dtype=np.uint8
    ).reshape(n_frames, _ANALYSIS_HEIGHT, _ANALYSIS_WIDTH)


def measure_video(path: Path, fps: int = 10) -> MotionReport:
    """Measure cut rate, frozen-time share, and shot-duration distribution of an encoded video.

    Side-effecting (shells out to ffmpeg) — lives in `tools/`, never `studio/`.
    """
    frames = _extract_gray_frames(path, fps)
    n_frames = frames.shape[0]
    duration_sec = n_frames / fps

    diffs = np.abs(frames[1:].astype(np.float32) - frames[:-1].astype(np.float32)).mean(
        axis=(1, 2)
    )
    is_cut = diffs > HARD_CUT_THRESHOLD
    is_frozen = diffs < FROZEN_THRESHOLD

    cut_indices = np.flatnonzero(is_cut)
    boundaries = [0.0, *((i + 1) / fps for i in cut_indices), duration_sec]
    # Pairwise adjacent-boundary iteration: `boundaries[1:]` is deliberately one shorter, so
    # `strict=True` (which requires equal-length iterables) would raise on every call.
    shot_durations = np.array(
        [end - start for start, end in zip(boundaries, boundaries[1:], strict=False)]
    )

    cuts_per_min = len(cut_indices) / (duration_sec / 60.0) if duration_sec > 0 else 0.0
    frozen_pct = float(is_frozen.mean()) * 100.0

    return MotionReport(
        cuts_per_min=round(float(cuts_per_min), 2),
        frozen_pct=round(frozen_pct, 2),
        median_shot_sec=round(float(np.median(shot_durations)), 3),
        p10_shot_sec=round(float(np.percentile(shot_durations, 10)), 3),
        p90_shot_sec=round(float(np.percentile(shot_durations, 90)), 3),
    )


def _main() -> None:
    if len(sys.argv) != 2:
        print("usage: uv run python tools/conformance.py <video.mp4>", file=sys.stderr)
        raise SystemExit(2)
    report = measure_video(Path(sys.argv[1]))
    print(report.summary())
    if report.ok:
        print("PASS — within Axen reference bands")
    else:
        print("FAIL")
        for failure in report.failures:
            print(f"  - {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    _main()
