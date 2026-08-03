# Script Generator Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the script generator produce scripts that pass the calibrated craft rubric, by fixing five prompt defects and adding one bounded self-repair pass.

**Architecture:** Every prompt-building function stays pure and in `studio/script_prompt.py`. The LLM calls, the repair loop and all persistence stay in `tools/make_script.py`. `studio/script_rubric.py` is **not touched** — it was calibrated in Task 2.2 of the previous plan and is the deterministic gate this work aims at.

**Tech Stack:** Python 3.12, `uv`, pydantic v2 (frozen models), pytest, ruff.

## Global Constraints

- **Package manager is `uv`.** Every command is `uv run …`. Never `pip install` into `.venv`.
- **Lint:** `uv run ruff check .` must pass. Rules `E,F,I,UP,B`; **line-length 100**.
- **Tests:** `uv run pytest -q` must pass. Baseline at plan start is **302 passing**; that number only goes up.
- **Pure vs side-effecting:** anything in `studio/` has **no I/O** — no file reads, no network, no `subprocess`, no `os.environ`. I/O lives in `tools/`. Known pre-existing exception: `studio/run_log.py` writes to disk; do not touch or refactor it.
- **Immutability:** new value objects are `pydantic.BaseModel` with `model_config = ConfigDict(frozen=True)`.
- **Type annotations on every function signature.** `from __future__ import annotations` at the top of every module.
- **Never print or commit `.env` values.** Reference variable *names* only. `script_prompt.txt` is persisted per run — no credential may reach it.
- **Never commit competitor media.** Measured numbers may be committed.
- **Do not modify `studio/script_rubric.py`.** Its thresholds are calibrated; changing them to make scripts pass would invert the point of this work.
- **Commit format:** `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf). No attribution trailer.
- **Reference targets (Axen pole, short-form):** 196 wpm, 8 minutes, ~1568 words; mean sentence 9.8–13.9; ≥25% of sentences under 8 words; ≤22% over 25 words; first question ≤45 s.

**Spec:** `docs/superpowers/specs/2026-08-03-script-generator-prompt-design.md`

---

## Task Overview

| Task | Deliverable | Independently shippable? |
|---|---|---|
| **1** | Corrected system-prompt rules (hook, rhythm, shots, specifics) | Yes — prompt-only |
| **2** | Word budget at the measured Axen rate | Yes — changes length targeting |
| **3** | `build_repair_user_prompt` (pure) | Yes — unused until Task 4 |
| **4** | Bounded one-shot repair loop wired into generation | Needs Tasks 1–3 |

Tasks 1, 2 and 3 touch disjoint regions and could land in any order. Task 4 consumes Task 3.

---

### Task 1: Correct the four system-prompt rules

The hook rule never asks for a question mark; the beat-sizing rule structurally forbids short
sentences; the shot model is stale; abstract topics lose their numbers.

**Files:**
- Modify: `studio/script_prompt.py` (`SCRIPT_SYSTEM_PROMPT`, lines 37–114)
- Test: `tests/test_script_prompt.py` (create)

**Interfaces:**
- Consumes: nothing
- Produces: `SCRIPT_SYSTEM_PROMPT` — same name, same type (`str`), corrected content

- [ ] **Step 1: Write the failing test**

```python
from studio.script_prompt import SCRIPT_SYSTEM_PROMPT


def test_hook_rule_demands_an_actual_question_mark():
    # 7 of 13 generated scripts contained no question mark at all, because "hook" reads to a
    # model as "engaging opener", not "ask something". The rule must be literal.
    #
    # Do NOT assert on "question mark" alone: the prompt ALREADY contains that phrase, in the
    # image-prompt guidance ("a giant question mark" as a drawable symbol). Verified 2026-08-03 —
    # that assertion passes today and would make this test vacuous. Assert on the hook rule.
    assert "FIRST beat must contain a literal question mark" in SCRIPT_SYSTEM_PROMPT


