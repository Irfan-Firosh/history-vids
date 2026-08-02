
## Workflow Orchestration

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes — don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests — then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

### 7. Frontend Design
- Use the shadcn MCP server (`mcp__shadcn__*`) when selecting/installing components
- Use the magicui MCP server (`mcp__magicui__*`) for animations and special effects
- Use `mcp__magic__21st_magic_component_builder` for creative component inspiration
- **Visual review — automatic Chrome**: After building any UI, automatically invoke `/chrome` to open Chrome and navigate to `localhost:3000`. Do NOT ask the user to do anything manually — Claude opens Chrome, takes screenshots, reads console, verifies dark/light mode, and iterates, all within the session.
- Use Playwright E2E tests ONLY for critical user flows (auth, checkout, core CRUD) — not design review
- Follow `~/.claude/FRONTEND_DESIGN.md` for all design decisions
- Always implement dark/light mode with next-themes + CSS variables
- Stack: Next.js 15 App Router + Tailwind v4 + shadcn/ui + magicui + Geist fonts

### 9. Automatic Skill Selection
The following skills are available and should be chosen automatically — never wait for the user to invoke them:
- Building a new component → use `/new-component` skill
- Adding a FastAPI endpoint → use `/new-route` skill
- Setting up a new project's design → use `/design-init` skill
- FastAPI schema changed → use `/api-sync` skill
- Full feature (frontend + backend) → use `/full-stack` skill
- After significant work session → suggest `/evolve [topic]` to capture learnings
- Code just written → invoke `code-reviewer` agent
- New feature requested → invoke `planner` agent first
- Auth/payments touched → invoke `security-reviewer` agent

### 8. Dynamic Skill Evolution
- After completing significant features: suggest running `/evolve [topic]` to capture learnings
- After ANY correction: update `tasks/lessons.md` with the specific pattern
- Agents self-improve: every agent has a `## Learned Patterns` section that grows over time
- Run `/evolve all` periodically (weekly) to do a comprehensive skill update

### 10. ECC Skill & Agent Routing (USE THESE — don't wait to be asked)
Prefer the namespaced **`ecc:*`** plugin skills/agents wherever they fit. They are first-class — invoke
them automatically when a trigger below matches. When an `ecc:*` and a bare version both exist, prefer `ecc:*`.

**The important ones (use constantly):**
| Trigger | Use |
|---|---|
| Any non-trivial task, before code | `ecc:plan` (restate reqs + step plan, wait for confirm) |
| Multi-session / multi-PR effort | `ecc:blueprint` then `ecc:architect` agent |
| "How do I use <lib/framework/API>?" | `ecc:documentation-lookup` / Context7 — never answer libs from memory |
| Research / prior art / competitive intel | `ecc:search-first` → `ecc:deep-research` / `ecc:exa-search` / `ecc:market-research` |
| Any code written or modified | `ecc:code-review` (diff) + the language reviewer agent |
| Python code | `ecc:python-review` → `ecc:python-reviewer`; patterns: `ecc:python-patterns`, tests: `ecc:python-testing` |
| TS/JS code | `ecc:typescript-reviewer`; Go/Rust/Java/Kotlin/C++/Flutter → matching `ecc:*-review` + `ecc:*-build` resolver |
| New feature / bug fix / refactor | `ecc:tdd` (write tests first, 80%+) |
| Before "done" | `ecc:verify` (verification-loop) — prove it runs, don't just claim |
| Auth / payments / user input / secrets / endpoints | `ecc:security-review` → `ecc:security-reviewer` |
| Build / type errors | `ecc:*-build` resolver agent for the language |
| Long session / phase boundary | `ecc:strategic-compact`; watch budget with `ecc:context-budget` |
| Commit / PR | `ecc:git-workflow`, `ecc:prp-commit`, `ecc:prp-pr` |
| Capture learnings / corrections | `ecc:learn-eval`, `ecc:evolve`; persist with `ecc:save-session` / `ecc:resume-session` |

**Domain skills — reach for them when relevant:**
- **LLM / agent pipelines:** `ecc:cost-aware-llm-pipeline`, `ecc:agent-harness-construction`,
  `ecc:content-hash-cache-pattern`, `ecc:regex-vs-llm-structured-text`, `ecc:iterative-retrieval`,
  `ecc:eval-harness`, `ecc:claude-api`. (Use these for any rate-limited / multi-agent / RAG / judge work.)
