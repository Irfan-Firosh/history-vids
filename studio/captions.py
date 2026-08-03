"""Caption cue splitting + timing (pure) — short readable subtitles instead of a wall of text.

Cartesia DOES return per-word timestamps (``CartesiaTimestampVoice``, ``add_timestamps``), and
``narration.caption_timeline`` anchors cues to them. This module only decides WHERE to split; the
proportional ``cue_timings`` below is the fallback for voices with no word data (offline ``say``).
The renderer shows each cue as a timed PNG overlay (this ffmpeg build lacks drawtext/libass), so
subtitles change every couple seconds.
"""

from __future__ import annotations

_SENTENCE_END = (".", "!", "?")


def split_caption_cues(text: str, max_words: int = 7, max_chars: int = 42) -> list[str]:
    """Split narration into short caption cues (≤ max_words / ≤ max_chars), breaking at sentences.

    Greedy: bank words until the next would overflow, or a sentence ends with ≥3 words accumulated.
    """
    words = text.split()
    if not words:
        return []
    cues: list[str] = []
    current: list[str] = []
    for word in words:
        current.append(word)
        joined = " ".join(current)
        ends_sentence = word.rstrip("\"'”’)").endswith(_SENTENCE_END)
        overflow = len(current) >= max_words or len(joined) >= max_chars
        if overflow or (ends_sentence and len(current) >= 3):
            cues.append(joined)
            current = []
    if current:
        cues.append(" ".join(current))
    return cues


def cue_timings(cues: list[str], total_duration: float) -> list[tuple[float, float]]:
    """Spread `total_duration` across cues, weighted by length (longer cue → more screen time).

    Returns contiguous (start, end) spans covering [0, total_duration]; the last ends exactly at it.
    """
    if not cues or total_duration <= 0:
        return []
    weights = [max(len(c), 1) for c in cues]
    total = sum(weights)
    spans: list[tuple[float, float]] = []
    t = 0.0
    for i, w in enumerate(weights):
        end = total_duration if i == len(cues) - 1 else t + total_duration * w / total
        spans.append((round(t, 3), round(end, 3)))
        t = end
    return spans