def test_rhythm_rule_replaces_the_uniform_sentence_rule():
    # The old rule ("2-3 full sentences", "a one-sentence beat is too short") forced uniform
    # 10-17 word sentences and made the >=25% short-sentence floor unreachable.
    assert "one-sentence beat is too short" not in SCRIPT_SYSTEM_PROMPT
    assert "under 8 words" in SCRIPT_SYSTEM_PROMPT


def test_stale_held_shot_model_is_gone_and_clauses_are_explained():
    # plan_shots subdivides beats at clause boundaries into ~2.2s shots; the old prompt told the
    # model a beat was one held shot for 8-16 seconds, which stopped being true.
    assert "8-12 seconds" not in SCRIPT_SYSTEM_PROMPT
    assert "clause" in SCRIPT_SYSTEM_PROMPT.lower()


def test_specificity_rule_targets_abstract_topics():
    # numbers_per_1k measured 0.0 on abstract topics whose briefs carried 1000-1942 digits.
    assert "abstract" in SCRIPT_SYSTEM_PROMPT.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_script_prompt.py -v`
Expected: FAIL — `test_hook_rule_demands_an_actual_question_mark` fails first, since the current
prompt contains neither "question mark" nor "first beat".

- [ ] **Step 3: Replace the hook and structure rule**

In `studio/script_prompt.py`, replace the `STRUCTURE (Axen):` paragraph with:

```python
    "STRUCTURE (Axen): (1) an immersive second-person hook that ASKS A REAL QUESTION — the FIRST "
    "beat must contain a literal question mark within its first two sentences, and it must be the "
    "question the video actually answers, not rhetorical throat-clearing; (2) a reframe to scale "
    "('for ninety-nine percent of human history...'); (3) real evidence — cite findings from the "
    "RESEARCH BRIEF with [n]; (4) an emotional / existential turn; (5) a quiet payoff that "
    "lands.\n\n"
```

- [ ] **Step 4: Replace the sentence-rhythm rule**

Replace the `VOICE (narration):` paragraph's "Short, speakable sentences." with an explicit law,
and delete the uniform-sentence instruction from the `SCENES:` paragraph. New `VOICE` paragraph:

```python
    "VOICE (narration): calm, warm, philosophical, unhurried — a documentary narrator. Immersive "
    "second person ('you'). Let the real facts carry the emotion; never over-perform. End on a "
    "quiet, resonant existential payoff.\n\n"
    "SENTENCE RHYTHM (hard rule — this is the texture that separates the channels that grow from "
    "the ones that stall): vary sentence length HARD. At least one sentence in four must be under "
    "8 words. No more than one in five may run over 25 words. Mean sentence length stays under 15 "
    "words. Deliberately set a very short line against a long one — 'They were wrong. Nobody came "
    "back. The ice had already closed behind them, and it would not open again for two thousand "
    "years.' Never write a run of same-length sentences.\n\n"
```

- [ ] **Step 5: Replace the stale held-shot model in the SCENES paragraph**

Replace the opening of the `SCENES:` paragraph (through "...many tiny ones, because each image
stays on screen for the whole beat.") with:

```python
    "SCENES: split the script into beats. Size beats by WORD COUNT: about 25-35 words each. A beat "
    "is NOT one held shot — the renderer subdivides every beat at CLAUSE boundaries into roughly "
    "2.2-second shots, so your commas and full stops are what drive the cut rate. Write in clear "
    "clauses and the pacing follows; write one long unbroken clause and the picture sits still too "
    "long. Sentence rhythm above is what controls this. For each beat provide:\n"
