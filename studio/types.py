"""Studio value objects + provider Protocols (frozen/immutable, mirrors core.shorts.types)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

#: Shot variety (like Axen — not every frame is the character). Drives whether reference images
#: of the recurring character are passed to the image provider.
SHOT_TYPES: tuple[str, ...] = ("character", "wide", "concept", "map")
_CHARACTER_SHOTS = frozenset({"character", "wide"})


def shot_uses_character(shot_type: str) -> bool:
    """True when the shot shows the recurring character → pass REF-1/REF-2 for consistency.

    ``concept`` (props/symbols) and ``map`` shots return False so the model isn't pushed to draw a
    person where there shouldn't be one.
    """
    return shot_type in _CHARACTER_SHOTS


class Scene(BaseModel):
    """One beat of the video: a line of narration + the image to show under it."""

    model_config = ConfigDict(frozen=True)

    narration: str
    image_prompt: str  # the subject; the locked style is appended at render time
    motion: str = "static"  # "static" hard-cut (default) or a studio.kenburns.MOTIONS camera move
    shot_type: Literal["character", "wide", "concept", "map"] = "character"  # ref conditioning
    cite: tuple[int, ...] = ()  # research-brief [n] indices backing this beat (for the QC gate)
    emphasis: str = ""  # optional short key fact ("1905") shown as an on-image callout overlay
    intense: bool = False  # dramatic/vivid beat → gets an extra distinct frame at render
    duration_sec: float | None = None  # filled from the narration audio length at render


class Storyboard(BaseModel):
    """A full video: title + ordered scenes + the locked visual style for consistency."""

    model_config = ConfigDict(frozen=True)

    title: str
    style: str
    scenes: tuple[Scene, ...]

    @property
    def total_narration_chars(self) -> int:
        return sum(len(s.narration) for s in self.scenes)


# ── Provider Protocols (concrete impls in tools/studio_poc.py) ───────────────────


@runtime_checkable
class ImageProvider(Protocol):
    """Render an image for a (styled) prompt to `out_path`. PlaceholderProvider → Gemini.

    `refs` are optional reference images (REF-1 character sheet, REF-2 expressions) used by
    providers that support conditioning (Gemini) to keep the character on-model; others ignore them.
    """

    name: str

    def generate(self, prompt: str, out_path: Path, refs: Sequence[Path] = ()) -> Path: ...


@runtime_checkable
class VoiceProvider(Protocol):
    """Synthesize `text` to a wav at `out_path`; return its duration in seconds. Say → Cartesia."""

    name: str

    def synthesize(self, text: str, out_path: Path) -> float: ...
