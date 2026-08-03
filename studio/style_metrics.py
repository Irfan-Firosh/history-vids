"""Measure a frame's look, and compare it to the reference envelope (pure).

Turns "does the art look right?" into an assertion. Envelope values are measured in
context/research/2026-08-01/04-video-forensics.md across 5 channels and 2,703 style frames:
saturation 0.16-0.27, 13-16 distinct colour bins per frame, 29-45% near-white.

CAVEAT: these tests prove the metric MATH. They cannot prove the envelope is the right TARGET —
that rests entirely on the forensics sample. Keep the envelope as data with its provenance, so it
is cheap to re-measure rather than baked into code.
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, ConfigDict

_NEAR_WHITE = 235
_BIN_WIDTH = 48


class FrameMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    saturation: float
    brightness: float
    edge_density: float
    near_white_pct: float
    colour_bins: int


class Envelope(BaseModel):
    """Inclusive (min, max) ranges the reference occupies."""

    model_config = ConfigDict(frozen=True)

    saturation: tuple[float, float]
    colour_bins: tuple[int, int]
    near_white_pct: tuple[float, float]


def measure_frame(rgb: np.ndarray) -> FrameMetrics:
    """Measure one RGB frame (H, W, 3), uint8."""
    arr = rgb.astype(np.float32)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    grey = arr.mean(axis=2)
    gx = np.abs(np.diff(grey, axis=1)).mean() if grey.shape[1] > 1 else 0.0
    gy = np.abs(np.diff(grey, axis=0)).mean() if grey.shape[0] > 1 else 0.0
    quantised = (arr // _BIN_WIDTH).astype(np.int32).reshape(-1, 3)
    bins = len(np.unique(quantised, axis=0))
    return FrameMetrics(
        saturation=round(float(sat.mean()), 4),
        brightness=round(float(mx.mean() / 255.0), 4),
        edge_density=round(float((gx + gy) / 2), 3),
        near_white_pct=round(float((grey > _NEAR_WHITE).mean()) * 100, 2),
        colour_bins=int(bins),
    )


def conforms(metrics: FrameMetrics, envelope: Envelope) -> tuple[bool, tuple[str, ...]]:
    """Is this frame inside the reference envelope? Returns (ok, human-readable failures)."""
    failures: list[str] = []
    checks = (
        ("saturation", metrics.saturation, envelope.saturation),
        ("colour_bins", float(metrics.colour_bins), tuple(float(v) for v in envelope.colour_bins)),
        ("near_white_pct", metrics.near_white_pct, envelope.near_white_pct),
    )
    for name, value, (low, high) in checks:
        if not low <= value <= high:
            failures.append(f"{name} {value} outside reference {low}-{high}")
    return (not failures), tuple(failures)