```

- [ ] **Step 6: Add the specificity rule**

Append after the `CREDIBILITY` paragraph:

```python
    "CONCRETE ANCHORS (hard rule): every beat that CAN carry a real number, date, place or name "
    "from the brief must carry one. Abstract or philosophical topics need MORE concrete anchors, "
    "not fewer — a script about what ancient humans did all day still needs the dig site, the "
    "year, the count of hearths. Vagueness is the failure mode on exactly these topics.\n\n"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_script_prompt.py -v`
Expected: PASS (4 tests)

- [ ] **Step 8: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 306 passing, lint clean.

- [ ] **Step 9: Commit**

```bash
git add studio/script_prompt.py tests/test_script_prompt.py
git commit -m "fix: prompt rules that fought the craft rubric"
```

---

### Task 2: Budget the script at the measured Axen rate

The budget is computed at 183 wpm over a 6–9 minute band (~1372 words). The measured Axen pole is
195.6 wpm at 8 minutes (~1568 words) — the budget is ~12% low before the model under-delivers.

**Files:**
- Modify: `tools/make_script.py` (`WORDS_PER_MINUTE` line 306, `WORDS_PER_BEAT` docstring lines 308–312, CLI defaults lines 418–419, `build_and_save` signature line 337)
- Modify: `studio/script_prompt.py` (`build_script_user_prompt` default `min_minutes`/`max_minutes`)
- Test: `tests/test_studio.py`

**Interfaces:**
- Consumes: nothing
- Produces: `WORDS_PER_MINUTE = 196.0`; `target_words(7.5, 8.5) -> 1568`; `scenes_for_minutes(7.5, 8.5) -> 52`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_studio.py`:

```python
def test_word_budget_uses_the_measured_axen_speaking_rate():
    # 04-video-forensics.md section 7: Axen speaks 195.6 wpm. The old 183.0 under-budgeted every
    # script by ~12% before the model under-delivered against it.
    from tools.make_script import WORDS_PER_MINUTE, scenes_for_minutes, target_words

    assert WORDS_PER_MINUTE == 196.0
    assert target_words(7.5, 8.5) == 1568       # 8 min at the measured rate
    assert scenes_for_minutes(7.5, 8.5) == 52   # 1568 words / 30 words per beat
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_studio.py::test_word_budget_uses_the_measured_axen_speaking_rate -v`
Expected: FAIL — `assert 183.0 == 196.0`

- [ ] **Step 3: Change the rate and correct the stale beat docstring**

In `tools/make_script.py`, replace lines 306–312:

```python
WORDS_PER_MINUTE = 196.0  # measured: Axen 195.6 wpm (04-video-forensics.md section 7)

#: Words of narration per beat. A beat is NOT one held shot — ``studio.shots.plan_shots``
#: subdivides each beat at clause boundaries into ~2.2s shots, so this controls how many IMAGES a
#: run generates, not the cut rate. ~30 words keeps image count near 52 for an 8-minute script.
#: Sizing goes through words, not seconds: the model cannot judge spoken duration but can count.
WORDS_PER_BEAT = 30
```

- [ ] **Step 4: Move the default band to the Axen pole**

In `tools/make_script.py`, change the CLI defaults (lines 418–419) and `build_and_save`'s
signature (line 337) from `6.0`/`9.0` to `7.5`/`8.5`:

```python
    ap.add_argument("--min-minutes", type=float, default=7.5)
    ap.add_argument("--max-minutes", type=float, default=8.5)
```

```python
def build_and_save(
    topic: str, scenes: int | None = None, min_minutes: float = 7.5, max_minutes: float = 8.5,
    log=print, skip_rubric: bool = False,
) -> Path:
```

In `studio/script_prompt.py`, change `build_script_user_prompt`'s defaults to match:

```python
def build_script_user_prompt(
    topic: str, research_brief: str, num_scenes: int,
    min_minutes: float = 7.5, max_minutes: float = 8.5,
    total_words: int | None = None, words_per_beat: int = 30,
) -> str:
```

