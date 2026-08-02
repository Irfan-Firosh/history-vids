# Shot-Rate Correction and Render Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Raise the pipeline's shot rate from 52 shots/8-min to ~208 (matching the measured reference), and replace the single-pass FFmpeg assembler — which benchmarks at ~12.8 hours for an 8-minute video — with a cached, parallel, segment-wise renderer.

**Architecture:** Four stages replace one monolithic `render_video` call: a pure shot planner splits beats on clause boundaries; images are built once and content-hash cached with callouts baked in via PIL; each shot renders to an independent short mp4; a final pass concatenates them (stream-copy) and burns libass subtitles in a single filtergraph with zero overlay nodes. Everything upstream of the renderer — research, script, grounding gate, Cartesia word-timestamp alignment, `RunRecorder`, dashboard — is kept and retuned, not rewritten.

**Tech Stack:** Python 3.12, `uv`, pydantic v2 (frozen models), pytest, ruff, FFmpeg 8.1.2 (+ keg-only `ffmpeg-full` for libass), Pillow, numpy, Agnes image API, Cartesia TTS.

## Global Constraints

- **Package manager is `uv`.** Every command is `uv run …`. Never `pip install` into `.venv`.
- **Lint:** `uv run ruff check .` must pass. Rules `E,F,I,UP,B`; **line-length 100**.
- **Tests:** `uv run pytest -q` must pass. Baseline at plan start is **196 passing**; that number only goes up.
- **Pure vs side-effecting:** anything in `studio/` has **no I/O** — no file reads, no network, no `subprocess`. I/O lives in `tools/`. This is the existing convention and every new pure module must honour it.
- **Immutability:** new value objects are `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`, matching `studio/types.py`.
- **Type annotations on every function signature.** `from __future__ import annotations` at the top of every module.
- **Never print or commit `.env` values.** Reference variable *names* only.
- **Never commit competitor media.** Frames/clips/thumbnails stay in scratch. Measured *numbers* may be committed.
- **No motion.** The reference measured 0% camera moves, 0% character animation, 0% dissolves. Do not add Ken Burns, zoompan, crossfades, or any tween. `studio/kenburns.py` stays unreachable by design.
- **Commit format:** `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf, ci). No attribution trailer.
- **Pre-commit:** run `coderabbit review --uncommitted` before each commit and address findings.
- **Reference targets (Axen pole, from `context/research/2026-08-01/04-video-forensics.md`):** median shot 2.2 s (p10 0.9 / p90 4.6), 16–18 cuts/min, ≥94.6% frozen runtime, 9–11 narration words per image, 196 wpm, dry VO with no music bed.

**Spec:** `docs/superpowers/specs/2026-08-02-shot-rate-and-render-rebuild-design.md`

---

## Phase Overview

| Phase | Deliverable | Independently shippable? |
|---|---|---|
| **0** | FFmpeg capability probe + `FFMPEG_BIN` selection | Yes — no behaviour change |
| **1** | Word-anchored captions; run settings persisted | Yes — fixes two live bugs |
| **2** | Script rubric gate (L1), calibrated | Yes — blocks bad scripts pre-spend |
| **3** | Clause-aware shot planning at reference rate | Yes — but slow to render until Phase 4 |
| **4** | Segment-wise cached renderer replacing `render_video` | Yes — the core win |
| **5** | Style metrics + pre-flight gate (L2/L3) | Yes |
| **6** | Parallel Agnes at 20 rpm; native-resolution frames | Yes |
| **7** | Motion conformance acceptance test (L5) | Yes |

**Phases 3 and 4 must land together in that order** — Phase 3 quadruples shot count, which makes the old assembler even slower. Do not ship Phase 3 to a real run without Phase 4.

---

# Phase 0 — Environment and FFmpeg capability

### Task 0.1: FFmpeg binary selection and capability probe

The machine's default `ffmpeg` 8.1.2 has **no libass, libfreetype, or drawtext**. `ffmpeg-full` is keg-only, so it installs alongside without conflict. This task makes the binary selectable and the capability detectable, so later phases can choose the subtitle backend and refuse renders that would take hours.

**Files:**
- Create: `tools/render/__init__.py`
- Create: `tools/render/ffmpeg.py`
- Test: `tests/test_render_ffmpeg.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `ffmpeg_bin() -> str` — path from `$FFMPEG_BIN`, else `"ffmpeg"`
  - `has_filter(name: str, *, bin_path: str | None = None) -> bool`
  - `subtitle_backend(*, bin_path: str | None = None) -> str` — `"libass"` or `"png_overlay"`

- [ ] **Step 1: Install the libass-capable binary**

```bash
brew install ffmpeg-full
/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg -hide_banner -filters | grep -E "^ .. subtitles"
```

Expected: a line containing `subtitles`. Record the path — it is `FFMPEG_BIN` for later phases.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_render_ffmpeg.py
import os
import pytest
from tools.render import ffmpeg


def test_ffmpeg_bin_defaults_to_path_lookup(monkeypatch):
    monkeypatch.delenv("FFMPEG_BIN", raising=False)
    assert ffmpeg.ffmpeg_bin() == "ffmpeg"


def test_ffmpeg_bin_honours_env(monkeypatch):
    monkeypatch.setenv("FFMPEG_BIN", "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg")
    assert ffmpeg.ffmpeg_bin() == "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def test_has_filter_reports_a_filter_that_always_exists():
    # `overlay` ships in every ffmpeg build; if this fails, ffmpeg itself is broken.
    assert ffmpeg.has_filter("overlay") is True


def test_has_filter_reports_false_for_a_nonexistent_filter():
    assert ffmpeg.has_filter("definitely_not_a_real_filter") is False


def test_subtitle_backend_is_one_of_the_two_known_values():
    assert ffmpeg.subtitle_backend() in {"libass", "png_overlay"}
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_render_ffmpeg.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.render'`

- [ ] **Step 4: Implement**

```python
# tools/render/__init__.py
"""Side-effecting render stage: ffmpeg invocation, per-shot segments, final assembly."""
```

```python
# tools/render/ffmpeg.py
"""Which ffmpeg do we call, and what can it do?

The default Homebrew ffmpeg 8.1.2 is built WITHOUT libass/libfreetype/drawtext, which is why
captions were originally rendered as full-frame PNG overlays. That path costs ~0.011 s/frame per
overlay and does not scale past ~50 cues. `ffmpeg-full` is keg-only, so pointing `FFMPEG_BIN` at
it gets libass without disturbing the default install.
"""

from __future__ import annotations

import functools
import os
import subprocess

#: A build without this filter cannot burn .ass subtitles and must fall back to PNG overlays.
_SUBTITLE_FILTER = "subtitles"


def ffmpeg_bin() -> str:
    """The ffmpeg executable to invoke. Override with ``FFMPEG_BIN``."""
    return os.environ.get("FFMPEG_BIN") or "ffmpeg"


@functools.lru_cache(maxsize=8)
def _filters(bin_path: str) -> frozenset[str]:
    """Filter names this build exposes. Cached — shelling out per query is wasteful."""
    try:
        out = subprocess.run(
            [bin_path, "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=30, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names: set[str] = set()
    for line in out.splitlines():
        parts = line.split()
        # Rows look like: " ... name  in->out  description"; the flags column precedes the name.
        if len(parts) >= 3 and not line.startswith("Filters:"):
            names.add(parts[1] if len(parts[0]) <= 3 else parts[0])
    return frozenset(names)


def has_filter(name: str, *, bin_path: str | None = None) -> bool:
    """Does this ffmpeg build expose `name`?"""
    return name in _filters(bin_path or ffmpeg_bin())


def subtitle_backend(*, bin_path: str | None = None) -> str:
    """``"libass"`` when .ass burn-in is available, else ``"png_overlay"`` (slow, small runs only)."""
    return "libass" if has_filter(_SUBTITLE_FILTER, bin_path=bin_path) else "png_overlay"
```

- [ ] **Step 5: Run tests and lint**

Run: `uv run pytest tests/test_render_ffmpeg.py -v && uv run ruff check .`
Expected: 5 passed, ruff clean

- [ ] **Step 6: Review and commit**

```bash
coderabbit review --uncommitted
git add tools/render/__init__.py tools/render/ffmpeg.py tests/test_render_ffmpeg.py
git commit -m "feat: select ffmpeg binary and probe subtitle capability"
```

---

# Phase 1 — Correctness fixes

Two live bugs, both independent of the architecture work.

### Task 1.1: Word-anchor the caption timeline

`caption_timeline` anchors cues to beat spans then spreads them **proportionally by character count**, while `align_beats_to_words` beside it uses real Cartesia word timings. Subtitles are on screen 100% of runtime and drift for no reason.

