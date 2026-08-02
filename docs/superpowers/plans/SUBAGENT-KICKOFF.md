# Subagent kickoff prompt

Template for dispatching one fresh subagent per plan task. Fill the two `«…»` slots.

**Why it names skills explicitly:** `superpowers:using-superpowers` begins with a `<SUBAGENT-STOP>`
instructing subagents dispatched for a specific task to ignore it — so a subagent will *not*
auto-discover skills. They must be named in the prompt, in slash form.

**One task per subagent.** Fresh context each time. Review between tasks.

**To reuse for a later task, change only two things:** the `Task:` line, and the baseline count in
the "full suite must pass" rule (196 → whatever the previous task ended at).

---

## Template

````
You are implementing exactly ONE task from an existing implementation plan. Work only on that
task. Do not start the next one.

## Invoke these skills before you write anything

1. `/superpowers:executing-plans` — how to work through a plan task's steps in order.
2. `/superpowers:test-driven-development` — the RED/GREEN/REFACTOR cycle you must follow.

Then, as they become relevant:
- `/superpowers:systematic-debugging` — the moment something fails in a way you did not expect.
  Do NOT start guessing or trying variations; invoke it and follow it.
- `/superpowers:verification-before-completion` — before you report done. Non-negotiable.

Announce each skill as you invoke it.

## Repository

Path: /Users/ippu/Documents/projects/ytautomation-fr
Python is managed by `uv`. Every command is prefixed:
  uv run pytest -q              # full suite
  uv run pytest tests/X.py -v   # one file
  uv run ruff check .           # lint
NEVER `pip install`. NEVER activate the venv manually. If you need a dependency, `uv add <pkg>`.
Confirm the suite is at «BASELINE COUNT» passing before you touch anything; if it is not, stop and
report rather than building on a broken base.

## Your task

Plan file: docs/superpowers/plans/2026-08-02-shot-rate-and-render-rebuild.md
Task: «TASK NUMBER AND NAME, e.g. "Task 0.1: FFmpeg binary selection and capability probe"»

Read the plan's `## Global Constraints` section at the top — it applies to your task even though
it is not repeated there. Then read your task's `**Files:**` and `**Interfaces:**` blocks. The
`Interfaces` block is how you learn the exact names and types neighbouring tasks depend on: match
them exactly, because another subagent is writing against them.

Work through your task's steps in order, ticking each `- [ ]` checkbox in the plan file as you
complete it.

## Non-negotiable rules

- **Write the failing test FIRST and actually run it to watch it fail.** A test that has never
  been red proves nothing. If it passes before you write the implementation, the test is wrong —
  fix the test, do not proceed.
- **Never weaken a test to make it pass.** If a test fails, the implementation is wrong until you
  have proven otherwise. Changing an assertion to match broken behaviour is the one thing that
  makes this whole plan worthless.
- **`studio/` is PURE.** No file I/O, no network, no `subprocess`, no `os.environ` reads. Frozen
  pydantic models (`model_config = ConfigDict(frozen=True)`). Side effects live in `tools/`.
  If your task adds I/O to a `studio/` module, you have misread it — stop and report.
- **Do not refactor anything your task does not name.** No opportunistic cleanups, no renaming,
  no reformatting untouched files.
- **Line length 100.** `uv run ruff check .` must pass before you commit.
- **The full suite must pass.** Baseline is «BASELINE COUNT» passing. That number only goes up.
  If a pre-existing test breaks, you changed behaviour something else depended on — report it, do
  not delete or skip the test.
- **Never print, echo, or commit `.env` contents.** Reference variable NAMES only.
- **Never commit competitor media** (frames, clips, thumbnails). Measured numbers are fine.
- **No motion.** The reference measured 0% camera moves, 0% character animation, 0% dissolves.
  Do not add Ken Burns, zoompan, crossfades, or any tween, however tempting.
- Commit format: `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf). No
  attribution trailer.

## Before you report done

Invoke `/superpowers:verification-before-completion` and follow it. Concretely, you must have:
- run `uv run pytest -q` and seen it pass, and be able to quote the count
- run `uv run ruff check .` and seen it clean
- ticked every `- [ ]` in your task
- committed

## Report back

Keep it under 300 words:
1. What you built, and the exact signatures you produced (so I can check them against the next
   task's `Consumes` block).
2. The test count before and after, quoted from real output.
3. Anything in the plan that was wrong, ambiguous, or that you had to deviate from — and why.
   This matters more than the code. A plan error found now saves the next five tasks.
4. Anything you noticed but deliberately did NOT fix because it was out of scope.

Do not pad. Do not claim anything you have not run.
````

---

## Worked example — Task 0.1 (paste-ready, the first dispatch)

````
You are implementing exactly ONE task from an existing implementation plan. Work only on that
task. Do not start the next one.

## Invoke these skills before you write anything

1. `/superpowers:executing-plans` — how to work through a plan task's steps in order.
2. `/superpowers:test-driven-development` — the RED/GREEN/REFACTOR cycle you must follow.

Then, as they become relevant:
- `/superpowers:systematic-debugging` — the moment something fails in a way you did not expect.
  Do NOT start guessing or trying variations; invoke it and follow it.
- `/superpowers:verification-before-completion` — before you report done. Non-negotiable.

Announce each skill as you invoke it.

## Repository

Path: /Users/ippu/Documents/projects/ytautomation-fr
Python is managed by `uv`. Every command is prefixed:
  uv run pytest -q              # full suite
  uv run pytest tests/X.py -v   # one file
  uv run ruff check .           # lint
NEVER `pip install`. NEVER activate the venv manually. If you need a dependency, `uv add <pkg>`.
The venv is current and working — `uv run pytest -q` should show 196 passing before you touch
anything. Confirm that first; if it does not, stop and report rather than building on a broken base.

## Your task

Plan file: docs/superpowers/plans/2026-08-02-shot-rate-and-render-rebuild.md
Task: Task 0.1: FFmpeg binary selection and capability probe (Phase 0) — the FIRST task in the plan

Read the plan's `## Global Constraints` section at the top — it applies to your task even though
it is not repeated there. Then read your task's `**Files:**` and `**Interfaces:**` blocks. The
`Interfaces` block is how you learn the exact names and types neighbouring tasks depend on: match
them exactly, because another subagent is writing against them.

