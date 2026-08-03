# Script generator prompt — design

**Status:** approved 2026-08-03
**Problem:** 0 of 13 generated scripts pass the calibrated script rubric.
**Decision:** fix five prompt defects, add a bounded one-shot repair loop.

---

## 1. Why

The renderer rebuild (`2026-08-02-shot-rate-and-render-rebuild`) fixed the pipeline's mechanics.
Replaying the calibrated rubric (`studio/script_rubric.py`, Task 2.2) over every script the
pipeline has produced shows the mechanics were never the binding constraint on quality.

### 1.1 The measurement

All 13 storyboards under `result/`, scored with `score_script`:

```
0/13 pass
```

Failure dimensions, counted across all failures (not just the first per script):

| Count | Failure |
|---|---|
| 13/13 | short-sentence share below the 25% floor (0–13% observed) |
| 13/13 | length far under an 8-minute target |
| 7/13 | **no question mark anywhere in the script** |
| 6/13 | first question at 145–258 s, against a 45 s ceiling |
| 7/13 | `numbers_per_1k` below the 10.0 floor |
| 5/13 | second-person density below the 8.0/1k floor after 90 s |

### 1.2 Length, measured

Target for the Axen pole is ~1568 words (196 wpm × 8 min). Observed:

| | words | minutes |
|---|---|---|
| Longest | 1026 | 5.2 |
| Median | ~770 | ~3.9 |
| Shortest | 164 | 0.8 |

Nothing generated is close. The shortest would render a 50-second video.

### 1.3 Root causes — all five are in the prompt

**(a) The hook rule does not mention a question.** `SCRIPT_SYSTEM_PROMPT` asks for "an immersive
second-person hook". To a language model a *hook* is an engaging opener, not a question mark.
The rubric requires `first_question_sec <= 45`, derived from the reference channels' most
consistent convention.

**(b) The beat-sizing rule structurally forbids the target rhythm.** The prompt requires
"about 25-35 words (2-3 full sentences)" per beat and states "a one-sentence beat is too short".
That arithmetic yields uniform 10-17 word sentences. The short-form winner envelope
(`context/research/2026-08-01/05-script-craft.md` §5) is mean sentence 9.8–13.9 with 25–44% of
sentences under 8 words — a texture of very short punchy lines against occasional long ones.
The prompt actively prevents it.

**(c) The word budget is computed low and then under-delivered.** `build_script_user_prompt`
uses 183 wpm and a 6.0–9.0 minute default, giving ~1373 words. The measured Axen pole is 195.6
wpm at 8 minutes = ~1568. The budget is ~12% low *before* the model under-delivers against it.

**(d) The prompt describes an architecture that no longer exists.** It tells the model each beat
is "one held shot, ~8-16 seconds spoken". That was true under `MIN_FRAME_HOLD = 8.0`.
`studio/shots.py::plan_shots` now subdivides each beat at clause boundaries into ~2.2 s shots, so
**the script's punctuation density drives the shot rate**. Measured on the shipped planner: a
comma-dense 8-minute narration yields 221 shots at a 2.45 s median, a punctuation-sparse one
yields 156 at 3.08 s — a 40% swing driven entirely by the script's commas. Nothing in the prompt
mentions this.

**(e) Abstract topics lose their specifics.** `numbers_per_1k` by topic:

| Script | numbers/1k | digits available in its brief |
|---|---|---|
| chinese-boys-in-the-1800s | 31.4 | 1237 |
| titanic | 24.0 | 1738 |
| what-did-ancient-humans-do-all-day | **0.0** | 1000 |
| how-did-ancient-humans-survive-death | **0.0** | 1942 |

The research briefs are not thin — every one carries 900–2500 digits. Concrete-event topics use
them; abstract topics do not. The prompt's "calm, philosophical" voice pulls toward abstraction
exactly when the topic already is.

### 1.4 What is NOT the problem

- **Not the research.** Every brief carries usable numbers (§1.3e). Upstream Exa retrieval is fine.
- **Not beat size or image cost.** Verified: a ~28-word beat with Axen-style internal rhythm
  passes every rubric dimension (mean sentence 7.9, 56% short, hook at 2.4 s). Rhythm is a
  property of sentences, not of beats, so beat count and therefore image count stay ~52. The
  expensive version of this change is unnecessary.
- **Not the rubric.** It was calibrated in Task 2.2 against the real cohort: all five Axen and
  ThenFolk winners pass, both Mack underperformers and Axen UNDER 11K fail correctly, and Axen
  UNDER 9.4K is caught on second-person density.

---

## 2. Decision

Fix the five prompt defects, and add a **bounded one-shot repair loop** so a failing draft gets
one chance to correct itself against its own measured failures before the gate blocks.

Rejected: *prompt-only, no repair.* Simpler, but every miss costs a full research + generation
cycle and a manual re-run.

Rejected: *always two passes.* Doubles LLM cost on every run, including the drafts that would
have passed first time.

---

## 3. Architecture