Also update its docstring's `183` to `196` and change the stale
`"(each one held shot, ~8-16 seconds spoken)"` in the returned TARGET line to
`"(each beat is subdivided into ~2.2s shots at clause boundaries)"`.

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/test_studio.py::test_word_budget_uses_the_measured_axen_speaking_rate -v`
Expected: PASS

- [ ] **Step 6: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 307 passing, lint clean. If a pre-existing test asserted the old 183.0 rate or the
6–9 minute band, update the expected VALUE only — do not weaken the assertion.

- [ ] **Step 7: Commit**

```bash
git add tools/make_script.py studio/script_prompt.py tests/test_studio.py
git commit -m "fix: budget scripts at the measured 196 wpm Axen rate"
```

---

### Task 3: The repair prompt builder

A pure function that turns a rejected draft plus its measured failures into a revision request.

**Files:**
- Modify: `studio/script_prompt.py` (add `build_repair_user_prompt`)
- Test: `tests/test_script_prompt.py`

**Interfaces:**
- Consumes: nothing
- Produces: `build_repair_user_prompt(draft_json: str, failures: Sequence[str]) -> str`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_script_prompt.py`:

```python
from studio.script_prompt import build_repair_user_prompt


def test_repair_prompt_embeds_the_draft_and_every_failure_verbatim():
    draft = '{"title": "T", "scenes": [{"narration": "A long flat line.", "cite": []}]}'
    failures = ("no question mark anywhere — the hook never asks anything",
                "mean sentence 30.0w (max 15.0)")
    out = build_repair_user_prompt(draft, failures)
    assert draft in out
    for f in failures:
        assert f in out, f"failure not passed through: {f}"


def test_repair_prompt_protects_beat_count_and_citations():
    # A repair that drops beats changes the image count, and one that drops cite indices breaks
    # the grounding gate that already passed. Both must survive the revision.
    out = build_repair_user_prompt("{}", ["mean sentence 30.0w (max 15.0)"])
    assert "same number of beats" in out.lower()
    assert "cite" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_script_prompt.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_repair_user_prompt'`

- [ ] **Step 3: Write the implementation**

Append to `studio/script_prompt.py`:

```python
def build_repair_user_prompt(draft_json: str, failures: Sequence[str]) -> str:
    """Ask for one revision of a draft that failed the craft rubric.

    The rubric's failure strings already name the metric, the observed value and the threshold
    ("mean sentence 30.0w (max 15.0)"), so they are passed through verbatim — a translation layer
    would only lose information. The revision must preserve the beat count (it sets the image
    count) and the `cite` indices (the grounding gate already passed on them).
    """
    bullets = "\n".join(f"  - {f}" for f in failures)
    return (
        "The script below was REJECTED by the craft rubric. Rewrite it so it passes, changing "
        "only what the failures demand.\n\n"
        f"MEASURED FAILURES:\n{bullets}\n\n"
        "RULES FOR THE REVISION:\n"
        "  - Keep the SAME NUMBER OF BEATS, in the same order, on the same facts.\n"
        "  - Keep every beat's `cite` list exactly as it is — those indices are already verified.\n"
        "  - Keep `image_prompt` and `shot_type` unchanged unless the narration change makes a "
        "shot type wrong.\n"
        "  - Fix the narration only. If a failure names a sentence-length or short-sentence "
        "target, break long sentences apart and add genuinely short ones; do not pad.\n"
        "  - If a failure says the hook never asks anything, put a real question mark in the "
        "FIRST beat's opening sentences.\n"
        "  - If a failure names a word count, hit it — do not shorten the script to fix rhythm.\n\n"
        f"REJECTED DRAFT:\n{draft_json}\n\n"
        "Return the corrected script as the same strict JSON object, no prose, no markdown fences."
    )
```

**`Sequence` is NOT currently imported in `studio/script_prompt.py`** — verified 2026-08-03, the
file's only import is `from __future__ import annotations`. Add this line below it:

```python
from collections.abc import Sequence
```

Ruff's `I` rule sorts imports; `from __future__` stays first, so this goes directly after it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_script_prompt.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 309 passing, lint clean.

