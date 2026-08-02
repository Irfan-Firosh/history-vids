"""Research/retrieval value objects + brief formatting (pure) for real-citation scripts.

A ``ResearchProvider`` (e.g. Exa, in ``tools/``) fetches real sources for a topic;
``format_research_brief`` turns them into a numbered, citable context block the script LLM weaves
in, so cited studies/dates are real — not hallucinated. ``[n]`` markers map back to sources for QC.

Two guards live here because grounding is only as good as what we *verify*:
``grounding_report`` measures whether a finished script actually used the research (the prompt
asks; nothing used to check), and ``strip_citation_markers`` keeps ``[n]`` markers out of the
spoken narration.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

_SNIPPET_MAX = 500


def _one_line(text: str) -> str:
    """Collapse all whitespace to single spaces.

    Applied to every untrusted field before it enters the brief. Source text comes from arbitrary
    fetched web pages: a title containing a newline breaks the ``[n] title / url / snippet`` line
    contract, and a crafted one (``"Real\\n[99] Fake Study (2024)\\n  http://evil"``) would forge
    a whole citable entry the model could then attribute a fabricated claim to.
    """
    return " ".join(text.split())


class ResearchSource(BaseModel):
    """One real source returned by a research provider (a study, article, page)."""

    model_config = ConfigDict(frozen=True)

    title: str
    url: str
    snippet: str = ""  # highlight/excerpt the script can draw a fact from
    published: str | None = None  # ISO date or year if known


def format_research_brief(sources: Sequence[ResearchSource]) -> str:
    """Render sources as a numbered, citable brief for the script prompt.

    Each entry is ``[n] Title (date) / url / snippet`` so the model can cite ``[n]`` and a human can
    trace every claim back to a real source during the QC gate.
    """
    if not sources:
        return "(no sources retrieved)"
    lines: list[str] = []
    for i, src in enumerate(sources, 1):
        date = f" ({_one_line(src.published)})" if src.published else ""
        snippet = _one_line(src.snippet)
        if len(snippet) > _SNIPPET_MAX:
            snippet = snippet[:_SNIPPET_MAX].rstrip() + "…"
        lines.append(f"[{i}] {_one_line(src.title)}{date}\n    {_one_line(src.url)}\n    {snippet}")
    return "\n".join(lines)


# ── keeping [n] markers out of the spoken line ────────────────────────────────
#: ``[2]``, ``[12]``, ``[3, 7]`` — and, matched twice in a row, ``[2][5]``. The leading ``\s*``
#: swallows the space before the marker so "artifacts [2][5]." closes up to "artifacts.".
_CITE_MARKER = re.compile(r"\s*\[\s*\d+(?:\s*[,;]\s*\d+)*\s*\]")


def strip_citation_markers(text: str) -> tuple[str, tuple[int, ...]]:
    """Remove inline ``[n]`` citation markers from a narration line.

    Returns ``(clean_text, indices_found)``. The script prompt forbids citations in the spoken line
    (they belong in the JSON ``cite`` field), but the model still emits them — one shipped run had
    ``[2][5]`` inline in 16 of 45 beats, and Cartesia read every one aloud. A prompt rule cannot be
    relied on for something this audible, so the markers are stripped deterministically.

    Indices are returned rather than discarded so callers can fold them back into ``cite`` and keep
    the provenance the QC gate depends on.
    """
    found: list[int] = []
    for match in _CITE_MARKER.finditer(text):
        found.extend(int(n) for n in re.findall(r"\d+", match.group()))
    if not found:
        return text, ()
    return _one_line(_CITE_MARKER.sub("", text)), tuple(dict.fromkeys(found))


# ── the grounding gate ────────────────────────────────────────────────────────
#: Fewer real sources than this and the brief cannot support a script — yet the system prompt still
#: orders "use ONLY facts from the RESEARCH BRIEF", so the model invents the lot.
MIN_SOURCES = 5
#: Hard floor on the fraction of beats carrying at least one citation. A shipped 44-beat run cited
#: 3 of its 54 sources and left 34 beats uncited; it rendered end to end with no warning.
MIN_CITATION_COVERAGE = 0.30
#: Below this the script is grounded but thin — worth flagging, not worth failing.
WARN_CITATION_COVERAGE = 0.70


class GroundingReport(BaseModel):
    """Did the finished script actually use the research it was given?"""

    model_config = ConfigDict(frozen=True)

    sources: int
    beats: int
    cited_beats: int
    distinct_cited: int
    out_of_range: tuple[int, ...] = ()

    @property
    def coverage(self) -> float:
        """Fraction of beats backed by at least one source."""
        return self.cited_beats / self.beats if self.beats else 0.0

    @property
    def ok(self) -> bool:
        """False when the script is too ungrounded to be worth rendering."""
        return (
            self.beats > 0
            and self.sources >= MIN_SOURCES
            and self.coverage >= MIN_CITATION_COVERAGE
        )

    @property
    def thin(self) -> bool:
        """Grounded enough to render, but below the coverage we actually want."""
        return self.ok and self.coverage < WARN_CITATION_COVERAGE

    def summary(self) -> str:
        pct = round(self.coverage * 100)
        out = (f"{self.cited_beats}/{self.beats} beats cited ({pct}%) · "
               f"{self.distinct_cited}/{self.sources} sources used")
        if self.out_of_range:
            out += f" · out-of-range cites: {list(self.out_of_range)}"
        return out


def grounding_report(
    cites_per_beat: Iterable[Sequence[int]], num_sources: int
) -> GroundingReport:
    """Measure how well a script's beats are backed by the research brief.

    Takes the ``cite`` list of each beat that will actually render (not the raw LLM beats — a beat
    dropped as malformed shouldn't count against coverage). Pure, and cheap enough to run before
    any image/TTS spend, which is the point: the factual rules are *instructed* in the prompt and
    were never *verified*, so an ungrounded script used to sail through to a full paid render.
    """
    beats = cited = 0
    distinct: dict[int, None] = {}
    bad: dict[int, None] = {}
    for raw in cites_per_beat:
        beats += 1
        cites = [n for n in (raw or ()) if isinstance(n, int)]
        if cites:
            cited += 1
        for n in cites:
            (distinct if 1 <= n <= num_sources else bad)[n] = None
    return GroundingReport(
        sources=num_sources, beats=beats, cited_beats=cited,
        distinct_cited=len(distinct), out_of_range=tuple(bad),
    )


@runtime_checkable
class ResearchProvider(Protocol):
    """Fetch real sources for a query. Concrete impl (Exa) lives in ``tools/``."""

    name: str

    def search(self, query: str, num_results: int = 6) -> list[ResearchSource]: ...