Work through your task's steps in order, ticking each `- [ ]` checkbox in the plan file as you
complete it. This task has 6 steps, and Step 1 is a `brew install ffmpeg-full` — that installation
is expected and authorised. It is keg-only, so it installs alongside the existing ffmpeg without
replacing it; do not `brew link` it or disturb the default `ffmpeg` on PATH.

Context for this task: the machine's default ffmpeg 8.1.2 was built WITHOUT libass, libfreetype,
or drawtext. Verify that yourself with `ffmpeg -hide_banner -version` before installing anything —
if it already has libass, say so, because that changes what later phases need.

## Non-negotiable rules

- **Write the failing test FIRST and actually run it to watch it fail.** A test that has never
  been red proves nothing. If it passes before you write the implementation, the test is wrong —
  fix the test, do not proceed.
- **Never weaken a test to make it pass.** If a test fails, the implementation is wrong until you
  have proven otherwise. Changing an assertion to match broken behaviour is the one thing that
  makes this whole plan worthless.
- **`studio/` is PURE.** No file I/O, no network, no `subprocess`, no `os.environ` reads. Frozen
  pydantic models (`model_config = ConfigDict(frozen=True)`). Side effects live in `tools/`.
  If your task adds I/O to a `studio/` module, you have misread it — stop and report.
  (Your task creates `tools/render/`, which is side-effecting by design. That is correct.)
- **Do not refactor anything your task does not name.** No opportunistic cleanups, no renaming,
  no reformatting untouched files.
- **Line length 100.** `uv run ruff check .` must pass before you commit.
- **The full suite must pass.** Baseline is 196 passing. That number only goes up. If a
  pre-existing test breaks, you changed behaviour something else depended on — report it, do
  not delete or skip the test.
- **Never print, echo, or commit `.env` contents.** Reference variable NAMES only.
- **Never commit competitor media** (frames, clips, thumbnails). Measured numbers are fine.
- **No motion.** The reference measured 0% camera moves, 0% character animation, 0% dissolves.
  Do not add Ken Burns, zoompan, crossfades, or any tween, however tempting.
- Commit format: `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf). No
  attribution trailer.

## Before you report done

Invoke `/superpowers:verification-before-completion` and follow it. Concretely, you must have:
- run `uv run pytest -q` and seen it pass, and be able to quote the count
- run `uv run ruff check .` and seen it clean
- ticked every `- [ ]` in your task
- committed

## Report back

Keep it under 300 words:
1. What you built, and the exact signatures you produced (so I can check them against the next
   task's `Consumes` block).
2. The test count before and after, quoted from real output.
3. Anything in the plan that was wrong, ambiguous, or that you had to deviate from — and why.
   This matters more than the code. A plan error found now saves the next five tasks.
4. Anything you noticed but deliberately did NOT fix because it was out of scope.
5. The exact `FFMPEG_BIN` path that works, and whether `subtitle_backend()` returns "libass" —
   Phase 4 depends on this and I need the literal value.

Do not pad. Do not claim anything you have not run.
````

---

## Dispatch order

Phases 0→7 in order. Within a phase, tasks in order.

**Phases 3 and 4 must land together**, in that order, before any real render: Phase 3 quadruples
shot count, which makes the old assembler slower still.

After each task returns: read the report, check the produced signatures against the next task's
`Consumes` block, run `uv run pytest -q` yourself, and only then dispatch the next.

### Per-task additions worth making

The template is generic; some tasks deserve an extra line or two:

| Task | Add |
|---|---|
| 0.1 | The `brew install` authorisation and the request for the literal `FFMPEG_BIN` value (see example above) |
| 2.2 | "Run the calibration and paste the real pass/fail table before wiring the gate. If any known-winner script fails, the threshold is wrong — fix it and re-run." |
| 3.1 + 4.x | "Do not run a full render between Phase 3 and the end of Phase 4." |
| 4.4 | "This deletes `render_video`. Confirm no other caller exists before removing it." |
| 6.2 | "Report which `AGNES_SIZE` values the API accepted and which it rejected, with latency for each." |