The insight that makes this simple: cues concatenated in order equal the beats concatenated in order, which equals the transcript that was actually spoken. So the whole cue list can be mapped onto the word stream in one pass — no per-beat nesting.

**Files:**
- Modify: `studio/narration.py:182-194` (`caption_timeline`)
- Modify: `studio/captions.py:1-6` (stale docstring)
- Modify: `studio/__init__.py` (export `word_spans_for_texts`)
- Test: `tests/test_studio.py`

**Interfaces:**
- Consumes: `split_caption_cues(text, max_words, max_chars) -> list[str]` from `studio/captions.py`
- Produces:
  - `word_spans_for_texts(texts, words, word_starts, word_ends) -> list[tuple[int, int]]` — inclusive first/last word index per text
  - `caption_timeline(beat_spans, narrations, *, word_starts=(), word_ends=(), max_words=7, max_chars=42) -> list[tuple[str, float, float]]` — unchanged behaviour when word data is absent

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_studio.py  (append)
from studio.narration import caption_timeline, word_spans_for_texts


def test_word_spans_are_contiguous_monotonic_and_cover_every_word():
    texts = ["one two", "three four five", "six"]
    words = ["one", "two", "three", "four", "five", "six"]
    starts = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]
    ends = [0.9, 1.9, 2.9, 3.9, 4.9, 5.9]
    spans = word_spans_for_texts(texts, words, starts, ends)
    assert len(spans) == 3
    assert spans[0][0] == 0 and spans[-1][1] == len(words) - 1
    for (_, prev_end), (next_start, _) in zip(spans, spans[1:]):
        assert next_start == prev_end + 1          # contiguous, no gaps, no overlap
    assert all(a <= b for a, b in spans)           # never empty


def test_caption_timeline_uses_real_word_times_when_available():
    # One beat, two cues. Speech is deliberately UNEVEN: the first cue takes 4s, the second 1s.
    # Proportional spreading would split near the middle; word anchoring must land on 4.0.
    narrations = ["alpha bravo charlie delta."]
    words = ["alpha", "bravo", "charlie", "delta."]
    starts = [0.0, 3.0, 4.0, 4.4]
    ends = [2.9, 3.9, 4.3, 5.0]
    got = caption_timeline(
        [(0.0, 5.0)], narrations, word_starts=starts, word_ends=ends, words=words, max_words=2,
    )
    assert [c for c, _, _ in got] == ["alpha bravo", "charlie delta."]
    assert got[0][1] == 0.0
    assert got[0][2] == 3.9        # real end of "bravo", NOT a proportional guess
    assert got[1][1] == 4.0        # real start of "charlie"


def test_caption_timeline_falls_back_to_proportional_without_word_data():
    # The offline `say` voice returns no word timings; behaviour must be unchanged there.
    got = caption_timeline([(0.0, 4.0)], ["alpha bravo charlie delta."], max_words=2)
    assert [c for c, _, _ in got] == ["alpha bravo", "charlie delta."]
    assert got[0][1] == 0.0
    assert got[-1][2] == 4.0       # last cue still ends exactly at the beat end
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_studio.py -k "word_spans or caption_timeline" -v`
Expected: FAIL — `ImportError: cannot import name 'word_spans_for_texts'`

- [ ] **Step 3: Implement**

```python
# studio/narration.py  — replace caption_timeline, add word_spans_for_texts above it

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
```

Then fix the stale docstring at the top of `studio/captions.py` — replace the sentence
`"Cartesia gives no word timestamps, so we split a scene's narration into short cues and spread the
scene's audio duration across them proportionally to length."` with:

```
Cartesia DOES return per-word timestamps (``CartesiaTimestampVoice``, ``add_timestamps``), and
``narration.caption_timeline`` anchors cues to them. This module only decides WHERE to split;
the proportional ``cue_timings`` below is the fallback for voices with no word data (offline ``say``).
```

Add `word_spans_for_texts` to the `studio/narration` import block and `__all__` in `studio/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 199 passed (196 + 3), ruff clean

- [ ] **Step 5: Wire the call site**

In `tools/studio_poc.py:_assemble_video`, pass the word data through. The beat-span computation
already has `words`, `word_starts`, `word_ends` in scope where `align_beats_to_words` is called;
persist them alongside `_save_beat_spans` so the approve-time assemble path has them too. Where
`cues = caption_timeline(beat_spans, narrations) if captions else []` appears, change to:

```python
cues = caption_timeline(
    beat_spans, narrations, words=words, word_starts=word_starts, word_ends=word_ends,
) if captions else []
```

- [ ] **Step 6: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/narration.py studio/captions.py studio/__init__.py tools/studio_poc.py tests/test_studio.py
git commit -m "fix: anchor caption cues to real spoken word times"
```

---

### Task 1.2: Persist run settings on the manifest

`RunManifest` has no `captions` field, so re-run and resume silently fall back to defaults — the behaviour `dashboard/app.py:328` documents as a known gap. This adds a `settings` block and a `stats` block, so the dashboard has data to show and re-runs inherit choices.

**Files:**
- Modify: `studio/run_log.py` (add `RunSettings`, `RunStats`; two fields on `RunManifest`)
- Modify: `dashboard/app.py` (`_spawn_run`, `rerun_run`, `resume_run` read settings from the manifest)
- Test: `tests/test_run_log.py`, `tests/test_dashboard.py`

**Interfaces:**
- Consumes: `RunManifest` from `studio/run_log.py`
- Produces:
  - `RunSettings(captions: bool = True, min_minutes: float | None = None, max_minutes: float | None = None, images_provider: str = "", voice: str = "", shot_hold_sec: float | None = None)`
  - `RunStats(shots: int = 0, images_generated: int = 0, images_cached: int = 0, stage_seconds: dict[str, float] = {}, duration_target_sec: float | None = None, duration_actual_sec: float | None = None, subtitle_backend: str = "")`
  - `RunManifest.settings: RunSettings`, `RunManifest.stats: RunStats`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_run_log.py  (append)
from studio.run_log import RunManifest, RunSettings, RunStats


def test_manifest_defaults_keep_old_run_json_loadable():
    # Runs recorded before this change have no settings/stats keys; they must still parse.
    m = RunManifest(
        run_id="x", title="t", images_provider="agnes", voice_provider="cartesia",
        status="completed", scene_count=3, started_at="2026-08-02T00:00:00",
        updated_at="2026-08-02T00:00:00",
    )
    assert m.settings.captions is True
    assert m.stats.shots == 0


def test_settings_round_trip_through_json():
    m = RunManifest(
        run_id="x", title="t", images_provider="agnes", voice_provider="cartesia",
        status="completed", scene_count=3, started_at="2026-08-02T00:00:00",
        updated_at="2026-08-02T00:00:00",
        settings=RunSettings(captions=False, min_minutes=7.5, max_minutes=8.5),
        stats=RunStats(shots=208, images_cached=12, subtitle_backend="libass"),
    )
    again = RunManifest.model_validate_json(m.model_dump_json())
    assert again.settings.captions is False
    assert again.settings.min_minutes == 7.5
    assert again.stats.shots == 208
    assert again.stats.subtitle_backend == "libass"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_run_log.py -v`
Expected: FAIL — `ImportError: cannot import name 'RunSettings'`

- [ ] **Step 3: Implement**

```python
# studio/run_log.py  — add above RunManifest

class RunSettings(BaseModel):
    """The operator's choices for a run, persisted so re-run and resume inherit them.

    Without this, `dashboard/app.py` re-runs fell back to defaults and silently discarded the
    captions choice the user made on the original run.
    """

    model_config = ConfigDict(frozen=True)

    captions: bool = True
    min_minutes: float | None = None
    max_minutes: float | None = None
    images_provider: str = ""
    voice: str = ""
    shot_hold_sec: float | None = None


class RunStats(BaseModel):
    """Measured facts about a finished run — what the dashboard shows without reading the log."""

    model_config = ConfigDict(frozen=True)

    shots: int = 0
    images_generated: int = 0
    images_cached: int = 0
    stage_seconds: dict[str, float] = {}
    duration_target_sec: float | None = None
    duration_actual_sec: float | None = None
    subtitle_backend: str = ""
```

Add to `RunManifest`:

```python
    settings: RunSettings = RunSettings()
    stats: RunStats = RunStats()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 201 passed, ruff clean

- [ ] **Step 5: Read settings back in the dashboard**

In `dashboard/app.py`, `_spawn_run` writes `RunSettings` onto the manifest at start. `rerun_run` and `resume_run` read `manifest["settings"]["captions"]` (defaulting to `True` when absent) instead of assuming the default, and delete the now-inaccurate comment at line 328.

