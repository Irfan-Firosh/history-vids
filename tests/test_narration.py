"""Tests for the global narration timeline — beat alignment, image schedule, caption timing."""

from __future__ import annotations

from studio.narration import (
    align_beats,
    build_transcript,
    caption_timeline,
    image_timeline,
)


# ── build_transcript ───────────────────────────────────────────────────────────
def test_build_transcript_joins_and_strips():
    assert build_transcript(["  A. ", "", "  B?  "]) == "A. B?"


# ── align_beats ──────────────────────────────────────────────────────────────
def test_align_beats_snaps_boundary_to_the_largest_pause():
    # Two equal beats; a clear 1.2s silence sits right at the proportional midpoint (2.4s).
    starts = [0.0, 1.0, 3.0, 4.0]
    ends = [0.9, 1.8, 3.9, 4.8]
    spans = align_beats([1, 1], starts, ends)
    assert spans == [(0.0, 2.4), (2.4, 4.8)]  # cut lands in the pause, not mid-word


def test_align_beats_snaps_to_nearest_gap_when_no_pause_in_window():
    # No pause near the ideal (2.5s) within a tight window → cut still lands in a real inter-word
    # gap (2.0s), never mid-word. This is the "switching a bit off" fix.
    starts = [0.0, 1.0, 2.0, 3.0]
    ends = [1.0, 2.0, 3.0, 4.0]
    spans = align_beats([5, 3], starts, ends, snap_window=0.1)
    assert spans == [(0.0, 2.0), (2.0, 4.0)]  # nearest gap to ideal 2.5, not the raw estimate


def test_align_beats_is_word_count_independent_and_covers_the_timeline():
    # Far fewer words than beats/characters (numbers expand in speech) — still valid, contiguous.
    spans = align_beats([100, 50, 50], [0.0, 3.0, 7.0], [2.5, 6.5, 9.0])
    assert len(spans) == 3
    assert spans[0][0] == 0.0 and spans[-1][1] == 9.0  # covers [0, total]
    for (_, e), (s, _) in zip(spans, spans[1:], strict=False):
        assert e == s and s >= 0  # contiguous + monotonic


def test_align_beats_handles_empty_and_degenerate():
    assert align_beats([], [], []) == []
    assert align_beats([1, 1], [], []) == [(0.0, 0.0), (0.0, 0.0)]  # no audio → no time


def test_image_timeline_never_repeats_a_frame_file():
    # No image filename may be scheduled in more than one segment (repeats look cheap).
    segs = image_timeline([(0.0, 32.0), (32.0, 48.0), (48.0, 56.0)], [4, 2, 1])
    names = [s[0] for s in segs]
    assert len(names) == len(set(names))  # all distinct


def test_image_timeline_covers_each_beat_contiguously():
    spans = [(0.0, 4.0), (4.0, 9.0)]
    segs = image_timeline(spans, [1, 1])
    assert segs[0][1] == 0.0 and segs[-1][2] == 9.0
    for (_, _, e), (_, s, _) in zip(segs, segs[1:], strict=False):
        assert abs(e - s) < 1e-6


def test_image_timeline_one_frame_per_beat_is_single_hold():
    assert image_timeline([(0.0, 5.0)], [1]) == [("img_0.png", 0.0, 5.0)]
    assert image_timeline([(0.0, 5.0)], [0]) == [("img_0.png", 0.0, 5.0)]  # coerced to ≥1


# ── caption_timeline ─────────────────────────────────────────────────────────
def test_caption_timeline_offsets_cues_into_their_beat_span():
    narrations = ["One two three four five.", "Six seven eight nine ten."]
    spans = [(0.0, 4.0), (4.0, 7.0)]
    cues = caption_timeline(spans, narrations)
    assert cues, "expected caption cues"
    # every cue lies within the video; beat-1 cues start at/after 4.0s.
    assert all(0.0 <= s <= e <= 7.0 for _, s, e in cues)
    assert any(s >= 4.0 for _, s, _ in cues)
