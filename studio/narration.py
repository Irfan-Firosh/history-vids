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

import re
from collections.abc import Sequence
from itertools import accumulate

from studio.captions import cue_timings, split_caption_cues

#: Every on-screen frame holds at least this long (calm, Axen-style pacing). A beat long enough for
#: two or more holds is split into that many DISTINCT freshly-generated frames.
MIN_FRAME_HOLD = 8.0  # seconds


MAX_FRAMES_PER_BEAT = 4  # hard cap so an intense/long beat can't balloon render cost

#: Callouts must feel rare — the user wants only ~2-3 flashed facts per 90s. We enforce a minimum
#: spacing between consecutive callouts at render time (a hard guardrail regardless of how many the
#: analysis pass proposes): ~35s apart ⇒ at most ~2-3 in any 90-second window.
CALLOUT_MIN_GAP_SEC = 35.0


def frames_for_span(
    dur: float, min_hold: float = MIN_FRAME_HOLD, intense: bool = False,
    cap: int = MAX_FRAMES_PER_BEAT,
) -> int:
    """How many frames a beat of length `dur` shows — each held ≥ `min_hold` (at least one). A
    high-intensity beat gets ONE extra frame for more visual punch. Always capped at `cap`."""
    base = max(1, int(dur // min_hold))
    return min(cap, base + (1 if intense else 0))


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


_NORM = re.compile(r"[^a-z0-9]+")


def _norm_len(text: str) -> int:
    """Length of `text` with everything but letters/digits stripped and lowercased — a stable
    per-token size that survives punctuation and casing (used to match beats to spoken words)."""
    return len(_NORM.sub("", text.lower()))


def align_beats_to_words(
    narrations: Sequence[str],
    words: Sequence[str],
    word_starts: Sequence[float],
    word_ends: Sequence[float],
) -> list[tuple[float, float]]:
    """Map ordered beats onto the audio by ANCHORING each beat's end to the REAL spoken word where
    its narration text runs out — the accurate replacement for the proportional ``align_beats``.

    Cartesia returns the actual spoken ``words`` with per-word ``start``/``end`` times. Because the
    transcript is exactly the beats joined in order, we walk that spoken-word stream and hand words
    to each beat until the beat's normalised character budget is spent, snapping to whichever word
    end lands the beat length closest to its text — so every cut falls on the true word boundary
    instead of a character-proportion estimate that drifts several seconds mid-video. Robust to how
    TTS pronounces numbers/abbreviations (a few over/under-counted characters shift the cut by at
    most a word, and never accumulate because each beat re-anchors from the current pointer). Falls
    back to the proportional ``align_beats`` when no word text is available. Returns contiguous,
    monotonic (start, end) spans over ``[0, total]`` (``total`` = last word end)."""
    n = len(narrations)
    if n == 0:
        return []
    total = float(word_ends[-1]) if len(word_ends) else 0.0
    if not words or total <= 0:
        return align_beats([max(_norm_len(x), 1) for x in narrations], word_starts, word_ends)

    wlen = [_norm_len(w) for w in words]
    nwords = len(words)
    spans: list[tuple[float, float]] = []
    wi = 0
    start = 0.0
    for bi, narr in enumerate(narrations):
        if bi == n - 1:  # last beat always runs to the end of the audio
            end = total
            wi = nwords
        else:
            target = max(_norm_len(narr), 1)
            got = 0
            # Leave at least one spoken word for each remaining beat so none starve on a mismatch.
            limit = nwords - (n - 1 - bi)
            end = word_ends[wi] if wi < nwords else total
            while wi < limit:
                nxt = got + wlen[wi]
                # Stop once including this word would overshoot the beat's text more than stopping
                # short of it undershoots — i.e. snap to the word end closest to the true length.
                if nxt >= target and got > 0 and (nxt - target) > (target - got):
                    end = word_ends[wi - 1]
                    break
                got = nxt
                end = word_ends[wi]
                wi += 1
                if got >= target:
                    break
        end = min(max(end, start), total)  # clamp monotonic + within the audio
        spans.append((round(start, 3), round(end, 3)))
        start = end
    return spans


def word_spans_for_texts(
    texts: Sequence[str],
    words: Sequence[str],
    word_starts: Sequence[float],
    word_ends: Sequence[float],
) -> list[tuple[int, int]]:
    """Map ordered `texts` onto the spoken-word stream, returning an inclusive (first, last) word
    index per text.

    Allocation is by cumulative character share, then snapped to a word boundary — the same idea as
    ``align_beats_to_words`` but at cue granularity. Anchoring in WORD-INDEX space rather than time
    space is what makes this robust to uneven speaking rate: a cue that takes four seconds to say
    gets four seconds of subtitle, not its proportional share of the beat.

    Every text gets at least one word, spans are contiguous and monotonic, and the last text always
    consumes the remaining stream, so cues never gap or overlap.
    """
    n_words = len(word_starts)
    if not texts or n_words == 0:
        return []
    lengths = [max(len(" ".join(t.split())), 1) for t in texts]
    total = sum(lengths)
    spans: list[tuple[int, int]] = []
    cursor = 0
    running = 0
    for i, length in enumerate(lengths):
        running += length
        remaining_texts = len(texts) - i - 1
        if i == len(texts) - 1:
            end = n_words - 1
        else:
            target = round(running / total * n_words) - 1
            # Leave at least one word for every text still to come, and never move backwards.
            end = min(max(target, cursor), n_words - 1 - remaining_texts)
        spans.append((cursor, end))
        cursor = end + 1
    return spans


def caption_timeline(
    beat_spans: Sequence[tuple[float, float]],
    narrations: Sequence[str],
    max_words: int = 7,
    max_chars: int = 42,
    *,
    words: Sequence[str] = (),
    word_starts: Sequence[float] = (),
    word_ends: Sequence[float] = (),
) -> list[tuple[str, float, float]]:
    """Global list of (cue_text, start, end).

    With word timings, cues are anchored to the words actually spoken — the cue list concatenated
    in order IS the transcript, so the whole script maps onto the word stream in one pass. Without
    them (the offline ``say`` voice) it degrades to spreading each beat's duration across its cues
    by length, which drifts within a beat but is the best available.
    """
    if word_starts and word_ends:
        all_cues: list[str] = []
        for text in narrations:
            all_cues.extend(split_caption_cues(text, max_words=max_words, max_chars=max_chars))
        spans = word_spans_for_texts(all_cues, words or all_cues, word_starts, word_ends)
        return [
            (cue, round(float(word_starts[a]), 3), round(float(word_ends[b]), 3))
            for cue, (a, b) in zip(all_cues, spans, strict=False)
        ]
    out: list[tuple[str, float, float]] = []
    for (start, end), text in zip(beat_spans, narrations, strict=False):
        cues = split_caption_cues(text, max_words=max_words, max_chars=max_chars)
        for (cue_start, cue_end), cue in zip(cue_timings(cues, end - start), cues, strict=False):
            out.append((cue, round(start + cue_start, 3), round(start + cue_end, 3)))
    return out


def emphasis_timeline(
    beat_spans: Sequence[tuple[float, float]],
    emphases: Sequence[str],
    narrations: Sequence[str] = (),
    min_gap_sec: float = CALLOUT_MIN_GAP_SEC,
    lead_sec: float = 0.3,
    min_hold_sec: float = 2.0,
) -> list[tuple[str, int, float, float]]:
    """Global list of (fact_text, beat_index, start, end) key-fact callouts — one per beat whose
    ``emphasis`` is non-empty — timed so each callout appears WHEN its phrase is spoken.

    Cartesia gives per-beat spans but not per-word times, so (like ``align_beats`` and the caption
    timing) we ESTIMATE the phrase's spoken moment from its character offset within the beat's
    narration, then pull it ``lead_sec`` earlier so it lands **on or before** the word. ``start`` is
    clamped so the callout stays up at least ``min_hold_sec`` (readability) and never precedes its
    beat; it holds until the beat ends. A minimum spacing of ``min_gap_sec`` between consecutive
    callouts is enforced greedily so flashed facts stay rare (~2-3 per 90s) even when the analysis
    pass over-proposes. ``beat_index`` lets the renderer find the beat's image (for placement).
    """
    out: list[tuple[str, int, float, float]] = []
    last_kept = float("-inf")
    for i, ((bstart, bend), text) in enumerate(zip(beat_spans, emphases, strict=False)):
        fact = (text or "").strip()
        if not fact:
            continue
        narr = narrations[i] if i < len(narrations) else ""
        dur = bend - bstart
        # Estimate when the phrase is spoken: its character position in the beat, scaled to the
        # beat duration (speech ≈ uniform per beat), minus a small lead so it shows before the word.
        pos = narr.lower().find(fact.lower()) if narr else -1
        if pos >= 0 and dur > 0:
            start = bstart + (pos / len(narr)) * dur - lead_sec
        else:  # phrase not located → show from the start of the beat (still "before" the word)
            start = bstart
        hold = min(min_hold_sec, dur)  # keep it on screen long enough (don't invert a short beat)
        start = max(bstart, min(start, bend - hold))
        if start - last_kept >= min_gap_sec:
            out.append((fact, i, round(start, 3), round(bend, 3)))
            last_kept = start
    return out


def image_timeline(
    beat_spans: Sequence[tuple[float, float]],
    frames_per_beat: Sequence[int],
) -> list[tuple[str, float, float]]:
    """The on-screen image schedule as (image_filename, start, end), by the file-name convention.

    Each beat span is split into ``frames_per_beat[i]`` equal, contiguous holds. The first frame is
    ``img_{i}.png``; extra frames are ``img_{i}_{k}.png`` (k = 1, 2, …) — each a DISTINCT image, so
    adjacent segments are never the same file (no cut-back). Callers size the count so every hold is
    ≥ :data:`MIN_FRAME_HOLD` (fresh render → ``frames_for_span``; re-edit → frames already on disk).
    """
    segs: list[tuple[str, float, float]] = []
    for i, ((start, end), nframes) in enumerate(zip(beat_spans, frames_per_beat, strict=False)):
        n = max(1, int(nframes))
        step = (end - start) / n
        for k in range(n):
            seg_start = start if k == 0 else round(start + k * step, 3)
            seg_end = end if k == n - 1 else round(start + (k + 1) * step, 3)
            name = f"img_{i}.png" if k == 0 else f"img_{i}_{k}.png"
            segs.append((name, seg_start, seg_end))
    return segs
