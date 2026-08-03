import numpy as np

from studio.style_metrics import Envelope, conforms, measure_frame


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
