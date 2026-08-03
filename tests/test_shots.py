"""Tests for the clause-aware shot planner — the measured reference rate, not a timer."""

from __future__ import annotations

import statistics

from studio.shots import MAX_SHOT_SEC, MIN_SHOT_SEC, Shot, plan_shots, split_clauses
from studio.types import Scene


def _scene(narration: str) -> Scene:
    return Scene(narration=narration, image_prompt="a stick figure", shot_type="character")


def _eight_minute_script() -> tuple[list[tuple[float, float]], list[Scene]]:
    """~1560 words over 52 beats at ~9.23s/beat — the reference channels' ~8-minute median video."""
    beat_words = 30
    beats = 52
    scenes = [_scene(" ".join(["word"] * beat_words) + ".") for _ in range(beats)]
    spans = [(i * 9.23, (i + 1) * 9.23) for i in range(beats)]
    return spans, scenes


def test_split_clauses_breaks_at_punctuation_before_word_count():
    text = "They ran. The fire spread fast across the whole valley that night."
    parts = split_clauses(text, words_per_shot=10)
    assert parts[0] == "They ran."
    assert len(parts) >= 2


def test_split_clauses_covers_every_word_exactly_once():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    parts = split_clauses(text, words_per_shot=5)
    assert " ".join(parts).split() == text.split()


def test_split_clauses_hard_splits_a_long_clause_with_no_punctuation():
    # No punctuation anywhere for split_clauses to break on — the clause must still be chopped
    # by word budget rather than emitted as one long, un-splittable piece.
    text = " ".join(["word"] * 25)
    parts = split_clauses(text, words_per_shot=10)
    assert len(parts) == 3  # 10 + 10 + 5, never one 25-word piece
    assert all(len(p.split()) <= 10 for p in parts)
    assert " ".join(parts).split() == text.split()


def test_plan_shots_hits_the_reference_shot_rate_for_an_eight_minute_script():
    # 8 min at 196 wpm = ~1568 words over ~52 beats. At ~10 words/shot that is ~157 shots,
    # i.e. ~3.1s per shot — inside the reference envelope (p10 0.9 / median 2.2 / p90 4.6).
    spans, scenes = _eight_minute_script()
    shots = plan_shots(spans, scenes)
    assert 120 <= len(shots) <= 240
    durations = [s.end - s.start for s in shots]
    assert all(d >= MIN_SHOT_SEC for d in durations)
    assert all(d <= MAX_SHOT_SEC for d in durations)


def test_plan_shots_median_duration_lands_in_the_reference_band():
    # The point of clause-aware splitting is landing inside the measured band, not merely
    # returning a non-empty list — this is the number the whole task exists to fix.
    spans, scenes = _eight_minute_script()
    shots = plan_shots(spans, scenes)
    durations = [s.end - s.start for s in shots]
    median_duration = statistics.median(durations)
    assert 0.9 <= median_duration <= 4.6  # reference p10 .. p90 envelope


def test_plan_shots_produces_contiguous_monotonic_spans():
    scenes = [_scene("one two three four. five six seven eight."), _scene("nine ten eleven.")]
    spans = [(0.0, 6.0), (6.0, 9.0)]
    shots = plan_shots(spans, scenes, words_per_shot=4)
    assert shots[0].start == 0.0
    assert shots[-1].end == 9.0
    for a, b in zip(shots, shots[1:], strict=False):
        assert b.start == a.end


def test_image_keys_are_unique_so_adjacent_shots_never_reuse_a_frame():
    scenes = [_scene("one two three four five six seven eight.")]
    shots = plan_shots([(0.0, 8.0)], scenes, words_per_shot=4)
    keys = [s.image_key for s in shots]
    assert len(keys) == len(set(keys))


def test_a_beat_too_short_to_split_yields_exactly_one_shot():
    shots = plan_shots([(0.0, 1.0)], [_scene("Go.")])
    assert len(shots) == 1
    assert shots[0].start == 0.0 and shots[0].end == 1.0


def test_plan_shots_merges_very_short_clauses_to_avoid_flicker():
    # Four one-word clauses over a 2.0s beat would be 0.5s each if left unmerged — below
    # MIN_SHOT_SEC. They must be paired back up until every resulting shot clears the floor.
    scene = _scene("Go. Stop. Now. Wait.")
    shots = plan_shots([(0.0, 2.0)], [scene], words_per_shot=1)
    durations = [s.end - s.start for s in shots]
    assert all(d >= MIN_SHOT_SEC for d in durations)
    assert len(shots) == 2


def test_plan_shots_splits_a_long_punctuation_free_beat_instead_of_one_long_hold():
    # A beat with no internal punctuation must still be cut into multiple shots, never held as
    # a single long frame for the whole span.
    text = " ".join(["word"] * 40)
    shots = plan_shots([(0.0, 30.0)], [_scene(text)])
    assert len(shots) > 1
    assert all(s.end - s.start <= MAX_SHOT_SEC for s in shots)


def test_shot_type_is_inherited_from_its_beat():
    scene = Scene(narration="one two three four.", image_prompt="a map", shot_type="map")
    assert all(s.shot_type == "map" for s in plan_shots([(0.0, 4.0)], [scene]))


def test_shot_is_frozen():
    shot = Shot(beat_index=0, sub_index=0, start=0.0, end=1.0, image_key="img_0.png")
    try:
        shot.start = 5.0  # type: ignore[misc]
    except Exception:
        pass
    else:
        raise AssertionError("Shot must be frozen")
