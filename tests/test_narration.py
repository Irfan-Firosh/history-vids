"""Tests for the global narration timeline — beat alignment, image schedule, caption timing."""

from __future__ import annotations

from studio.narration import (
    align_beats,
    build_transcript,
    caption_timeline,
    emphasis_timeline,
    frames_for_span,
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


# ── frames_for_span / image_timeline ─────────────────────────────────────────
def test_frames_for_span_splits_by_min_hold():
    assert frames_for_span(8.0) == 1  # exactly one 8s hold
    assert frames_for_span(15.9) == 1  # not enough for a 2nd ≥8s hold
    assert frames_for_span(16.0) == 2
    assert frames_for_span(25.0) == 3
    assert frames_for_span(2.0) == 1  # always at least one


def test_frames_for_span_intense_adds_one_frame_capped():
    assert frames_for_span(8.0, intense=True) == 2  # +1 for an intense beat
    assert frames_for_span(16.0, intense=True) == 3  # 2 + 1
    assert frames_for_span(8.0, intense=False) == 1  # unchanged when not intense
    assert frames_for_span(100.0, intense=True) == 4  # hard cap 4/beat (bounds render cost)
    assert frames_for_span(100.0) == 4  # cap applies even without intensity


def test_image_timeline_never_repeats_a_frame_file():
    # No image filename may be scheduled in more than one segment (repeats look cheap).
    segs = image_timeline([(0.0, 32.0), (32.0, 48.0), (48.0, 56.0)], [4, 2, 1])
    names = [s[0] for s in segs]
    assert len(names) == len(set(names))  # all distinct


def test_image_timeline_splits_long_beats_into_distinct_frames():
    # 2 frames for beat 0, 1 for beat 1 → distinct files, no repeats, contiguous.
    segs = image_timeline([(0.0, 16.0), (16.0, 24.0)], [2, 1])
    names = [s[0] for s in segs]
    assert names == ["img_0.png", "img_0_1.png", "img_1.png"]
    # never the same file twice in a row
    assert all(a != b for a, b in zip(names, names[1:], strict=False))
    assert segs[0] == ("img_0.png", 0.0, 8.0) and segs[1] == ("img_0_1.png", 8.0, 16.0)


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


# ── emphasis_timeline ────────────────────────────────────────────────────────
def test_emphasis_timeline_emits_only_marked_beats_with_index_and_span():
    spans = [(0.0, 4.0), (4.0, 11.0), (11.0, 15.0)]
    emphases = ["", "18,000 miles", "   "]  # only the middle beat is a real callout
    assert emphasis_timeline(spans, emphases) == [("18,000 miles", 1, 4.0, 11.0)]


def test_emphasis_timeline_is_empty_when_no_beat_is_marked():
    assert emphasis_timeline([(0.0, 4.0), (4.0, 8.0)], ["", ""]) == []


def test_emphasis_timeline_enforces_minimum_spacing_between_callouts():
    # Four marked beats close together; with a 35s gap only the first + one ~40s later survive,
    # so callouts stay rare (~2-3 per 90s) even when the analysis pass over-proposes.
    spans = [(0.0, 10.0), (10.0, 20.0), (20.0, 30.0), (40.0, 50.0)]
    emphases = ["A", "B", "C", "D"]
    kept = emphasis_timeline(spans, emphases, min_gap_sec=35.0)
    assert [(t, i) for t, i, _s, _e in kept] == [("A", 0), ("D", 3)]  # B, C dropped (too soon)


def test_emphasis_timeline_times_the_callout_to_the_spoken_phrase():
    # The phrase sits late in the beat → the callout appears near (just before) when it is spoken,
    # not at the beat start; it holds until the beat ends.
    spans = [(0.0, 20.0)]
    narr = "the two fleets circled all morning before they finally met at Tsushima"
    (text, i, start, end) = emphasis_timeline(spans, ["Tsushima"], [narr])[0]
    assert text == "Tsushima" and i == 0 and end == 20.0
    spoken = 20.0 * (narr.lower().index("tsushima") / len(narr))  # ~ when the word is said
    assert start < spoken  # lands on/before the word (a lead is subtracted)
    assert start > 8.0  # and NOT at the beat start — it's synced to the late phrase


def test_emphasis_timeline_falls_back_to_beat_start_when_phrase_not_found():
    # Callout text not present in the narration (or no narration) → show from the start of the beat.
    spans = [(4.0, 14.0)]
    out = emphasis_timeline(spans, ["1905"], ["no year appears in this spoken line at all"])
    assert out == [("1905", 0, 4.0, 14.0)]


def test_emphasis_timeline_clamps_start_to_keep_min_hold():
    # A phrase at the very end of the beat is pulled earlier so it's on screen >= min_hold seconds.
    spans = [(0.0, 10.0)]
    narr = "a long calm windup and then, right at the very end, Tsushima"
    (_t, _i, start, end) = emphasis_timeline(spans, ["Tsushima"], [narr], min_hold_sec=2.0)[0]
    assert end == 10.0 and start <= 8.0  # end - min_hold