- [ ] **Step 6: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/run_log.py dashboard/app.py tests/test_run_log.py tests/test_dashboard.py
git commit -m "feat: persist run settings and stats on the manifest"
```

---

# Phase 2 — The script rubric gate

### Task 2.1: Pure script rubric

Thresholds come from `context/research/2026-08-01/05-script-craft.md`, measured on an age-controlled Mack cohort (996K / 31K / 24K views, same channel, same format, published within ~4 weeks).

**Files:**
- Create: `studio/script_rubric.py`
- Modify: `studio/__init__.py` (exports)
- Test: `tests/test_script_rubric.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `RubricReport` (frozen) with fields `words: int`, `first_question_sec: float | None`, `second_person_per_1k: float`, `second_person_after_90s_per_1k: float`, `mean_sentence_words: float`, `short_sentence_pct: float`, `long_sentence_pct: float`, `numbers_per_1k: float`, `failures: tuple[str, ...]`; properties `.ok -> bool`, `.summary() -> str`
  - `score_script(narrations: Sequence[str], wpm: float = 196.0) -> RubricReport`
  - Constants `MAX_FIRST_QUESTION_SEC = 45.0`, `MIN_2P_AFTER_90S_PER_1K = 8.0`, `MAX_MEAN_SENTENCE_WORDS = 17.0`, `MIN_SHORT_SENTENCE_PCT = 25.0`, `MAX_LONG_SENTENCE_PCT = 22.0`, `MIN_NUMBERS_PER_1K = 10.0`

- [ ] **Step 1: Write the failing tests**

The first test is the regression guard for a bug the research agent hit and corrected in its own detector: a hook question ending `?"` is read at the wrong timestamp by naive parsing, inverting the most important rule.

```python
# tests/test_script_rubric.py
from studio.script_rubric import (
    MAX_FIRST_QUESTION_SEC,
    RubricReport,
    score_script,
)


def test_question_mark_followed_by_a_closing_quote_is_still_a_question():
    # Mack's 1.6M-view hook ends `?"`. Naive detection missed it and reported the first question
    # at 313s instead of 23s — which would fail the single most important rule on a winning script.
    narrations = ['He asked one thing: "what if we were never meant to survive?" Nobody answered.']
    report = score_script(narrations)
    assert report.first_question_sec is not None
    assert report.first_question_sec < MAX_FIRST_QUESTION_SEC


def test_a_script_with_no_question_at_all_reports_none_and_fails():
    report = score_script(["This is a statement. So is this. And this one too."])
    assert report.first_question_sec is None
    assert not report.ok
    assert any("question" in f for f in report.failures)


def test_first_question_time_is_derived_from_word_position_and_wpm():
    # 98 words of preamble at 196 wpm = 30s, so the question lands at ~30s.
    narrations = [" ".join(["word"] * 98) + " why did they leave?"]
    report = score_script(narrations, wpm=196.0)
    assert 29.0 <= report.first_question_sec <= 31.5


def test_second_person_density_is_measured_after_the_90_second_mark():
    # 300 words of body (past 90s at 196 wpm) containing 6 "you" -> 20 per 1k, comfortably passing.
    body = (" ".join(["filler"] * 44) + " you know this.") * 6
    report = score_script([body])
    assert report.second_person_after_90s_per_1k >= 8.0


def test_long_rambling_sentences_fail_the_rubric():
    # The 24K underperformer: mean sentence 28.4 words, 2.4% short, 51% long.
    long_sentence = " ".join(["word"] * 30) + "."
    report = score_script([long_sentence * 10])
    assert not report.ok
    assert any("sentence" in f for f in report.failures)


def test_summary_is_a_single_readable_line():
    report = score_script(["Why did they leave? You know. They ran. It was 1905."])
    assert "\n" not in report.summary()
    assert isinstance(report, RubricReport)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_script_rubric.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.script_rubric'`

- [ ] **Step 3: Implement**

```python
# studio/script_rubric.py
"""Numeric quality gate for a generated script (pure).

Mirrors ``studio.research.grounding_report``: measure, report, and let the caller refuse BEFORE any
image or TTS spend. Thresholds are derived in context/research/2026-08-01/05-script-craft.md from an
age-controlled cohort — three videos on one channel, same narrator and format, published within
~4 weeks, spanning 996K / 31K / 24K views. Holding channel and age constant is what makes the
measured differences attributable to the writing.
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

#: The hook question must land early. Winner: 0:16. Underperformer: 6:51.
MAX_FIRST_QUESTION_SEC = 45.0
#: Second-person density AFTER the hook is what separates winners; the opening always has it.
MIN_2P_AFTER_90S_PER_1K = 8.0
#: Winner 14.0 words; underperformer 28.4.
MAX_MEAN_SENTENCE_WORDS = 17.0
#: Winner 31% of sentences under 8 words; underperformer 2.4%.
MIN_SHORT_SENTENCE_PCT = 25.0
#: Winner 14% over 25 words; underperformer 51%.
MAX_LONG_SENTENCE_PCT = 22.0
#: Concrete figures. Winner 14.8/1k; underperformer 2.6.
MIN_NUMBERS_PER_1K = 10.0

_SHORT_SENTENCE_WORDS = 8
_LONG_SENTENCE_WORDS = 25
_BODY_STARTS_SEC = 90.0

#: A question mark may be followed by a closing quote or bracket before the sentence truly ends.
#: Missing this reads Mack's `?"` hook at 313s instead of 23s.
_QUESTION = re.compile(r'\?["\'”’)\]]*')
_SENTENCE_SPLIT = re.compile(r'(?<=[.!?])["\'”’)\]]*\s+')
_SECOND_PERSON = re.compile(r"\b(you|your|yours|yourself)\b", re.IGNORECASE)
_NUMBER = re.compile(r"\b\d[\d,.]*\b")


class RubricReport(BaseModel):
    """How a script measures against the reference cohort."""

    model_config = ConfigDict(frozen=True)

    words: int
    first_question_sec: float | None
    second_person_per_1k: float
    second_person_after_90s_per_1k: float
    mean_sentence_words: float
    short_sentence_pct: float
    long_sentence_pct: float
    numbers_per_1k: float
    failures: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """False when the script violates a threshold the cohort says predicts failure."""
        return not self.failures

    def summary(self) -> str:
        q = f"{self.first_question_sec:.0f}s" if self.first_question_sec is not None else "never"
        return (
            f"{self.words}w · first ? {q} · 2p {self.second_person_after_90s_per_1k:.1f}/1k after 90s "
            f"· sentence {self.mean_sentence_words:.1f}w "
            f"({self.short_sentence_pct:.0f}% short / {self.long_sentence_pct:.0f}% long) "
            f"· numbers {self.numbers_per_1k:.1f}/1k"
        )


def _sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SENTENCE_SPLIT.split(text)) if s]


def score_script(narrations: Sequence[str], wpm: float = 196.0) -> RubricReport:
    """Measure a script against the reference thresholds. Pure and free — run it before any spend."""
    text = " ".join(n.strip() for n in narrations if n.strip())
    words = text.split()
    n_words = len(words)
    if n_words == 0:
        return RubricReport(
            words=0, first_question_sec=None, second_person_per_1k=0.0,
            second_person_after_90s_per_1k=0.0, mean_sentence_words=0.0,
            short_sentence_pct=0.0, long_sentence_pct=0.0, numbers_per_1k=0.0,
            failures=("empty script",),
        )
    per_word_sec = 60.0 / wpm if wpm > 0 else 0.0

    match = _QUESTION.search(text)
    first_q: float | None = None
    if match:
        first_q = len(text[: match.start()].split()) * per_word_sec

    body_start_word = int(_BODY_STARTS_SEC / per_word_sec) if per_word_sec else 0
    body = " ".join(words[body_start_word:])
    body_words = max(len(body.split()), 1)

    sents = _sentences(text) or [text]
    lengths = [len(s.split()) for s in sents]
    mean_len = sum(lengths) / len(lengths)
    short_pct = sum(1 for n in lengths if n < _SHORT_SENTENCE_WORDS) / len(lengths) * 100
    long_pct = sum(1 for n in lengths if n > _LONG_SENTENCE_WORDS) / len(lengths) * 100

    per_1k = 1000.0 / n_words
    report = RubricReport(
        words=n_words,
        first_question_sec=first_q,
        second_person_per_1k=len(_SECOND_PERSON.findall(text)) * per_1k,
        second_person_after_90s_per_1k=len(_SECOND_PERSON.findall(body)) * 1000.0 / body_words,
        mean_sentence_words=mean_len,
        short_sentence_pct=short_pct,
        long_sentence_pct=long_pct,
        numbers_per_1k=len(_NUMBER.findall(text)) * per_1k,
    )
    failures: list[str] = []
    if report.first_question_sec is None:
        failures.append("no question mark anywhere — the hook never asks anything")
    elif report.first_question_sec > MAX_FIRST_QUESTION_SEC:
        failures.append(
            f"first question at {report.first_question_sec:.0f}s (max {MAX_FIRST_QUESTION_SEC:.0f}s)"
        )
    if report.second_person_after_90s_per_1k < MIN_2P_AFTER_90S_PER_1K:
        failures.append(
            f"second person {report.second_person_after_90s_per_1k:.1f}/1k after 90s "
            f"(min {MIN_2P_AFTER_90S_PER_1K})"
        )
    if report.mean_sentence_words > MAX_MEAN_SENTENCE_WORDS:
        failures.append(
            f"mean sentence {report.mean_sentence_words:.1f}w (max {MAX_MEAN_SENTENCE_WORDS})"
        )
    if report.short_sentence_pct < MIN_SHORT_SENTENCE_PCT:
        failures.append(
            f"only {report.short_sentence_pct:.0f}% short sentences (min {MIN_SHORT_SENTENCE_PCT:.0f}%)"
        )
    if report.long_sentence_pct > MAX_LONG_SENTENCE_PCT:
        failures.append(
            f"{report.long_sentence_pct:.0f}% long sentences (max {MAX_LONG_SENTENCE_PCT:.0f}%)"
        )
    if report.numbers_per_1k < MIN_NUMBERS_PER_1K:
        failures.append(f"numbers {report.numbers_per_1k:.1f}/1k (min {MIN_NUMBERS_PER_1K})")
    return report.model_copy(update={"failures": tuple(failures)})