- [ ] **Step 6: Commit**

```bash
git add studio/script_prompt.py tests/test_script_prompt.py
git commit -m "feat: prompt builder for a rubric repair pass"
```

---

### Task 4: Wire the bounded repair loop

One repair attempt, before the callout pass so callouts are computed on the final text.

**Files:**
- Modify: `tools/make_script.py` (`LLMScriptProvider.generate` around line 203, add `_repair_if_needed`)
- Test: `tests/test_studio.py`

**Interfaces:**
- Consumes: `build_repair_user_prompt(draft_json, failures)` from Task 3; `score_script` from `studio/script_rubric.py`
- Produces: `LLMScriptProvider.repair_ran: bool` — True when a repair pass was issued

- [ ] **Step 1: Write the failing test**

Append to `tests/test_studio.py`:

```python
def test_generate_repairs_a_failing_draft_exactly_once(monkeypatch):
    # The rubric gate already blocks a bad script. Without a repair pass, every miss costs a full
    # research + generation cycle and a manual re-run. One pass, then the gate.
    from tools.make_script import LLMScriptProvider

    # Build dicts directly — `json` is NOT imported in this test file (verified 2026-08-03) and
    # the implementation serialises the draft itself, so a dict is the honest input here.
    #
    # 16 beats, not 8. `second_person_after_90s_per_1k` measures the region AFTER 90 seconds, so a
    # fixture under ~294 words (90s at 196 wpm) has no such region and scores 0.0 no matter how
    # much second person it contains. 8 beats x 25 words = 200 words = 61s and fails for that
    # reason alone. This exact trap already shipped once in this project's plans — verified
    # 2026-08-03 that 16 beats passes and 8 does not.
    bad = {"title": "T", "scenes": [
        {"narration": " ".join(["word"] * 30) + ".", "image_prompt": "x",
         "shot_type": "concept", "cite": []} for _ in range(16)]}
    good_text = (
        '{"title": "T", "scenes": [' + ",".join(
            '{"narration": "Why did they go? You would have gone too. In 1908 a team found 40 '
            'hearths, each one still ringed with stones you could count.", "image_prompt": "x", '
            '"shot_type": "concept", "cite": []}' for _ in range(16)) + "]}"
    )

    calls = []

    def fake_chat(self, system, user):
        calls.append(user)
        return good_text

    monkeypatch.setattr(LLMScriptProvider, "_chat", fake_chat)
    p = LLMScriptProvider.__new__(LLMScriptProvider)
    p.repair_ran = False
    data = p._repair_if_needed(bad, log=lambda *a: None)

    assert p.repair_ran is True
    assert len(calls) == 1, "exactly one repair pass, never a loop"
    assert "?" in " ".join(s["narration"] for s in data["scenes"])


def test_generate_does_not_repair_a_passing_draft(monkeypatch):
    from tools.make_script import LLMScriptProvider

    good_scenes = [{
        "narration": "Why did they go? They went. In 1908 a team found 40 hearths, each one "
                     "still ringed with stones you could count.",
        "image_prompt": "x", "shot_type": "concept", "cite": [],
    } for _ in range(8)]

    def fake_chat(self, system, user):
        raise AssertionError("must not call the LLM when the draft already passes")

    monkeypatch.setattr(LLMScriptProvider, "_chat", fake_chat)
    p = LLMScriptProvider.__new__(LLMScriptProvider)
    p.repair_ran = False
    data = p._repair_if_needed({"title": "T", "scenes": good_scenes}, log=lambda *a: None)

    assert p.repair_ran is False
    assert data["scenes"] == good_scenes
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_studio.py -k repair -v`
Expected: FAIL with `AttributeError: 'LLMScriptProvider' object has no attribute '_repair_if_needed'`

- [ ] **Step 3: Write the implementation**

