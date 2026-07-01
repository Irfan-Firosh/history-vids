"""Research/retrieval value objects + brief formatting (pure) for real-citation scripts.

A ``ResearchProvider`` (e.g. Exa, in ``tools/``) fetches real sources for a topic;
``format_research_brief`` turns them into a numbered, citable context block the script LLM weaves
in, so cited studies/dates are real — not hallucinated. ``[n]`` markers map back to sources for QC.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict

_SNIPPET_MAX = 500


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
        date = f" ({src.published})" if src.published else ""
        snippet = " ".join(src.snippet.split())
        if len(snippet) > _SNIPPET_MAX:
            snippet = snippet[:_SNIPPET_MAX].rstrip() + "…"
        lines.append(f"[{i}] {src.title}{date}\n    {src.url}\n    {snippet}")
    return "\n".join(lines)


@runtime_checkable
class ResearchProvider(Protocol):
    """Fetch real sources for a query. Concrete impl (Exa) lives in ``tools/``."""

    name: str

    def search(self, query: str, num_results: int = 6) -> list[ResearchSource]: ...
