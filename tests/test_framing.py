"""Framing variety is structural — these tests are the guarantee, not the prompt."""

from __future__ import annotations

from collections import Counter

from studio.framing import MAX_RUN, legal_framings, plan_framings
from studio.style import FRAMINGS


def _longest_run(seq):
    best = run = 1
    for a, b in zip(seq, seq[1:], strict=False):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best


def test_framing_names_never_collide_with_shot_type_names():
    """A real run died on `shot_type: "detail"`. Both fields answer "what kind of shot is this?",
    and when framing also offered a "wide" the script LLM started writing framing values into
    shot_type. Two overlapping vocabularies in one JSON object invite exactly that."""
    from studio.types import SHOT_TYPES

    assert not set(FRAMINGS) & set(SHOT_TYPES)


def test_every_framing_name_has_a_directive():
    for shot_type in ("character", "wide", "concept", "map"):
        for name in legal_framings(shot_type):
            assert name in FRAMINGS


def test_never_exceeds_the_max_run_even_when_every_shot_requests_the_same():
    shots = ["character"] * 30
    out = plan_framings(shots, ["medium"] * 30)
    assert _longest_run(out) <= MAX_RUN


def test_a_long_uniform_run_uses_most_of_the_available_framings():
    """The measured failure was 57% of frames in one layout. Spread is the point."""
    out = plan_framings(["character"] * 40)
    used = Counter(out)
    assert len(used) >= 5
    assert max(used.values()) / len(out) < 0.40


def test_concept_and_map_never_get_a_framing_that_requires_a_person():
    out = plan_framings(["concept", "map"] * 12)
    assert set(out) <= set(legal_framings("concept"))
    assert "close_up" not in out and "over_shoulder" not in out


def test_a_legal_request_is_honoured():
    out = plan_framings(["character", "character"], ["cutaway", "establishing"])
    assert out == ["cutaway", "establishing"]


def test_an_illegal_request_is_replaced_not_raised():
    out = plan_framings(["concept"], ["over_shoulder"])
    assert out[0] in legal_framings("concept")


def test_garbage_and_short_request_lists_degrade_quietly():
    out = plan_framings(["character"] * 4, ["not_a_framing", "medium"])
    assert len(out) == 4
    assert all(f in FRAMINGS for f in out)


def test_is_deterministic_so_a_rerun_reproduces_the_storyboard():
    shots = ["character", "concept", "wide", "map", "character"] * 6
    assert plan_framings(shots) == plan_framings(shots)


def test_empty_input():
    assert plan_framings([]) == []
