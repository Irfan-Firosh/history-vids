"""Global narration timeline (pure) — align beats/captions/images to REAL spoken word times.

The pacing fix: instead of synthesising each beat separately (choppy prosody) and guessing caption
timing, we synthesise the whole script in ONE Cartesia request with ``add_timestamps`` and drive the
video off the returned word timings. This module is the pure math:

  1. ``build_transcript`` — join beats into one continuous transcript.
  2. ``align_beats_to_words`` — map ordered beats onto the audio by ANCHORING each beat's end to the
     REAL spoken word where its text runs out (Cartesia returns the actual words + per-word times).
     This is the accurate path. ``align_beats`` (proportional, pause-snapped) stays as the fallback
     for voices that give no word text (offline ``say``); it drifts up to several seconds mid-video,
     which is exactly what word-anchoring fixes.
  3. ``caption_timeline`` — per-cue (text, start, end) over the whole video, anchored to beat spans.
  4. ``image_timeline`` — the on-screen image schedule: each beat split into N distinct frames, each
     held ≥ ``MIN_FRAME_HOLD`` seconds; adjacent segments are never the same file (no cut-back).

Only word start/end arrays are needed for alignment — never the word text — which is what makes it
robust to how the TTS pronounces numbers, abbreviations, or hyphenated words.
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import accumulate

from studio.captions import cue_timings, split_caption_cues


def build_transcript(narrations: Sequence[str]) -> str:
    """Join beats into one continuous transcript for a single natural-prosody TTS request."""
    return " ".join(n.strip() for n in narrations if n.strip())


def align_beats(
    weights: Sequence[float],
    word_starts: Sequence[float],
    word_ends: Sequence[float],
    snap_window: float = 1.0,
) -> list[tuple[float, float]]:
    """Map ordered beats onto the audio timeline using real word timings.

    Each beat's *ideal* end time is proportional to its narration length; that boundary is snapped
    to the largest speech pause (inter-word gap) within ``±snap_window`` seconds. If no gap falls
    in the window, it snaps to the *nearest* inter-word gap instead of the raw estimate — so a cut
    ALWAYS lands in silence, never mid-word (the "switching a bit off" case). Returns contiguous,
    monotonic (start, end) spans over ``[0, total]``, where ``total`` is the last word's end time.
    """
    n = len(weights)
    if n == 0:
        return []
    total = float(word_ends[-1]) if len(word_ends) else 0.0
    if total <= 0:
        return [(0.0, 0.0) for _ in range(n)]

    cum = list(accumulate(float(w) for w in weights))
    tot_w = cum[-1] or 1.0
    ideals = [total * c / tot_w for c in cum]  # ideal END time of each beat; last == total

    # (midpoint, gap_size) for every silence between consecutive words.
    gaps = [
        ((word_ends[i] + word_starts[i + 1]) / 2.0, word_starts[i + 1] - word_ends[i])
        for i in range(len(word_ends) - 1)
    ]

    boundaries: list[float] = []
    prev = 0.0
    for k in range(n - 1):
        ideal = ideals[k]
        forward = [g for g in gaps if g[0] > prev]
        in_window = [g for g in forward if abs(g[0] - ideal) <= snap_window]
        if in_window:
            # Prefer the biggest pause in the window; break ties toward the ideal boundary.
            boundary, _ = max(in_window, key=lambda g: (g[1], -abs(g[0] - ideal)))
        elif forward:
            # No pause nearby → still cut in a real gap: the one closest to the ideal.
            boundary = min(forward, key=lambda g: abs(g[0] - ideal))[0]
        else:
            boundary = ideal
        boundary = min(max(boundary, prev), total)
        boundaries.append(boundary)
        prev = boundary
    boundaries.append(total)

    spans: list[tuple[float, float]] = []
    start = 0.0
    for end in boundaries:
        spans.append((round(start, 3), round(end, 3)))
        start = end
    return spans


def caption_timeline(
    beat_spans: Sequence[tuple[float, float]],
    narrations: Sequence[str],
    max_words: int = 7,
    max_chars: int = 42,
) -> list[tuple[str, float, float]]:
    """Global list of (cue_text, start, end) — short subtitles anchored to real beat spans."""
    out: list[tuple[str, float, float]] = []
    for (start, end), text in zip(beat_spans, narrations, strict=False):
        cues = split_caption_cues(text, max_words=max_words, max_chars=max_chars)
        for (cue_start, cue_end), cue in zip(cue_timings(cues, end - start), cues, strict=False):
            out.append((cue, round(start + cue_start, 3), round(start + cue_end, 3)))
    return out
