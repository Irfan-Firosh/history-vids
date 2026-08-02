# Subagent kickoff prompt

Template for dispatching one fresh subagent per plan task. Fill the four `«…»` slots.

**Why it names skills explicitly:** `superpowers:using-superpowers` begins with a `<SUBAGENT-STOP>`
instructing subagents dispatched for a specific task to ignore it — so a subagent will *not*
auto-discover skills. They must be named in the prompt.

**One task per subagent.** Fresh context each time. Review between tasks.

---

## Template

```
You are implementing exactly ONE task from an existing implementation plan. Work only on that
task. Do not start the next one.

## Invoke these skills before you write anything

1. `superpowers:executing-plans` — how to work through a plan task's steps in order.
2. `superpowers:test-driven-development` — the RED/GREEN/REFACTOR cycle you must follow.

Then, as they become relevant:
- `superpowers:systematic-debugging` — the moment something fails in a way you did not expect.
  Do NOT start guessing or trying variations; invoke it and follow it.
- `superpowers:verification-before-completion` — before you report done. Non-negotiable.

Announce each skill as you invoke it.

## Repository

Path: /Users/ippu/Documents/projects/ytautomation-fr
Python is managed by `uv`. Every command is prefixed:
  uv run pytest -q              # full suite
  uv run pytest tests/X.py -v   # one file
  uv run ruff check .           # lint
NEVER `pip install`. NEVER activate the venv manually. If you need a dependency, `uv add <pkg>`.

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
- **The full suite must pass.** Baseline is «CURRENT TEST COUNT» passing. That number only goes up.
  If a pre-existing test breaks, you changed behaviour something else depended on — report it, do
  not delete or skip the test.
- **Never print, echo, or commit `.env` contents.** Reference variable NAMES only.
- **Never commit competitor media** (frames, clips, thumbnails). Measured numbers are fine.
- **No motion.** The reference measured 0% camera moves, 0% character animation, 0% dissolves.
  Do not add Ken Burns, zoompan, crossfades, or any tween, however tempting.
- Commit format: `<type>: <description>` (feat, fix, refactor, docs, test, chore, perf). No
  attribution trailer.

## Before you report done

Invoke `superpowers:verification-before-completion` and follow it. Concretely, you must have:
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
```

---

## Worked example — Task 0.1

```
You are implementing exactly ONE task from an existing implementation plan. Work only on that
task. Do not start the next one.

## Invoke these skills before you write anything

1. `superpowers:executing-plans` — how to work through a plan task's steps in order.
2. `superpowers:test-driven-development` — the RED/GREEN/REFACTOR cycle you must follow.

Then, as they become relevant:
- `superpowers:systematic-debugging` — the moment something fails in a way you did not expect.
  Do NOT start guessing or trying variations; invoke it and follow it.
- `superpowers:verification-before-completion` — before you report done. Non-negotiable.

Announce each skill as you invoke it.

## Repository

Path: /Users/ippu/Documents/projects/ytautomation-fr
Python is managed by `uv`. Every command is prefixed:
  uv run pytest -q              # full suite
  uv run pytest tests/X.py -v   # one file
  uv run ruff check .           # lint
NEVER `pip install`. NEVER activate the venv manually. If you need a dependency, `uv add <pkg>`.

## Your task

Plan file: docs/superpowers/plans/2026-08-02-shot-rate-and-render-rebuild.md
Task: Task 0.1: FFmpeg binary selection and capability probe (Phase 0)

Read the plan's `## Global Constraints` section at the top — it applies to your task even though
it is not repeated there. Then read your task's `**Files:**` and `**Interfaces:**` blocks. The
`Interfaces` block is how you learn the exact names and types neighbouring tasks depend on: match
them exactly, because another subagent is writing against them.

Work through your task's steps in order, ticking each `- [ ]` checkbox in the plan file as you
complete it.

Context specific to this task: the machine's default `ffmpeg` 8.1.2 was built WITHOUT libass,
libfreetype, or drawtext — verify that yourself with `ffmpeg -hide_banner -version`. Step 1 has you
`brew install ffmpeg-full`, which is keg-only and installs alongside without disturbing the default.

## Non-negotiable rules

[…same block as the template…]

## Before you report done

[…same block as the template…]

## Report back

[…same block as the template…]
```

---

## Dispatch order

Phases 0→7 in order. Within a phase, tasks in order.

**Phases 3 and 4 must land together**, in that order, before any real render: Phase 3 quadruples
shot count, which makes the old assembler slower than its benchmarked 12.8 hours.

After each task returns: read the report, check the produced signatures against the next task's
`Consumes` block, run `uv run pytest -q` yourself, and only then dispatch the next.