```
topic + research brief
        |
        v
build_script_user_prompt  (pure, studio/)   <- fix (c) budget, (d) clause guidance
SCRIPT_SYSTEM_PROMPT      (pure, studio/)   <- fix (a) hook, (b) rhythm, (d) shots, (e) specifics
        |
        v
      LLM draft
        |
        v
   score_script  (pure, studio/script_rubric.py — unchanged)
        |
   ok? -+-- yes --> gate passes
        |
        no
        |
        v
build_repair_user_prompt(draft, failures)   (pure, studio/ — NEW)
        |
        v
      LLM repair  (exactly once)
        |
        v
   score_script
        |
   ok? -+-- yes --> gate passes
        |
        no --> RuntimeError (gate blocks; --skip-rubric escapes)
```

Every prompt-building function stays pure and in `studio/`. The loop, the LLM calls and all
persistence stay in `tools/make_script.py`.

---

## 4. Components

| Unit | Location | Responsibility |
|---|---|---|
| `SCRIPT_SYSTEM_PROMPT` | `studio/script_prompt.py` | The five corrected rules |
| `build_script_user_prompt` | `studio/script_prompt.py` | Per-run budget + clause guidance |
| `build_repair_user_prompt` | `studio/script_prompt.py` (**new**) | Embeds the draft and its verbatim failures |
| repair loop | `tools/make_script.py` | draft → score → one repair → score → gate |
| `score_script` | `studio/script_rubric.py` | **Unchanged.** The deterministic check |

### 4.1 The five prompt fixes

| # | Rule to write |
|---|---|
| a | The FIRST beat must contain a question mark, inside its first two sentences. Not rhetorical throat-clearing — a real question the video answers. |
| b | Replace "2-3 full sentences" with an explicit rhythm law: at least one sentence in four under 8 words; no more than one in five over 25; mean under 15. Deliberately set a 3-word line against a 20-word line. |
| c | Budget at **196 wpm**, default **8.0 minutes** → ~1568 words. |
| d | Beats are subdivided at clause boundaries into ~2.2 s shots. Commas and full stops drive the cut rate — write in clauses. Remove the stale "one held shot, ~8-16 seconds". |
| e | Every beat that can carry a concrete number, date or name from the brief must. Abstract topics need **more** concrete anchors, not fewer. |

### 4.2 The repair prompt

Takes the rejected draft and the rubric's own failure strings verbatim. They are already written
as actionable English — the real output of `score_script` on a failing draft is:

```
no question mark anywhere — the hook never asks anything
second person 0.0/1k after 90s (min 8.0)
mean sentence 30.0w (max 15.0)
only 0% short sentences (min 25%)
100% long sentences (max 22%)
numbers 0.0/1k (min 10.0)
```

Each names the metric, the observed value and the threshold, so no translation layer is needed.
The repair prompt instructs a revision fixing exactly those failures while preserving the beat
count, the cited facts, and the `cite` indices.

---

## 5. Data flow and failure modes

| Failure | Handling |
|---|---|
| Draft fails rubric | One repair pass with failures fed back |
| Repair also fails | `RuntimeError`, gate blocks. `--skip-rubric` is the informed-operator escape |
| LLM returns invalid JSON on repair | Existing JSON-parse handling; the draft is not silently substituted |
| Research brief genuinely lacks numbers | Rubric still fails `numbers_per_1k`; correct behaviour, and §1.3e shows it is not the current situation |

`rubric.json` is already persisted per run (artifact-copy fix). It gains a record of **whether the
repair pass ran**, so the first-pass hit rate is observable rather than guessed.

---

## 6. Testing

**L0 — pure, no LLM calls.** Budget arithmetic (196 wpm × 8 min → 1568). Each of the five rules is
present in the system prompt. `build_repair_user_prompt` embeds the draft and every failure string.

**L1 — the existing gate.** `score_script` is unchanged and already calibrated; the corrected
prompt is validated against it by the pipeline itself at generation time.

**Explicitly out of scope for automated testing:** asserting that a real LLM call now passes the
rubric. That is a paid, non-deterministic call; a test asserting it would be flaky and would spend
money on every suite run. The deterministic proof lives where it already lives — the rubric gate
at the spend boundary.

**Risk on the record.** A prompt rule is not a guarantee. Per this project's gate discipline, any
rule whose violation is expensive needs a deterministic check in code at the last boundary before
the cost. That check exists and blocks. This work improves the odds of passing it; it does not and
cannot enforce compliance by itself.

---

## 7. Out of scope

- Changing beat size, image count, or the image prompt (verified unnecessary, §1.4)
- Changing `score_script` or any rubric threshold (calibrated in Task 2.2)
- Regenerating the 13 existing scripts (an operational decision, not a design one)
- Upstream Exa research changes (not the problem, §1.3e)

---

## 8. Sources

- `context/research/2026-08-01/05-script-craft.md` §5 (short-form winner envelope), §13 (rules)
- `context/research/2026-08-01/04-video-forensics.md` §2.2 (shot rate), §7 (words per shot)
- `studio/script_rubric.py` — thresholds as calibrated in Task 2.2
- Measurements in §1.1–1.4 produced against the 13 storyboards in `result/` on 2026-08-03