In `tools/make_script.py`, add the import alongside the existing `script_prompt` imports:

```python
from studio.script_prompt import build_repair_user_prompt
```

Add the method to `LLMScriptProvider`:

```python
    def _repair_if_needed(self, data: dict, log) -> dict:
        """One revision pass when a draft fails the craft rubric. Returns the data to use.

        Runs BEFORE the callout pass so callouts are chosen on the final text. Exactly one attempt:
        if the repair also fails, `build_and_save`'s gate refuses the render, which is the
        deterministic check. A garbled repair degrades to the original draft rather than aborting —
        the gate still gets the last word.
        """
        scenes = data.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            return data
        report = score_script([s.get("narration", "") for s in scenes])
        if report.ok:
            return data
        log(f"rubric: draft failed ({len(report.failures)} issues) — one repair pass")
        user = build_repair_user_prompt(json.dumps(data, ensure_ascii=False), report.failures)
        self.repair_ran = True
        try:
            repaired = llm.parse_json_block(self._chat(SCRIPT_SYSTEM_PROMPT, user))
        except Exception as exc:  # noqa: BLE001 — a bad repair must not lose the draft
            log(f"  ⚠ repair pass failed to parse ({exc}); keeping the original draft")
            return data
        if not isinstance(repaired.get("scenes"), list) or not repaired["scenes"]:
            log("  ⚠ repair pass returned no beats; keeping the original draft")
            return data
        _strip_inline_citations(repaired)
        after = score_script([s.get("narration", "") for s in repaired["scenes"]])
        log(f"  repair: {after.summary()}")
        return repaired
```

Initialise the flag in `LLMScriptProvider.__init__`, beside `self.last_prompt`:

```python
        self.repair_ran = False  # did a rubric repair pass run on the last generate()?
```

Call it in `generate`, between `_strip_inline_citations(data)` and `self._apply_callout_analysis(data)`:

```python
        _strip_inline_citations(data)
        data = self._repair_if_needed(data, log=print)
        self._apply_callout_analysis(data)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/test_studio.py -k repair -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Record whether the repair ran**

`rubric.json` is currently written at `tools/make_script.py:410` as:

```python
    (out / "rubric.json").write_text(rubric_report.model_dump_json(indent=2))
```

`model_dump_json` cannot carry an extra key, so replace that exact line with:

```python
    (out / "rubric.json").write_text(json.dumps(
        {**rubric_report.model_dump(), "repair_ran": provider.repair_ran}, indent=2
    ))
```

`json` is already imported at `tools/make_script.py:14`.

**Check the dashboard still parses it.** `GET /api/runs/{id}/rubric` reads this file. Adding a key
should be additive, but run `uv run pytest tests/test_dashboard.py -q` and confirm. `model_dump()`
returns only pydantic *fields* — `ok` is a property, so it is absent from both the old and new
output; do not "fix" that as a drive-by, it is pre-existing and the endpoint already handles it.

- [ ] **Step 6: Run the full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 311 passing, lint clean.

- [ ] **Step 7: Commit**

```bash
git add tools/make_script.py tests/test_studio.py
git commit -m "feat: one repair pass when a draft fails the craft rubric"
```

---

## Verification

This plan cannot prove a real LLM now passes the rubric — that is a paid, non-deterministic call,
and a test asserting it would be flaky and would spend money on every suite run. The deterministic
proof stays where it already is: `build_and_save`'s rubric gate, before any image or TTS spend,
with `--skip-rubric` as the informed-operator escape.

What this plan does prove: the prompt no longer contains rules that make the rubric unreachable,
the budget matches the measured speaking rate, and a failing draft gets exactly one measured,
targeted repair attempt before the gate refuses it.

**The honest check after landing:** run one real topic end to end and read `rubric.json`. If
`repair_ran` is false and `ok` is true, the prompt fix did the work. If `repair_ran` is true more
often than not, the prompt still needs tightening and the loop is masking it.
