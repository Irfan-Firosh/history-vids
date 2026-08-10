"""Assign a camera framing to every shot, guaranteeing variety by construction.

The measured failure this exists to fix: across one 60-image run, mean pairwise layout similarity
was 0.879 and 57% of frames put their subject mass in the same horizontal band
(``context/research/2026-08-09/01-render-quality-gap.md`` §3). Nothing in the pipeline varied the
camera, because nothing in the pipeline had an opinion about the camera at all.

A prompt rule would not fix it. "Vary your framing" is exactly the kind of instruction that reads
well and is quietly ignored, and its violation is only visible after paying for every image in the
run. So framing is assigned here, deterministically, and the prompt receives an explicit directive
per shot rather than a request for variety.

The planner takes whatever framing the script LLM asked for and honours it when it is legal and
would not extend a run of identical framings past ``MAX_RUN``. Otherwise it substitutes the
legal framing used least recently. Same inputs always give the same plan — no RNG, so a re-run
reproduces the storyboard exactly and the segment cache stays valid.
"""

from __future__ import annotations

from collections.abc import Sequence

from studio.style import FRAMINGS

#: Longest run of the same framing before the planner forces a change. Two is deliberate: three
#: identical framings in a row is the pattern that reads as monotony on screen.
MAX_RUN = 2

#: Framings that require a person, so they can never land on a `concept`/`map` shot (which carry an
#: explicit "absolutely NO people" instruction — pairing the two would send a self-contradicting
#: prompt).
_NEEDS_PERSON = frozenset({"close_up", "medium", "over_shoulder", "profile"})

#: Preference order within each shot family. First entry is the natural default for that family;
#: the rest are the variety pool, ordered so consecutive picks look different from each other.
_CHARACTER_ORDER = ("medium", "profile", "close_up", "wide", "over_shoulder", "cutaway")
_CONCEPT_ORDER = ("detail", "wide", "cutaway")


def legal_framings(shot_type: str) -> tuple[str, ...]:
    """Framings that make sense for `shot_type`, in preference order."""
    if shot_type in ("concept", "map"):
        return _CONCEPT_ORDER
    return _CHARACTER_ORDER


def plan_framings(
    shot_types: Sequence[str],
    requested: Sequence[str] = (),
    *,
    max_run: int = MAX_RUN,
) -> list[str]:
    """One framing per shot, honouring `requested` where legal and varied.

    `requested` is what the script LLM asked for, positionally aligned with `shot_types`; it may be
    shorter, empty, or contain names that are not framings — all of those degrade to "no request"
    for that shot rather than raising, because a storyboard is model output and a single bad token
    should not fail a whole run.
    """
    out: list[str] = []
    last_used: dict[str, int] = {}
    for i, shot_type in enumerate(shot_types):
        legal = legal_framings(shot_type)
        want = requested[i] if i < len(requested) else ""
        want = want if want in legal else ""

        run = _trailing_run(out)
        if want and not (run and run[0] == want and run[1] >= max_run):
            pick = want
        else:
            pick = _least_recently_used(legal, last_used, avoid=run[0] if run else None,
                                        at_limit=bool(run and run[1] >= max_run))
        out.append(pick)
        last_used[pick] = i
    return out


def _trailing_run(chosen: Sequence[str]) -> tuple[str, int] | None:
    """The framing at the end of `chosen` and how many times it repeats there."""
    if not chosen:
        return None
    last = chosen[-1]
    n = 0
    for x in reversed(chosen):
        if x != last:
            break
        n += 1
    return last, n


def _least_recently_used(
    legal: Sequence[str], last_used: dict[str, int], *, avoid: str | None, at_limit: bool
) -> str:
    """The legal framing seen longest ago, skipping `avoid` once the run is at its limit."""
    pool = [f for f in legal if not (at_limit and f == avoid)] or list(legal)
    return min(pool, key=lambda f: (last_used.get(f, -1), legal.index(f)))


def framing_directive(name: str) -> str:
    """The prompt sentence for a framing. Unknown names fall back to `medium`."""
    return FRAMINGS.get(name, FRAMINGS["medium"])


def variation_framing(base: str, shot_type: str, k: int) -> str:
    """The framing for extra frame `k` of one beat — a NAMED different shot of the same scene.

    A beat long enough to hold two images shows two distinct generations, and the switch between
    them should read as a real cut. Asking the model for "a clearly different composition" left it
    to guess; naming a specific different framing does not. `k == 0` is always the beat's own
    framing.
    """
    if k <= 0:
        return base
    others = [f for f in legal_framings(shot_type) if f != base]
    return others[(k - 1) % len(others)] if others else base