```

Export `score_script`, `RubricReport` from `studio/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_script_rubric.py -v && uv run ruff check .`
Expected: 6 passed, ruff clean

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/script_rubric.py studio/__init__.py tests/test_script_rubric.py
git commit -m "feat: numeric script rubric derived from an age-controlled cohort"
```

---

### Task 2.2: Calibrate the rubric, then wire it as a gate

`tasks/lessons.md` records the rule from the grounding gate: *a threshold you haven't replayed is a guess.* Calibrate before enforcing.

**Files:**
- Create: `tools/calibrate_rubric.py`
- Modify: `tools/make_script.py` (gate in `build_and_save`, `--skip-rubric` flag)
- Test: `tests/test_studio.py`

**Interfaces:**
- Consumes: `score_script`, `RubricReport` from Task 2.1
- Produces: `build_and_save(..., skip_rubric: bool = False)` raising `RuntimeError` on a failing script

- [ ] **Step 1: Write the calibration harness**

```python
# tools/calibrate_rubric.py
"""Replay the rubric over real corpora before trusting it to block runs.

Pass criteria: every measured WINNER passes, the measured UNDERPERFORMER fails. If a threshold
rejects a 996K-view script, the threshold is wrong — not the script.

Usage:
    uv run python tools/calibrate_rubric.py result/axen/scripts /path/to/transcripts
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from studio.script_rubric import score_script  # noqa: E402


def _narrations(path: Path) -> list[str]:
    if path.suffix == ".json":
        data = json.loads(path.read_text())
        return [s.get("narration", "") for s in data.get("scenes", []) if isinstance(s, dict)]
    return [path.read_text()]


def main() -> None:
    roots = [Path(a) for a in sys.argv[1:]] or [Path("result/axen/scripts")]
    files: list[Path] = []
    for root in roots:
        files += sorted(root.rglob("storyboard.json")) + sorted(root.rglob("*.txt"))
    passed = 0
    for f in files:
        report = score_script(_narrations(f))
        mark = "PASS" if report.ok else "FAIL"
        passed += report.ok
        print(f"{mark}  {f}\n      {report.summary()}")
        for failure in report.failures:
            print(f"        - {failure}")
    print(f"\n{passed}/{len(files)} passed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run calibration and record the result**

```bash
uv run python tools/calibrate_rubric.py result/axen/scripts
```

Record the pass count for the 13 existing scripts — that is the honest baseline of where the pipeline is today. Then run it over the competitor transcripts in the research scratch dir. **If any 996K-view winner fails, adjust the threshold and re-run before continuing.** Write the calibration outcome into `tasks/lessons.md` as a dated entry.

- [ ] **Step 3: Write the failing gate test**

```python
# tests/test_studio.py  (append)
import pytest
from studio.script_rubric import score_script


def test_rubric_rejects_the_underperformer_shape_and_accepts_the_winner_shape():
    winner = [
        "You wake up cold. Why did they leave? Nobody knows.",
        "In 1905, 12 families walked out. You would have too. It was 40 below.",
    ]
    loser = [" ".join(["word"] * 30) + "." for _ in range(8)]
    assert score_script(winner * 6).ok
    assert not score_script(loser).ok
```

- [ ] **Step 4: Run to verify it passes against the implementation from Task 2.1**

Run: `uv run pytest tests/test_studio.py -k rubric -v`
Expected: PASS

- [ ] **Step 5: Wire the gate into `build_and_save`**

In `tools/make_script.py`, directly after the existing grounding gate block (which ends with the
`report.out_of_range` warning), add:

```python
    # Script-craft gate, also BEFORE any image/TTS spend and beside the grounding gate. Grounding
    # asks "is this true?"; the rubric asks "will anyone watch it?" — measured on an age-controlled
    # cohort where the only variable was the writing. Thresholds calibrated in
    # tools/calibrate_rubric.py; see tasks/lessons.md.
    rubric = score_script([s.narration for s in storyboard.scenes])
    log(f"rubric: {rubric.summary()}")
    if not rubric.ok and not skip_rubric:
        raise RuntimeError(
            "script fails the craft rubric; refusing to render:\n  - "
            + "\n  - ".join(rubric.failures)
            + "\nRe-run the topic, or pass --skip-rubric to render anyway."
        )
    if not rubric.ok:
        log(f"  ⚠ rubric bypassed via --skip-rubric ({len(rubric.failures)} failures)")
```

Add `skip_rubric: bool = False` to the `build_and_save` signature, an `--skip-rubric` argparse flag,
and the `score_script` import.

- [ ] **Step 6: Run the full suite, review and commit**

```bash
uv run pytest -q && uv run ruff check .
coderabbit review --uncommitted
git add tools/calibrate_rubric.py tools/make_script.py tests/test_studio.py tasks/lessons.md
git commit -m "feat: gate renders on a calibrated script-craft rubric"
```

---

# Phase 3 — Shot planning at the reference rate

### Task 3.1: Clause-aware shot planner

Reference cuts on clause at 9–11 narration words per image, not on a timer.

**Files:**
- Create: `studio/shots.py`
- Modify: `studio/__init__.py`
- Test: `tests/test_shots.py`

**Interfaces:**
- Consumes: `word_spans_for_texts` from Task 1.1
- Produces:
  - `Shot` (frozen): `beat_index: int`, `sub_index: int`, `start: float`, `end: float`, `image_key: str`, `shot_type: str`
  - `WORDS_PER_SHOT = 10`, `MIN_SHOT_SEC = 0.9`, `MAX_SHOT_SEC = 8.5`
  - `split_clauses(text: str, words_per_shot: int = WORDS_PER_SHOT) -> list[str]`
  - `plan_shots(beat_spans, scenes, *, words=(), word_starts=(), word_ends=(), words_per_shot=WORDS_PER_SHOT) -> list[Shot]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_shots.py
from studio.shots import MAX_SHOT_SEC, MIN_SHOT_SEC, Shot, plan_shots, split_clauses
from studio.types import Scene


def _scene(narration: str) -> Scene:
    return Scene(narration=narration, image_prompt="a stick figure", shot_type="character")


def test_split_clauses_breaks_at_punctuation_before_word_count():
    text = "They ran. The fire spread fast across the whole valley that night."
    parts = split_clauses(text, words_per_shot=10)
    assert parts[0] == "They ran."
    assert len(parts) >= 2


def test_split_clauses_covers_every_word_exactly_once():
    text = "one two three four five six seven eight nine ten eleven twelve thirteen"
    parts = split_clauses(text, words_per_shot=5)
    assert " ".join(parts).split() == text.split()


def test_plan_shots_hits_the_reference_shot_rate_for_an_eight_minute_script():
    # 8 min at 196 wpm = ~1568 words over ~52 beats. At ~10 words/shot that is ~157 shots,
    # i.e. ~3.1s per shot — inside the reference envelope (p10 0.9 / median 2.2 / p90 4.6).
    beat_words = 30
    beats = 52
    scenes = [_scene(" ".join(["word"] * beat_words) + ".") for _ in range(beats)]
    spans = [(i * 9.23, (i + 1) * 9.23) for i in range(beats)]
    shots = plan_shots(spans, scenes)
    assert 120 <= len(shots) <= 240
    durations = [s.end - s.start for s in shots]
    assert all(d >= MIN_SHOT_SEC for d in durations)
    assert all(d <= MAX_SHOT_SEC for d in durations)


