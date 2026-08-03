"""Plan the on-screen shot schedule (pure).

The measured reference cuts every ~2.2s (p10 0.9 / p90 4.6) at 16-18 cuts/min, landing on CLAUSE
boundaries at roughly 9-11 narration words per image — not on a timer. The previous approach held
one image for a whole beat (MIN_FRAME_HOLD 8.0s), giving 52 shots where the reference has ~218.

There is no motion of any kind in the reference: 0% camera moves, 0% character animation, 0%
dissolves across 27,723 measured frame pairs. A Shot is therefore a still held for a span — the
grammar is correct, only the rate was wrong.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from studio.types import Scene

#: Narration words per image. Reference: 9-11 (Axen 6.8-11 depending on section).
WORDS_PER_SHOT = 10
#: Reference p10. Below this a cut reads as a flicker.
MIN_SHOT_SEC = 0.9
#: Reference never exceeds ~8.5s on a single held frame.
MAX_SHOT_SEC = 8.5

#: Clause boundaries, strongest first. A comma is a weaker break than a full stop but still reads
#: as a natural cut point, which is what the reference cuts on.
_CLAUSE_END = re.compile(r'(?<=[.!?;:,])["\'”’)\]]*\s+')


class Shot(BaseModel):
    """One held still and the span it occupies."""

    model_config = ConfigDict(frozen=True)

    beat_index: int
    sub_index: int
    start: float
    end: float
    image_key: str
    shot_type: str = "character"

    @property
    def duration(self) -> float:
        return self.end - self.start


def split_clauses(text: str, words_per_shot: int = WORDS_PER_SHOT) -> list[str]:
    """Split narration into ~`words_per_shot`-word chunks, preferring clause boundaries.

    Greedy: accumulate clauses until adding the next would overshoot the budget, then cut. A clause
    longer than the budget on its own is hard-split by word count instead of being held as one long
    shot — otherwise a run of narration with no internal punctuation (nothing for the clause regex
    to break on) would degrade to a single multi-second hold, exactly the bug this task removes.
    """
    pieces = [p for p in (s.strip() for s in _CLAUSE_END.split(text)) if p]
    if not pieces:
        return [text.strip()] if text.strip() else []
    out: list[str] = []
    current: list[str] = []
    count = 0
    for piece in pieces:
        words = piece.split()
        n = len(words)
        if current and count + n > words_per_shot:
            out.append(" ".join(current))
            current, count = [], 0
        if n > words_per_shot:
            for start in range(0, n, words_per_shot):
                out.append(" ".join(words[start : start + words_per_shot]))
            continue
        current.append(piece)
        count += n
    if current:
        out.append(" ".join(current))
    return out


def plan_shots(
    beat_spans: Sequence[tuple[float, float]],
    scenes: Sequence[Scene],
    *,
    words: Sequence[str] = (),
    word_starts: Sequence[float] = (),
    word_ends: Sequence[float] = (),
    words_per_shot: int = WORDS_PER_SHOT,
) -> list[Shot]:
    """Split each beat into clause-aligned shots covering its span exactly.

    With word timings the shot boundaries land on real spoken word ends. Without them (offline
    ``say``) the beat's span is divided proportionally by clause length — the same degradation
    ``caption_timeline`` makes, and recorded on the manifest so it is never silent.

    Spans are contiguous and monotonic across the whole video, every shot gets a distinct
    ``image_key``, and no shot is shorter than ``MIN_SHOT_SEC`` (over-eager splits are merged back).
    """
    shots: list[Shot] = []
    for i, ((start, end), scene) in enumerate(zip(beat_spans, scenes, strict=False)):
        chunks = split_clauses(scene.narration, words_per_shot) or [scene.narration]
        span = end - start
        # Merge chunks that would render shorter than the reference p10.
        while len(chunks) > 1 and span / len(chunks) < MIN_SHOT_SEC:
            chunks = [" ".join(chunks[i : i + 2]) for i in range(0, len(chunks), 2)]
        weights = [max(len(c.split()), 1) for c in chunks]
        total = sum(weights)
        cursor = start
        for k, weight in enumerate(weights):
            shot_end = end if k == len(weights) - 1 else round(cursor + span * weight / total, 3)
            shots.append(
                Shot(
                    beat_index=i,
                    sub_index=k,
                    start=round(cursor, 3),
                    end=shot_end,
                    image_key=f"img_{i}.png" if k == 0 else f"img_{i}_{k}.png",
                    shot_type=scene.shot_type,
                )
            )
            cursor = shot_end
    return shots