- **Backend:** `ecc:backend-patterns`, `ecc:api-design`, `ecc:postgres-patterns`, `ecc:database-migrations`.
- **Frontend:** `ecc:frontend-design`, `ecc:frontend-patterns`, `ecc:design-system`.
- **Video / media:** `ecc:video-editing`, `ecc:remotion-video-creation`, `ecc:fal-ai-media`, `ecc:manim-video`.
- **Content / distribution:** `ecc:content-engine`, `ecc:crosspost`, `ecc:seo`, `ecc:x-api`.
- **Orchestration:** `ecc:orchestrate` / `ecc:dmux-workflows` / `ecc:autonomous-agent-harness` for parallel agents.

Rule: if a matching `ecc:*` skill exists for what you're about to do, invoke it instead of improvising.

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## GITHUB MANAGEMENT
1. **Inital**: alway make the project a git project always make sure u get the correct project.
2. **Pre Commit**: Before every commit run `uv run pytest -q` and `uv run ruff check .`, then
   invoke `superpowers:verification-before-completion`. For non-trivial changes also invoke
   `superpowers:requesting-code-review`. Never claim a task done on unrun tests.

## Planning Architecture

Work flows **research → spec → plan → phases → tasks → TDD steps**. Each stage has one home and
one gate. Do not skip forward: a plan without a spec, or a spec without evidence, is a guess.

### Where artifacts live

| Artifact | Path | Written by |
|---|---|---|
| Research findings | `context/research/YYYY-MM-DD/NN-<topic>.md` | parallel subagents; one file per domain |
| Design spec | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` | `superpowers:brainstorming` |
| Implementation plan | `docs/superpowers/plans/YYYY-MM-DD-<feature>.md` | `superpowers:writing-plans` |
| Durable project state | `context/project/` | decisions that outlive one feature |
| Measured targets | `context/project/*.json` | numbers only — never competitor media |
| Session todo | `tasks/todo.md` | in-flight checklist + review section |
| Lessons | `tasks/lessons.md` | after ANY correction, dated, with the rule |

### Plan structure

Plans are organised into **phases**, each ending in working, testable software that could ship
alone. Within a phase, a **task** is the smallest unit carrying its own test cycle — the unit a
reviewer could reject without rejecting its neighbour. Within a task, every **step** is one 2–5
minute action, and code steps contain real runnable code, never a description of code.

Every plan opens with a **Global Constraints** block: version floors, lint rules, layer rules, and
domain invariants copied verbatim from the spec. Every task implicitly inherits it.

Order dependencies explicitly. If two phases must land together, say so and say why.

### Layer separation (this repo's core invariant)

- `studio/` — **pure**. No file I/O, no network, no `subprocess`. Frozen pydantic models. This is
  what makes the logic fast to test and safe to reason about.
- `tools/` — side-effecting: providers, ffmpeg, orchestration, CLIs.
- `dashboard/` — FastAPI control plane; spawns detached subprocesses, never does pipeline work.

A new module goes in `studio/` if it can. Reach for `tools/` only when it genuinely touches the
outside world.

### Gates

- **Gates run immediately before the spend they protect**, not after. Checking output quality after
  paying for 208 images tells you too late.
- **A prompt rule is not a guarantee.** Any rule whose violation is expensive (a paid render) or
  audible (TTS) needs a deterministic check in code at the last boundary before the cost.
- **Calibrate before enforcing.** Replay a new threshold over the real corpus on disk and show it
  refuses the known-bad and passes the known-good. A threshold you haven't replayed is a guess.
- **Gates are escapable by an informed operator** (`--skip-*`), never by accident.

### Evidence standards

- **Measure, don't assert.** A claim about performance, cost, or behaviour needs a number you
  produced. Benchmark before declaring something a bottleneck.
- **Cite `file.py:line`** for claims about this codebase.
- **Label estimates as estimates.** Distinguish SOURCED from ESTIMATE in research.
- **When two sources conflict, prefer the one holding the raw data**, and record which lost and why.
- **Correct the record in place.** When research invalidates a documented claim, fix the document —
  a stale claim in `context/project/` will be believed.

## Core Principles

- **Simplicity First**: Make every change as simple as possible. Impact minimal code.
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards.
- **Minimal Impact**: Changes should only touch what's necessary. Avoid introducing bugs.