def test_plan_shots_produces_contiguous_monotonic_spans():
    scenes = [_scene("one two three four. five six seven eight."), _scene("nine ten eleven.")]
    spans = [(0.0, 6.0), (6.0, 9.0)]
    shots = plan_shots(spans, scenes, words_per_shot=4)
    assert shots[0].start == 0.0
    assert shots[-1].end == 9.0
    for a, b in zip(shots, shots[1:]):
        assert b.start == a.end


def test_image_keys_are_unique_so_adjacent_shots_never_reuse_a_frame():
    scenes = [_scene("one two three four five six seven eight.")]
    shots = plan_shots([(0.0, 8.0)], scenes, words_per_shot=4)
    keys = [s.image_key for s in shots]
    assert len(keys) == len(set(keys))


def test_a_beat_too_short_to_split_yields_exactly_one_shot():
    shots = plan_shots([(0.0, 1.0)], [_scene("Go.")])
    assert len(shots) == 1
    assert shots[0].start == 0.0 and shots[0].end == 1.0


def test_shot_type_is_inherited_from_its_beat():
    scene = Scene(narration="one two three four.", image_prompt="a map", shot_type="map")
    assert all(s.shot_type == "map" for s in plan_shots([(0.0, 4.0)], [scene]))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_shots.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.shots'`

- [ ] **Step 3: Implement**

```python
# studio/shots.py
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

    Greedy: accumulate clauses until adding the next would overshoot the budget, then cut. A single
    clause longer than the budget is emitted whole rather than split mid-phrase — a cut inside a
    noun phrase reads worse than a slightly long shot.
    """
    pieces = [p for p in (s.strip() for s in _CLAUSE_END.split(text)) if p]
    if not pieces:
        return [text.strip()] if text.strip() else []
    out: list[str] = []
    current: list[str] = []
    count = 0
    for piece in pieces:
        n = len(piece.split())
        if current and count + n > words_per_shot:
            out.append(" ".join(current))
            current, count = [], 0
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
```

Export `Shot`, `plan_shots`, `split_clauses` from `studio/__init__.py`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_shots.py -v && uv run ruff check .`
Expected: 7 passed, ruff clean

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/shots.py studio/__init__.py tests/test_shots.py
git commit -m "feat: clause-aware shot planning at the measured reference rate"
```

---

# Phase 4 — The segment-wise renderer

**This phase replaces `render_video`.** Do not run a real render between Phase 3 and the end of Phase 4 — the old assembler with 4× the shots would take even longer than its benchmarked 12.8 hours.

### Task 4.1: ASS subtitle generation

**Files:**
- Create: `studio/subtitles.py`
- Test: `tests/test_subtitles.py`

**Interfaces:**
- Consumes: cue tuples `(text, start, end)` from `caption_timeline`
- Produces: `build_ass(cues: Sequence[tuple[str, float, float]], *, width: int = 1920, height: int = 1080, font: str = "Arial", font_size: int = 54) -> str`, `ass_timestamp(seconds: float) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_subtitles.py
from studio.subtitles import ass_timestamp, build_ass


def test_timestamp_format_is_h_mm_ss_cc():
    assert ass_timestamp(0.0) == "0:00:00.00"
    assert ass_timestamp(61.5) == "0:01:01.50"
    assert ass_timestamp(3661.25) == "1:01:01.25"


def test_every_cue_becomes_one_dialogue_line():
    cues = [("hello there", 0.0, 1.0), ("second cue", 1.0, 2.0)]
    out = build_ass(cues)
    assert out.count("\nDialogue:") == 2
    assert "hello there" in out and "second cue" in out


def test_braces_and_newlines_are_escaped_so_they_cannot_inject_ass_override_tags():
    # `{...}` is an ASS override block. Unescaped, narration containing braces would be
    # interpreted as styling commands instead of shown as text.
    out = build_ass([("a {b} c\nd", 0.0, 1.0)])
    assert "{b}" not in out
    assert "\\N" in out


def test_header_declares_the_render_resolution():
    out = build_ass([("x", 0.0, 1.0)], width=1920, height=1080)
    assert "PlayResX: 1920" in out
    assert "PlayResY: 1080" in out
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_subtitles.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.subtitles'`

- [ ] **Step 3: Implement**

```python
# studio/subtitles.py
"""Build an .ass subtitle file (pure string generation).

Captions were previously one full-frame PNG overlay per cue, serially chained in a single ffmpeg
filtergraph. Measured on this machine that costs ~0.011 s/frame per overlay: an 8-minute video with
~290 cues over 14,400 frames is ~12.8 hours. libass renders all of them in ONE filter.

This module is pure so the styling is diffable and testable; the burn-in lives in tools/render.
"""

from __future__ import annotations

from collections.abc import Sequence

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, \
Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, \
MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},&H00141414,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,4,0,2,\
120,120,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def ass_timestamp(seconds: float) -> str:
    """``H:MM:SS.CC`` — ASS uses centiseconds, not milliseconds."""
    total = max(0.0, float(seconds))
    hours, rem = divmod(int(total), 3600)
    minutes, secs = divmod(rem, 60)
    centis = int(round((total - int(total)) * 100))
    if centis == 100:  # rounding carried into the next second
        centis, secs = 0, secs + 1
        if secs == 60:
            secs, minutes = 0, minutes + 1
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _escape(text: str) -> str:
    """Neutralise ASS control characters.

    ``{`` opens an override block, so unescaped narration containing braces would be read as
    styling commands rather than displayed. Newlines become the literal ``\\N`` line break.
    """
    return (
        text.replace("\\", "\\\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\r\n", "\\N")
        .replace("\n", "\\N")
    )


def build_ass(
    cues: Sequence[tuple[str, float, float]],
    *,
    width: int = 1920,
    height: int = 1080,
    font: str = "Arial",
    font_size: int = 54,
) -> str:
    """Render cues as an .ass file: dark text with a heavy white outline, bottom-centred."""
    lines = [_HEADER.format(width=width, height=height, font=font, font_size=font_size)]
    for text, start, end in cues:
        if end <= start:
            continue
        lines.append(
            f"Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},Default,,0,0,0,,{_escape(text)}"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_subtitles.py -v && uv run ruff check .`
Expected: 4 passed, ruff clean

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/subtitles.py tests/test_subtitles.py
git commit -m "feat: generate .ass subtitles instead of per-cue PNG overlays"
```

---

### Task 4.2: Content-hash cached segment renderer

**Files:**
- Create: `tools/render/segments.py`
- Test: `tests/test_render_segments.py`

**Interfaces:**
- Consumes: `Shot` from Task 3.1; `ffmpeg_bin` from Task 0.1
- Produces:
  - `CACHE_VERSION = 1`
  - `segment_key(image_bytes: bytes, duration: float, width: int, height: int, fps: int) -> str`
  - `render_segment(image: Path, duration: float, out_dir: Path, *, width=1920, height=1080, fps=30) -> tuple[Path, bool]` — returns `(path, was_cached)`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render_segments.py
import pytest
from tools.render.segments import CACHE_VERSION, segment_key


def test_key_changes_when_any_input_changes():
    base = segment_key(b"img", 2.0, 1920, 1080, 30)
    assert segment_key(b"different", 2.0, 1920, 1080, 30) != base
    assert segment_key(b"img", 2.5, 1920, 1080, 30) != base
    assert segment_key(b"img", 2.0, 1280, 1080, 30) != base
    assert segment_key(b"img", 2.0, 1920, 720, 30) != base
    assert segment_key(b"img", 2.0, 1920, 1080, 24) != base


def test_key_is_stable_for_identical_inputs():
    assert segment_key(b"img", 2.0, 1920, 1080, 30) == segment_key(b"img", 2.0, 1920, 1080, 30)


def test_key_embeds_the_cache_version_so_a_renderer_change_invalidates_everything():
    # A cache that survives a renderer change silently ships stale frames — the worst failure mode
    # here, because the output looks fine.
    assert str(CACHE_VERSION) in segment_key(b"img", 2.0, 1920, 1080, 30)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_render_segments.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.render.segments'`

- [ ] **Step 3: Implement**

