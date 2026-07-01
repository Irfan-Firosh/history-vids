#!/usr/bin/env python3
"""Generate a real-citation, Axen-structured storyboard from a topic (Phase 1 script stage).

topic → [LLM: search queries] → [Exa: real sources] → research brief → [gpt-oss:120b writes a calm,
philosophical script with an engaging title, citing [n]] → validated Storyboard JSON + a QC report
(every scene ↔ its sources). Output feeds tools/studio_poc.py via --storyboard.

Run:  python tools/make_script.py "What Did Ancient Humans Do All Day?" --scenes 8
Needs: LLM_API_BASE_URL + LLM_API_KEY + LLM_SCRIPT_MODEL, EXA_API_KEY in .env.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

from studio import format_research_brief, llm, storyboard_from_dict  # noqa: E402
from studio.research import ResearchSource  # noqa: E402
from studio.script_prompt import (  # noqa: E402
    CALLOUT_ANALYSIS_SYSTEM_PROMPT,
    QUERY_SYSTEM_PROMPT,
    SCRIPT_SYSTEM_PROMPT,
    build_callout_analysis_user_prompt,
    build_query_user_prompt,
    build_script_user_prompt,
)

OUT_DIR = _ROOT / "result/axen/scripts"
EXA_SEARCH_URL = "https://api.exa.ai/search"

#: The user wants ~1.5x more "fire spots" (intense beats — each shows two distinct frames, so the
#: image switches mid-beat) than the analysis pass picks on its own. After the LLM flags the real
#: dramatic peaks, we deterministically top up to this multiple by promoting the longest-narration
#: beats (the most spoken time → the most natural place for a second on-screen image).
INTENSE_MULTIPLIER = 1.5
#: Never let more than this fraction of beats be fire spots (keeps the extra cuts a punctuation, and
#: caps render cost — an intense beat draws an extra frame).
INTENSE_MAX_FRACTION = 0.5


def _boost_intense_beats(
    scenes: list[dict], multiplier: float = INTENSE_MULTIPLIER,
    max_fraction: float = INTENSE_MAX_FRACTION,
) -> None:
    """Promote extra beats to ``intense`` so there are ~``multiplier``x as many fire spots as the
    analysis pass flagged (mutates ``scenes`` in place). Extra beats are the longest-narration ones
    not already flagged; the total is capped at ``max_fraction`` of all beats. A no-op when nothing
    was flagged (0 * 1.5 = 0) or the target is already met."""
    flagged = [i for i, s in enumerate(scenes) if s.get("intense")]
    want = round(len(flagged) * multiplier)
    want = min(want, int(len(scenes) * max_fraction))
    need = want - len(flagged)
    if need <= 0:
        return
    candidates = sorted(
        (i for i in range(len(scenes)) if not scenes[i].get("intense")),
        key=lambda i: len(scenes[i].get("narration", "")),
        reverse=True,
    )
    for i in candidates[:need]:
        scenes[i]["intense"] = True


class ExaResearchProvider:
    """Real web sources via the Exa search API. Needs EXA_API_KEY."""

    name = "exa"

    def __init__(self, key: str | None = None, max_chars: int = 1000) -> None:
        self.key = key or os.environ.get("EXA_API_KEY")
        self.max_chars = max_chars

    def search(self, query: str, num_results: int = 6) -> list[ResearchSource]:
        import httpx

        if not self.key:
            raise RuntimeError("Set EXA_API_KEY in .env to use Exa research.")
        resp = httpx.post(
            EXA_SEARCH_URL,
            headers={"x-api-key": self.key, "Content-Type": "application/json"},
            json={
                "query": query,
                "numResults": num_results,
                "contents": {"highlights": True, "text": {"maxCharacters": self.max_chars}},
            },
            timeout=60,
        )
        resp.raise_for_status()
        sources: list[ResearchSource] = []
        for r in resp.json().get("results", []):
            highlights = r.get("highlights") or []
            snippet = " ".join(highlights) if highlights else (r.get("text") or "")
            sources.append(
                ResearchSource(
                    title=r.get("title") or "(untitled)",
                    url=r.get("url") or "",
                    snippet=snippet,
                    published=r.get("publishedDate"),
                )
            )
        return sources


class LLMScriptProvider:
    """Topic → grounded Storyboard via the local OpenAI-compatible endpoint (gpt-oss:120b)."""

    name = "llm-script"

    def __init__(self, research, base_url=None, key=None, model=None, temperature=0.7) -> None:
        self.research = research
        self.base_url = base_url or os.environ.get("LLM_API_BASE_URL", "")
        self.key = key or os.environ.get("LLM_API_KEY")
        self.model = model or os.environ.get("LLM_SCRIPT_MODEL", "gpt-oss:120b")
        self.temperature = temperature

    def _chat(self, system: str, user: str, temperature: float | None = None) -> str:
        import time

        import httpx

        if not self.base_url or not self.key:
            raise RuntimeError("Set LLM_API_BASE_URL + LLM_API_KEY in .env to use the script LLM.")
        body = llm.build_chat_request(
            self.model, system, user,
            temperature=self.temperature if temperature is None else temperature,
        )
        # A big local model (gpt-oss:120b) can be slow/flaky under load; retry transient network /
        # read-timeout errors with backoff so one hiccup doesn't fail a whole run (image providers
        # already do this — see tasks/lessons.md).
        attempts = 3
        for attempt in range(attempts):
            try:
                resp = httpx.post(
                    llm.chat_endpoint(self.base_url),
                    headers={
                        "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"
                    },
                    json=body,
                    timeout=300,
                )
                resp.raise_for_status()
                return llm.extract_message(resp.json())
            except (httpx.TimeoutException, httpx.TransportError) as err:
                if attempt == attempts - 1:
                    raise
                wait = 3 * (attempt + 1)
                print(f"  script LLM {type(err).__name__} (attempt {attempt + 1}/{attempts}); "
                      f"retrying in {wait}s…", file=sys.stderr)
                time.sleep(wait)
        raise RuntimeError("unreachable")  # loop either returns or raises

    def gather_sources(self, topic: str, num_queries: int = 6, per_query: int = 8):
        text = self._chat(QUERY_SYSTEM_PROMPT, build_query_user_prompt(topic, num_queries), 0.3)
        queries = llm.parse_json_block(text).get("queries", [])[:num_queries]
        seen: set[str] = set()
        sources: list[ResearchSource] = []
        for q in queries:
            for src in self.research.search(q, per_query):
                if src.url and src.url not in seen:
                    seen.add(src.url)
                    sources.append(src)
        return queries, sources

    def generate(
        self, topic: str, num_scenes: int = 45, min_minutes: float = 6.0, max_minutes: float = 9.0
    ):
        # A longer video needs more real facts — scale research depth with the beat count.
        num_queries = min(12, max(6, num_scenes // 6))
        queries, sources = self.gather_sources(topic, num_queries, per_query=8)
        brief = format_research_brief(sources)
        user = build_script_user_prompt(topic, brief, num_scenes, min_minutes, max_minutes)
        text = self._chat(SCRIPT_SYSTEM_PROMPT, user)
        data = llm.parse_json_block(text)
        self._apply_callout_analysis(data)  # a focused 2nd pass: pick callouts + flag intense beats
        storyboard = storyboard_from_dict(data)
        return storyboard, sources, data

    def _apply_callout_analysis(self, data: dict) -> None:
        """Second gpt-oss pass over the finished beats: choose sparse on-screen callouts (proper
        names / hard numbers) and flag the most intense beats. Mutates ``data`` in place so the saved
        storyboard.json carries ``emphasis`` + ``intense``. A failed/garbled pass degrades gracefully
        (no callouts) rather than aborting the run."""
        scenes = data.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            return
        for s in scenes:  # start clean; the pass owns these fields now
            s["emphasis"] = ""
            s["intense"] = False
        beats = [{"beat": i, "narration": s.get("narration", "")} for i, s in enumerate(scenes)]
        try:
            text = self._chat(
                CALLOUT_ANALYSIS_SYSTEM_PROMPT, build_callout_analysis_user_prompt(beats), 0.2
            )
            result = llm.parse_json_block(text)
        except (llm.LLMError, RuntimeError) as exc:
            print(f"  callout analysis skipped ({type(exc).__name__}: {exc})", file=sys.stderr)
            return
        for c in result.get("callouts") or []:
            i, txt = c.get("beat"), (c.get("text") or "").strip()
            if isinstance(i, int) and 0 <= i < len(scenes) and 0 < len(txt) <= 40:
                scenes[i]["emphasis"] = txt
        for i in result.get("intense") or []:
            if isinstance(i, int) and 0 <= i < len(scenes):
                scenes[i]["intense"] = True
        _boost_intense_beats(scenes)  # ~1.5x more fire spots than the pass picks (user request)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "script"


def _qc_report(data: dict, sources: list[ResearchSource]) -> str:
    """Every scene ↔ its cited sources, for a human fact-check spot-check."""
    lines = [f"# QC — fact-check: {data.get('title', '(untitled)')}\n"]
    for i, scene in enumerate(data.get("scenes", [])):
        cites = scene.get("cite") or []
        lines.append(f"## Scene {i} ({scene.get('shot_type', '?')})")
        lines.append(f"> {scene.get('narration', '')}")
        if cites:
            for n in cites:
                src = sources[n - 1] if 1 <= n <= len(sources) else None
                lines.append(f"- [{n}] {src.title} — {src.url}" if src else f"- [{n}] (out of range!)")
        else:
            lines.append("- (no citation — verify this is a framing/transition line, not a fact)")
        lines.append("")
    return "\n".join(lines)


#: ~10s of narration per (longer) beat → beats needed for a target minute band.
def scenes_for_minutes(min_minutes: float, max_minutes: float, seconds_per_beat: float = 10.0) -> int:
    return max(20, round((min_minutes + max_minutes) / 2 * 60 / seconds_per_beat))


def build_and_save(
    topic: str, scenes: int | None = None, min_minutes: float = 6.0, max_minutes: float = 9.0,
    log=print,
) -> Path:
    """topic → research → script; write storyboard.json/sources.json/qc.md. Returns the output dir.

    Shared by the CLI and the dashboard's run_pipeline orchestrator. ``scenes`` overrides the beat
    count; otherwise it's derived from the ``min_minutes``-``max_minutes`` band. ``log`` is any
    line-logger (``print`` or ``RunRecorder.log``) so progress shows up wherever the caller wants it.
    """
    scenes = scenes or scenes_for_minutes(min_minutes, max_minutes)
    provider = LLMScriptProvider(ExaResearchProvider())
    log(f"researching topic {topic!r} · model={provider.model} · "
        f"target {min_minutes:g}-{max_minutes:g} min (~{scenes} beats)")
    storyboard, sources, data = provider.generate(topic, scenes, min_minutes, max_minutes)
    log(f"gathered {len(sources)} real sources · script has {len(storyboard.scenes)} scenes")

    out = OUT_DIR / _slug(topic)
    out.mkdir(parents=True, exist_ok=True)
    (out / "storyboard.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
    (out / "sources.json").write_text(
        json.dumps([s.model_dump() for s in sources], indent=2, ensure_ascii=False)
    )
    (out / "qc.md").write_text(_qc_report(data, sources))
    return out


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser()
    ap.add_argument("topic")
    ap.add_argument("--min-minutes", type=float, default=6.0)
    ap.add_argument("--max-minutes", type=float, default=9.0)
    ap.add_argument("--scenes", type=int, default=None, help="override the beat count (else derived)")
    args = ap.parse_args()

    out = build_and_save(args.topic, args.scenes, args.min_minutes, args.max_minutes)
    print(f"\n✅ {out}/  (storyboard.json · sources.json · qc.md)")
    print(f"   → render: python tools/studio_poc.py --images gemini --voice cartesia "
          f"--storyboard {out / 'storyboard.json'}")


if __name__ == "__main__":
    main()
