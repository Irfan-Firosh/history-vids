import numpy as np

from studio.style_metrics import (
    Envelope,
    FrameMetrics,
    conforms,
    measure_frame,
    median_metrics,
)


def _solid(rgb, size=64):
    return np.full((size, size, 3), rgb, dtype=np.uint8)


def test_pure_white_frame_is_fully_near_white_and_unsaturated():
    m = measure_frame(_solid((255, 255, 255)))
    assert m.near_white_pct == 100.0
    assert m.saturation == 0.0
    assert m.edge_density == 0.0


def test_a_two_colour_frame_reports_few_colour_bins():
    a = _solid((250, 248, 240), 32)
    b = _solid((20, 20, 20), 32)
    m = measure_frame(np.concatenate([a, b], axis=0))
    assert m.colour_bins <= 4


def test_a_saturated_frame_exceeds_the_reference_envelope():
    env = Envelope(saturation=(0.16, 0.27), colour_bins=(13, 16), near_white_pct=(29.0, 45.0))
    ok, failures = conforms(measure_frame(_solid((255, 0, 0))), env)
    assert ok is False
    assert any("saturation" in f for f in failures)


def test_envelope_can_leave_a_metric_ungated():
    """`colour_bins` refused run 20260803-113248 at 43.0 against a 12-20 band. Our implementation
    counts unique (pixel // 48) RGB triples; the research NEVER documents how it computed its own
    "distinct colour bins", and our frames measure richer than its richest channel (ThenFolk 28.7,
    described as a "far richer palette"). Two numbers with the same name and no shared method
    cannot gate a paid render — the same trap `edge_density` carries (mean gradient vs edge-pixel
    fraction, ~26x apart). A metric may be MEASURED without being ENFORCED."""
    env = Envelope(saturation=(0.12, 0.33), near_white_pct=(23.4, 39.9), colour_bins=None)
    m = FrameMetrics(saturation=0.20, brightness=0.78, edge_density=1.1,
                     near_white_pct=30.0, colour_bins=43)
    ok, failures = conforms(m, env)
    assert ok, f"an ungated metric must not refuse: {failures}"


def test_median_of_probe_frames_ignores_one_outlier():
    """The gate refused on a SINGLE probe frame — a sample size of 1 for a stochastic generator,
    judged against an envelope built from 2,703 reference frames. Three frames, judged on the
    median, means one unlucky draw cannot kill a run that has already paid for research, script
    and TTS."""
    good = [FrameMetrics(saturation=0.20, brightness=0.78, edge_density=1.1,
                         near_white_pct=30.0, colour_bins=15) for _ in range(2)]
    outlier = FrameMetrics(saturation=0.90, brightness=0.20, edge_density=9.9,
                           near_white_pct=1.0, colour_bins=99)
    med = median_metrics([*good, outlier])
    assert med.saturation == 0.20
    assert med.near_white_pct == 30.0
    assert med.colour_bins == 15