```python
# tools/render/segments.py
"""Render one still to a short mp4, cached by content hash.

Each segment is independent: identical codec parameters mean the concat demuxer can stream-copy
them together with no re-encode, and an unchanged shot is never re-rendered. This is what makes a
208-shot video usable as a development loop instead of a once-a-day event.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tools.render.ffmpeg import ffmpeg_bin

#: Bump whenever the ffmpeg arguments below change. A cache key that outlives a renderer change
#: silently serves stale video — worse than no cache, because the output looks correct.
CACHE_VERSION = 1


def segment_key(image_bytes: bytes, duration: float, width: int, height: int, fps: int) -> str:
    """Cache key covering every input that can change the rendered bytes."""
    digest = hashlib.sha256(image_bytes).hexdigest()[:32]
    return f"v{CACHE_VERSION}-{digest}-{duration:.3f}-{width}x{height}-{fps}"


def render_segment(
    image: Path,
    duration: float,
    out_dir: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> tuple[Path, bool]:
    """Render `image` held for `duration` seconds. Returns (path, was_cached)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    key = segment_key(image.read_bytes(), duration, width, height, fps)
    out = out_dir / f"seg_{key}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out, True
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps}"
    )
    subprocess.run(
        [
            ffmpeg_bin(), "-nostdin", "-v", "error", "-y",
            "-loop", "1", "-t", f"{duration:.3f}", "-i", str(image),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-g", str(fps * 2), str(out),
        ],
        check=True, capture_output=True,
    )
    return out, False
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_render_segments.py -v && uv run ruff check .`
Expected: 3 passed, ruff clean

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add tools/render/segments.py tests/test_render_segments.py
git commit -m "feat: content-hash cached per-shot segment renderer"
```

---

### Task 4.3: Assembly — concat, mux, subtitle burn

**Files:**
- Create: `tools/render/assemble.py`
- Test: `tests/test_render_assemble.py`

**Interfaces:**
- Consumes: `render_segment` (4.2), `build_ass` (4.1), `subtitle_backend`/`ffmpeg_bin` (0.1)
- Produces:
  - `MAX_PNG_OVERLAY_CUES = 50`
  - `concat_file(segments: Sequence[Path], out: Path) -> Path`
  - `assemble(shots_and_images, wav, cues, out, *, work_dir, width=1920, height=1080, fps=30) -> Path`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_render_assemble.py
from pathlib import Path

import pytest

from tools.render.assemble import MAX_PNG_OVERLAY_CUES, concat_file


def test_concat_file_quotes_paths_so_spaces_and_apostrophes_cannot_break_it(tmp_path):
    a = tmp_path / "seg one.mp4"
    b = tmp_path / "it's two.mp4"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    out = concat_file([a, b], tmp_path / "list.txt")
    text = out.read_text()
    assert text.count("file ") == 2
    # An unescaped apostrophe terminates the quoted string and corrupts the demuxer list.
    assert "it'\\''s two.mp4" in text or "it\\'s two.mp4" in text


def test_concat_file_rejects_an_empty_segment_list(tmp_path):
    with pytest.raises(ValueError, match="no segments"):
        concat_file([], tmp_path / "list.txt")


def test_png_overlay_ceiling_is_low_enough_to_stay_fast():
    # Benchmarked on M2: ~0.011 s/frame per serially chained overlay. At 50 overlays an 8-minute
    # video is already ~2 hours, so the fallback must refuse anything larger.
    assert MAX_PNG_OVERLAY_CUES <= 50
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_render_assemble.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.render.assemble'`

- [ ] **Step 3: Implement**

```python
# tools/render/assemble.py
"""Concatenate per-shot segments, mux narration, and burn subtitles in ONE pass.

Replaces `studio_poc.render_video`, which built a single filtergraph with N image inputs and M
serially chained full-frame PNG overlay nodes. Measured on this machine, that chain costs
~0.303 s/frame at depth 32, 1.391 at 128, and did not finish a 2-second output at 256. An 8-minute
video needs ~290 caption cues over 14,400 frames.

Here the segments are already rendered and stream-copy together, and every caption is one .ass
Dialogue line handled by a single libass filter.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from studio.subtitles import build_ass
from tools.render.ffmpeg import ffmpeg_bin, subtitle_backend

#: Hard ceiling for the no-libass fallback. Above this, refuse rather than start a multi-hour render.
MAX_PNG_OVERLAY_CUES = 50


def concat_file(segments: Sequence[Path], out: Path) -> Path:
    """Write an ffmpeg concat-demuxer list.

    Paths are single-quoted with embedded apostrophes escaped: an unescaped `'` terminates the
    quoted string and silently drops or corrupts entries.
    """
    if not segments:
        raise ValueError("no segments to concatenate")
    lines = []
    for seg in segments:
        escaped = str(seg.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    out.write_text("\n".join(lines) + "\n")
    return out


def assemble(
    segments: Sequence[Path],
    wav: Path,
    cues: Sequence[tuple[str, float, float]],
    out: Path,
    *,
    work_dir: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> Path:
    """Concat segments, mux `wav`, burn `cues`. Returns `out`."""
    work_dir.mkdir(parents=True, exist_ok=True)
    listing = concat_file(segments, work_dir / "concat.txt")
    backend = subtitle_backend()

    if cues and backend != "libass" and len(cues) > MAX_PNG_OVERLAY_CUES:
        raise RuntimeError(
            f"{len(cues)} caption cues but this ffmpeg has no libass, and the PNG-overlay fallback "
            f"is capped at {MAX_PNG_OVERLAY_CUES} (it costs ~0.011 s/frame per cue — this render "
            f"would take hours). Fix:\n"
            f"  brew install ffmpeg-full\n"
            f"  export FFMPEG_BIN=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg\n"
            f"Or re-run with captions disabled."
        )

    cmd = [
        ffmpeg_bin(), "-nostdin", "-v", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-i", str(wav),
    ]
    if cues and backend == "libass":
        ass = work_dir / "captions.ass"
        ass.write_text(build_ass(cues, width=width, height=height))
        # Escape for the filter-argument parser: ':' separates options, '\' escapes.
        filter_path = str(ass.resolve()).replace("\\", "\\\\").replace(":", r"\:")
        cmd += ["-vf", f"subtitles='{filter_path}'", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]  # nothing to draw → keep the segments byte-for-byte
    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_render_assemble.py -v && uv run ruff check .`
Expected: 3 passed, ruff clean

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add tools/render/assemble.py tests/test_render_assemble.py
git commit -m "feat: concat-and-burn assembler replacing the single-pass filtergraph"
```

---

### Task 4.4: Golden-fixture integration test, then swap the call site

This is the test that would have caught the 12.8-hour filtergraph. It exercises shot-plan → segment → concat → subtitle end to end with **zero API calls**.

**Files:**
- Create: `tests/fixtures/golden_run/storyboard.json`
- Create: `tests/test_render_integration.py`
- Modify: `tools/studio_poc.py` (`_assemble_video` calls the new path; delete `render_video`)
- Test: `tests/test_resume.py` (update expectations)

**Interfaces:**
- Consumes: everything from Phases 3 and 4
- Produces: `_assemble_video` unchanged in signature, new internals

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_render_integration.py
"""End-to-end assembler test with synthetic images and silent audio — no API calls, no network."""
import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from studio.narration import caption_timeline
from studio.shots import plan_shots
from studio.types import Scene
from tools.render.assemble import assemble
from tools.render.segments import render_segment


def _probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out)


@pytest.mark.integration
def test_full_assembly_from_shots_to_mp4(tmp_path):
    scenes = [
        Scene(narration="They ran. The fire spread fast.", image_prompt="p", shot_type="character"),
        Scene(narration="Nobody came back. Not one.", image_prompt="p", shot_type="wide"),
    ]
    beat_spans = [(0.0, 4.0), (4.0, 8.0)]
    shots = plan_shots(beat_spans, scenes, words_per_shot=4)
    assert len(shots) >= 4

    for i, shot in enumerate(shots):
        img = tmp_path / shot.image_key
        Image.new("RGB", (640, 360), (240 - i * 8, 238, 230)).save(img)

    segs = []
    for shot in shots:
        seg, cached = render_segment(tmp_path / shot.image_key, shot.duration, tmp_path / "segs",
                                     width=640, height=360, fps=15)
        assert cached is False
        segs.append(seg)

    # Second pass must hit the cache.
    _, cached_again = render_segment(
        tmp_path / shots[0].image_key, shots[0].duration, tmp_path / "segs",
        width=640, height=360, fps=15,
    )
    assert cached_again is True

    wav = tmp_path / "narration.wav"
    subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=mono", "-t", "8", str(wav)],
        check=True, capture_output=True,
    )

    cues = caption_timeline(beat_spans, [s.narration for s in scenes])
    out = assemble(segs, wav, cues, tmp_path / "video.mp4",
                   work_dir=tmp_path / "work", width=640, height=360, fps=15)

    assert out.exists() and out.stat().st_size > 0
    assert _probe_duration(out) == pytest.approx(8.0, abs=0.5)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_render_integration.py -v`
Expected: FAIL — the modules exist but the wiring does not yet produce a valid mp4; fix until green.

- [ ] **Step 3: Swap the production call site**

In `tools/studio_poc.py::_assemble_video`, replace the `image_timeline` + `render_video` body with
`plan_shots` → `render_segment` per shot → `assemble`. Record `stats.shots`, `stats.images_cached`,
and `stats.subtitle_backend` on the recorder. Delete `render_video`, and remove the now-unused
`scene_filter` import (`tools/studio_poc.py:51`) — `studio/kenburns.py` stays in the tree,
unreachable by design, per the no-motion constraint.

- [ ] **Step 4: Run the whole suite**

Run: `uv run pytest -q && uv run ruff check .`
Expected: all green. Update `tests/test_resume.py` where it asserted on the old assembler.

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add tests/ tools/studio_poc.py
git commit -m "refactor: assemble videos segment-wise instead of one filtergraph"
```

---

# Phase 5 — Style measurement

### Task 5.1: Style metrics and the reference envelope

**Files:**
- Create: `studio/style_metrics.py`
- Create: `context/project/style-envelope.json`
- Test: `tests/test_style_metrics.py`

**Interfaces:**
- Produces: `FrameMetrics` (frozen: `saturation`, `brightness`, `edge_density`, `near_white_pct`, `colour_bins`), `measure_frame(rgb: "np.ndarray") -> FrameMetrics`, `Envelope`, `conforms(metrics, envelope) -> tuple[bool, tuple[str, ...]]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_style_metrics.py
import numpy as np
from studio.style_metrics import Envelope, conforms, measure_frame


def _solid(rgb, size=64):
    return np.full((size, size, 3), rgb, dtype=np.uint8)


def test_pure_white_frame_is_fully_near_white_and_unsaturated():
    m = measure_frame(_solid((255, 255, 255)))
    assert m.near_white_pct == 100.0
    assert m.saturation == 0.0
    assert m.edge_density == 0.0


def test_a_two_colour_frame_reports_few_colour_bins():
    a = _solid((250, 248, 240), 32)
    b = _solid((20, 20, 20), 32)
    m = measure_frame(np.concatenate([a, b], axis=0))
    assert m.colour_bins <= 4


def test_a_saturated_frame_exceeds_the_reference_envelope():
    env = Envelope(saturation=(0.16, 0.27), colour_bins=(13, 16), near_white_pct=(29.0, 45.0))
    ok, failures = conforms(measure_frame(_solid((255, 0, 0))), env)
    assert ok is False
    assert any("saturation" in f for f in failures)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_style_metrics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.style_metrics'`

- [ ] **Step 3: Implement**

```python
# studio/style_metrics.py
"""Measure a frame's look, and compare it to the reference envelope (pure).

Turns "does the art look right?" into an assertion. Envelope values are measured in
context/research/2026-08-01/04-video-forensics.md across 5 channels and 2,703 style frames:
saturation 0.16-0.27, 13-16 distinct colour bins per frame, 29-45% near-white.

CAVEAT: these tests prove the metric MATH. They cannot prove the envelope is the right TARGET —
that rests entirely on the forensics sample. Keep the envelope as data with its provenance, so it
is cheap to re-measure rather than baked into code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    pass

_NEAR_WHITE = 235
_BIN_WIDTH = 48


class FrameMetrics(BaseModel):
    model_config = ConfigDict(frozen=True)

    saturation: float
    brightness: float
    edge_density: float
    near_white_pct: float
    colour_bins: int


class Envelope(BaseModel):
    """Inclusive (min, max) ranges the reference occupies."""

    model_config = ConfigDict(frozen=True)

    saturation: tuple[float, float]
    colour_bins: tuple[int, int]
    near_white_pct: tuple[float, float]


def measure_frame(rgb: np.ndarray) -> FrameMetrics:
    """Measure one RGB frame (H, W, 3), uint8."""
    arr = rgb.astype(np.float32)
    mx = arr.max(axis=2)
    mn = arr.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    grey = arr.mean(axis=2)
    gx = np.abs(np.diff(grey, axis=1)).mean() if grey.shape[1] > 1 else 0.0
    gy = np.abs(np.diff(grey, axis=0)).mean() if grey.shape[0] > 1 else 0.0
    quantised = (arr // _BIN_WIDTH).astype(np.int32).reshape(-1, 3)
    bins = len(np.unique(quantised, axis=0))
    return FrameMetrics(
        saturation=round(float(sat.mean()), 4),
        brightness=round(float(mx.mean() / 255.0), 4),
        edge_density=round(float((gx + gy) / 2), 3),
        near_white_pct=round(float((grey > _NEAR_WHITE).mean()) * 100, 2),
        colour_bins=int(bins),
    )


def conforms(metrics: FrameMetrics, envelope: Envelope) -> tuple[bool, tuple[str, ...]]:
    """Is this frame inside the reference envelope? Returns (ok, human-readable failures)."""
    failures: list[str] = []
    checks = (
        ("saturation", metrics.saturation, envelope.saturation),
        ("colour_bins", float(metrics.colour_bins), tuple(float(v) for v in envelope.colour_bins)),
        ("near_white_pct", metrics.near_white_pct, envelope.near_white_pct),
    )
    for name, value, (low, high) in checks:
        if not low <= value <= high:
            failures.append(f"{name} {value} outside reference {low}-{high}")
    return (not failures), tuple(failures)
```

```json
// context/project/style-envelope.json
{
  "_provenance": {
    "source": "context/research/2026-08-01/04-video-forensics.md",
    "measured": "2026-08-01",
    "channels": ["AxenCool", "Mack", "Stickly", "HistoryAlive", "ThenFolk"],
    "style_frames": 2703,
    "note": "Numbers only. Competitor media is never committed."
  },
  "saturation": [0.16, 0.27],
  "colour_bins": [13, 16],
  "near_white_pct": [29.0, 45.0]
}
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_style_metrics.py -v && uv run ruff check .`
Expected: 3 passed, ruff clean

- [ ] **Step 5: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/style_metrics.py context/project/style-envelope.json tests/test_style_metrics.py
git commit -m "feat: measure frame style against the reference envelope"
```

---

### Task 5.2: Style probe CLI and pre-flight gate

**Files:**
- Create: `tools/style_check.py`
- Modify: `tools/studio_poc.py` (pre-flight before the image loop)

- [ ] **Step 1: Implement the CLI**

```python
# tools/style_check.py
"""Fast style feedback loop: change LOCKED_STYLE, see the numbers in ~2 minutes.

  uv run python tools/style_check.py --probe            # 1 image
  uv run python tools/style_check.py --batch 12         # spread + contact sheet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from studio.style import LOCKED_STYLE, styled_prompt  # noqa: E402
from studio.style_metrics import Envelope, conforms, measure_frame  # noqa: E402
from studio.types import SHOT_TYPES  # noqa: E402

ENVELOPE_PATH = _ROOT / "context" / "project" / "style-envelope.json"
_SUBJECTS = (
    "two early humans crouched by a fire at night",
    "a wide empty tundra under a pale sky",
    "a hand axe and scattered bone fragments",
    "a simple map of a river valley",
)


def load_envelope() -> Envelope:
    raw = json.loads(ENVELOPE_PATH.read_text())
    return Envelope(
        saturation=tuple(raw["saturation"]),
        colour_bins=tuple(raw["colour_bins"]),
        near_white_pct=tuple(raw["near_white_pct"]),
    )


def check(paths: list[Path], envelope: Envelope) -> bool:
    all_ok = True
    for p in paths:
        m = measure_frame(np.asarray(Image.open(p).convert("RGB")))
        ok, failures = conforms(m, envelope)
        all_ok &= ok
        print(f"{'PASS' if ok else 'FAIL'}  {p.name}  sat={m.saturation} bins={m.colour_bins} "
              f"white={m.near_white_pct}%")
        for f in failures:
            print(f"        - {f}")
    return all_ok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true", help="one image")
    ap.add_argument("--batch", type=int, default=0, help="N images across shot types")
    ap.add_argument("--out", type=Path, default=_ROOT / "result" / "style_check")
    args = ap.parse_args()

    from tools.studio_poc import make_image_provider  # noqa: PLC0415 - avoids import cost when unused

    provider = make_image_provider("agnes")
    args.out.mkdir(parents=True, exist_ok=True)
    n = 1 if args.probe else max(args.batch, 1)
    paths: list[Path] = []
    for i in range(n):
        subject = _SUBJECTS[i % len(_SUBJECTS)]
        shot = SHOT_TYPES[i % len(SHOT_TYPES)]
        target = args.out / f"probe_{i:02d}_{shot}.png"
        provider.generate(styled_prompt(subject, LOCKED_STYLE), target)
        paths.append(target)
    sys.exit(0 if check(paths, load_envelope()) else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the probe against the current style**

Run: `uv run python tools/style_check.py --probe`
Record the numbers. This is the baseline for how far the current `LOCKED_STYLE` sits from the reference.

- [ ] **Step 3: Add the pre-flight gate**

In `tools/studio_poc.py::render_storyboard`, before the main image loop, generate the first shot's
image, measure it, and abort if it is outside the envelope — unless `--skip-style-check` is passed.
Checking after 208 images tells you the art drifted only once you have paid for it.

- [ ] **Step 4: Review and commit**

```bash
uv run pytest -q && uv run ruff check .
coderabbit review --uncommitted
git add tools/style_check.py tools/studio_poc.py
git commit -m "feat: style probe CLI and pre-flight gate before the image loop"
```

---

# Phase 6 — Throughput and native resolution

### Task 6.1: Shared token bucket for Agnes

Agnes's documented free tier is 20 rpm. Generation is currently serial, paying ~96 s of latency 208 times. Pipelined against the limit, 208 images is ~10–15 minutes.

**Files:**
- Create: `studio/rate_limit.py`
- Modify: `tools/studio_poc.py` (`AgnesImageProvider`, parallel image loop)
- Test: `tests/test_rate_limit.py`

**Interfaces:**
- Produces: `TokenBucket(rpm: int)` with `.acquire() -> None` (blocking, thread-safe)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rate_limit.py
import threading
import time

from studio.rate_limit import TokenBucket


def test_bucket_is_shared_across_threads_not_per_thread():
    # The easy bug: each worker honours its own 3s floor, so 8 workers make 160 rpm, not 20,
    # and Agnes 429s immediately. One bucket must gate them all.
    bucket = TokenBucket(rpm=60)  # 1/s
    started = time.monotonic()
    threads = [threading.Thread(target=bucket.acquire) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert time.monotonic() - started >= 2.9  # 4 acquisitions at 1/s ≥ 3s of spacing
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_rate_limit.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.rate_limit'`

- [ ] **Step 3: Implement**

```python
# studio/rate_limit.py
"""A thread-safe request spacer shared across workers.

The bug this exists to prevent: giving each worker its own minimum interval. Eight workers each
honouring a 3-second floor issue 160 requests/minute against a 20 rpm limit.
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    """Blocks until at least ``60/rpm`` seconds have passed since the previous acquisition."""

    def __init__(self, rpm: int) -> None:
        self._interval = 60.0 / max(1, rpm)
        self._lock = threading.Lock()
        self._next_at = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = max(0.0, self._next_at - now)
            self._next_at = max(now, self._next_at) + self._interval
        if wait:
            time.sleep(wait)
```

- [ ] **Step 4: Wire it in**

`AgnesImageProvider` takes a module-level shared `TokenBucket(FREE_RPM)` and calls `acquire()` before
each request, replacing the per-instance `min_interval` sleep. The image loop in `render_storyboard`
becomes a `ThreadPoolExecutor(max_workers=6)` over shots, preserving output ordering by index.

- [ ] **Step 5: Run tests, review, commit**

```bash
uv run pytest -q && uv run ruff check .
coderabbit review --uncommitted
git add studio/rate_limit.py tools/studio_poc.py tests/test_rate_limit.py
git commit -m "perf: pipeline image generation behind one shared rate limiter"
```

---

### Task 6.2: Stop upscaling every frame

`agnes.DEFAULT_SIZE = "1024x576"` upscales 1.875× to 1920×1080. Reference linework is ~3 px at native 1080p; upscaling softens exactly the thin-line signature.

- [ ] **Step 1: Find the largest supported size**

```bash
uv run python tools/style_check.py --probe   # with AGNES_SIZE=1920x1080
```

Try `1920x1080`, then `1536x864`. Record which sizes the API accepts and their latency.

- [ ] **Step 2: Set the best supported default**

Change `studio/agnes.py:21 DEFAULT_SIZE` to the largest accepted 16:9 size, and update the comment
to record what was tested and rejected.

- [ ] **Step 3: Verify edge density moved toward the reference**

Run: `uv run python tools/style_check.py --batch 4`
Expected: `edge_density` closer to the reference; no regression in saturation or colour bins.

- [ ] **Step 4: Review and commit**

```bash
coderabbit review --uncommitted
git add studio/agnes.py
git commit -m "fix: generate frames at native render resolution instead of upscaling"
```

---

# Phase 7 — Conformance acceptance test

### Task 7.1: Measure our own output against the reference

**Files:**
- Create: `tools/conformance.py`
- Test: `tests/test_conformance.py`

**Interfaces:**
- Produces: `MotionReport` (frozen: `cuts_per_min`, `frozen_pct`, `median_shot_sec`, `p10_shot_sec`, `p90_shot_sec`), `measure_video(path: Path, fps: int = 10) -> MotionReport`, `TARGETS`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_conformance.py
from tools.conformance import TARGETS, MotionReport


def test_targets_match_the_measured_axen_reference():
    assert TARGETS["cuts_per_min"] == (16.0, 18.0)
    assert TARGETS["frozen_pct"][0] >= 94.6
    assert TARGETS["median_shot_sec"] == (0.9, 4.6)


def test_report_flags_a_slideshow_that_cuts_too_slowly():
    r = MotionReport(cuts_per_min=6.5, frozen_pct=99.0, median_shot_sec=9.2,
                     p10_shot_sec=8.0, p90_shot_sec=10.0)
    assert not r.ok
    assert any("cuts_per_min" in f for f in r.failures)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_conformance.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'tools.conformance'`

- [ ] **Step 3: Implement**

`tools/conformance.py` extracts frames at 10 fps with ffmpeg, computes mean absolute inter-frame
difference, classifies each interval as hard cut (>26.0), frozen (<2.0), or motion, and derives
`cuts_per_min`, `frozen_pct`, and the shot-duration distribution. `MotionReport.ok` checks each
value against `TARGETS`:

```python
TARGETS = {
    "cuts_per_min": (16.0, 18.0),
    "frozen_pct": (94.6, 100.0),
    "median_shot_sec": (0.9, 4.6),
}
```

- [ ] **Step 4: Run against a real render**

```bash
uv run python tools/conformance.py result/axen/poc/runs/<latest>/video.mp4
```

Expected: `cuts_per_min` in 16–18, `frozen_pct` ≥ 94.6, median shot in 0.9–4.6.

- [ ] **Step 5: Review and commit**

```bash
uv run pytest -q && uv run ruff check .
coderabbit review --uncommitted
git add tools/conformance.py tests/test_conformance.py
git commit -m "test: acceptance check measuring our output against the reference"
```

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: §3 architecture → Phases 3–4; §4 components → Tasks 1.2, 2.1, 3.1, 4.1–4.3, 5.1; §5 failure modes → Tasks 0.1 (libass refusal), 4.2 (cache version), 4.3 (concat quoting, PNG ceiling), 6.1 (shared bucket); §6 testing → the L0 tests throughout, L1 in 2.2, L2/L3 in 5.2, L4 in 4.4, L5 in 7.1; §1.5 bugs → 1.1 (captions, docstring), 1.2 (settings), 6.2 (upscaling). **One spec item has no task and is deliberately deferred:** background reuse / foreground swap (§7 lists it as out of scope pending a keying spike). Reference-image generation (`assets/refs/character.png`) is likewise out of scope — `AGNES_IMG2IMG` is off because the path hangs.

**Placeholder scan.** No TBD/TODO. Every code step contains runnable code. Task 5.2 step 3, 6.1 step 4, 6.2 step 2, and 7.1 step 3 describe edits to existing functions in prose rather than full listings — these are integration points whose surrounding code the implementer will be reading anyway, and each names the exact file, function, and change.

**Type consistency.** `Shot.image_key` matches the `img_{i}.png` / `img_{i}_{k}.png` convention `image_timeline` already uses, so on-disk frame names are unchanged and resume still works. `render_segment` returns `tuple[Path, bool]` and is consumed as `(seg, cached)` in Task 4.4. `caption_timeline`'s new keyword-only `words`/`word_starts`/`word_ends` are passed in Task 1.1 step 5 and used again in 4.4. `Envelope` field names match the JSON keys in `style-envelope.json`. `score_script` returns `RubricReport`, consumed via `.ok`, `.failures`, `.summary()` in Task 2.2.

**Known risk carried from the spec:** the style envelope's validity rests entirely on the forensics sample. Unit tests prove the metric math, not that the target is right.
