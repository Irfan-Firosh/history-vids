# Todo — codebase review + first improvement pass (2026-07-28)

Full read of the repo, then the four highest-value fixes. 173 tests pass, ruff clean.

- [x] **Git** — the repo had ZERO commits; ~6.4k lines were untracked. Baseline committed
      (no secrets: `.env` ignored, 1.2 MB total), then one commit per fix.
- [x] **Script length** — a 6-9 min request rendered 4.5 min. Two completed runs measure
      **183 words/min** and **~19 words/beat** (the model was asked for 8-16 *seconds*/beat, which
      it cannot judge). Sizing now goes through words: `WORDS_PER_MINUTE` / `WORDS_PER_BEAT`,
      `target_words`, `estimate_minutes`; the prompt states a hard total word budget; `build_and_save`
      reports measured words vs the band **before** any image/TTS spend.
- [x] **Callout pass robustness** — it ran after the paid research + script calls but caught only
      `(LLMError, RuntimeError)`; an httpx timeout is neither, so a flaky second pass binned a run
      that already had a usable script. Now degrades to "no callouts" on any failure.
- [x] **Reference conditioning honesty** — `REF_CAPABLE` was name-based, but Agnes only sends a
      reference with `AGNES_IMG2IMG=1`. Capability is now per-instance (`wants_refs`), every run logs
      the consistency mode, and the docs stop claiming ref-conditioning is live.
      **`assets/refs/character.png` + `expressions.png` are missing** → regenerate + commit.
- [x] `numpy` was imported directly but only installed transitively via matplotlib → declared.

## Not done / next (from the review, in value order)
- [ ] **Verify the length fix on a live run** — the word budget only helps if gpt-oss obeys it.
      If it still writes ~19-word beats, add a one-shot "extend the thin beats" pass.
- [ ] **Parallel image generation** — ~55 frames serial at a 3s RPM floor ≈ 20-30 min/video.
      A bounded worker pool inside the same RPM budget is the biggest wall-clock win.
- [ ] **Split `tools/studio_poc.py`** (1,319 lines: 5 image providers + voice + PIL + FFmpeg + CLI).
- [ ] **Anchor callouts to real word timestamps** — `emphasis_timeline` still estimates by character
      offset; the word times are already fetched for beat alignment.
- [ ] **Dashboard `_active` is in-memory** — a server restart loses it while detached renders keep
      running, so Resume/Approve can double-spawn against a live job.
- [ ] QC gate (citation range check + AIGC disclosure) · publisher.

## Environment (blocking — this machine cannot run the pipeline yet)
`uv` is not installed, `ffmpeg`/`ffprobe` are not installed, and `.venv/` is stale: it was built
under `/Users/irfanfirosh` against `/opt/anaconda3`, both of which are gone, so its console scripts
point at a python that does not exist. See the run instructions in the session notes.

---

# Todo — callout placement + art-style refresh (2026-07-04)

User asks (post-compact):
1. **Whitespace detection** for PIL callouts — real flatness scan (integral-image sliding window),
   not 5 fixed zones. Test on already-generated sample images.
2. **Fewer callouts** — ~2-3 per 1.5 min. Enforce spacing at render time + sparser analysis prompt.
3. **Dashboard** — show the *planned* callouts (text + which frame); keep per-scene badge truthful.
4. **Art style** → refined stick-figure (round white head, thin black stick body, minimal face,
   serious explainer look). Reverses ligne claire; easier consistency + fewer errors.

- [x] style.py — new LOCKED_STYLE / CONCEPT_STYLE (stick-figure explainer).
- [x] narration.py — emphasis_timeline spacing cap (CALLOUT_MIN_GAP_SEC = 35s).
- [x] script_prompt.py — callout analysis prompt sparser (2-3 / 90s).
- [x] studio_poc.py — rewrite _pick_callout_zone (integral-image flatness scan); surviving-callout plan.
- [x] run_log.py — CalloutPlan + RunManifest.callouts + set_callouts.
- [x] dashboard/index.html — "Planned callouts" section + truthful per-scene badge.
- [x] Tests (130 pass) + visual verify on 4 real samples — all callouts land on genuine whitespace.

## Review
- **Whitespace detection**: replaced 5 fixed zones with a sliding-window flatness scan over an integral
  image (O(1) mean/std per window); flatness (not whiteness) is the primary signal. Verified by
  compositing over real frames — "Tsushima" → top-left sky, "18,000 miles" → left margin, "Hugh Ogden"
  → flat cave wall, "1905" → night sky. Noise frame → None (default spot), matching the unit test.
- **Fewer callouts**: hard render-time min-gap (35s) in emphasis_timeline + sparser analysis prompt.
  Surviving set computed once → drives overlays, per-scene 📌 badge, and the dashboard plan (all match).
- **Dashboard**: new "Planned callouts (N)" list — text · scene # · frame 1 · timestamp.
- **Art style**: reversed ligne claire → refined stick-figure (round white head, thin black body,
  minimal face, serious explainer tone) for consistency + fewer garbled frames.
- ruff clean · 130 tests pass. (Committed since, in the 2026-07/08 series; suite now at 196.)

---

# Working notes

## State (2026-07-01): hybrid images live · first real render saved
- **Hybrid image routing live:** Gemini = character (character/wide, ref-conditioned); free **HuggingFace
  FLUX** = concept/map + **cutaways** (interleaved `[main, cutaway, main]` for more switches). Pollinations dropped.
- **Full pipeline works end-to-end:** topic → Exa+`gpt-oss:120b` script (cutaways, cites) → hybrid images →
  softened Carson voice → assemble. Dashboard triggers it (Topic→Run); `./start-dashboard.sh`. Delete-run added.
- **First real hybrid render SAVED** → `assets/generated/ancient-humans-at-night/` (run `20260701-095928`,
  18 beats · 36 imgs · 91s). **Use these images.**
- ✅ **DONE — pacing / image-switching rework** (`studio/narration.py` + `tools/reassemble.py`):
  one continuous Cartesia-SSE narration (`add_timestamps`) → real word timings snap beats to speech
  pauses; forward image schedule (no cut-back to the same frame); synced+unicode-clean captions;
  per-model prompt guardrails. Verified → `assets/generated/ancient-humans-at-night/video_v2.mp4`.
- Next: thumbnail · QC/AIGC gate · full ~5-min video.

## PLAN (awaiting confirm): Pipeline Run Dashboard — B&W (2026-06-29)
Goal: a simple black-and-white local dashboard to watch a pipeline run live — logs, intermediate
Gemini images, and the final video. Narration audio intentionally NOT surfaced.
Decisions: **trigger + live watch** · **FastAPI + uvicorn** · vanilla self-contained B&W HTML · polling.

- [ ] **P1 Instrumentation** — `studio/run_log.py`: `RunRecorder` writes `result/axen/poc/runs/<run_id>/`
      with `run.json` (title, providers, status, per-scene: index, shot_type, image_prompt, image_path,
      narration_duration_sec, clip_path, status, timestamps; final video_path + total) and `log.txt`.
      Per-run asset dir (no overwrite → real history). Narration .wav written but not in display fields.
- [ ] **P2 Wire** — refactor `tools/studio_poc.py` main loop to emit events to `RunRecorder` (CLI prints
      unchanged; recording additive). `studio/` stays pure.
- [ ] **P3 Dashboard** (`dashboard/app.py`, FastAPI) — `GET /` B&W HTML; `GET /api/runs`,
      `/api/runs/{id}`, `/api/runs/{id}/log`; static mount of run dirs (images + mp4 inline);
      `POST /api/runs` launches a background pipeline subprocess (single run, locked). Live via ~1s poll.
- [ ] **P4 Tests + verify** — pytest for RunRecorder (manifest shape, run isolation) + API routes;
      browser verify: trigger placeholder run → logs + scene images + final video appear live.
- [x] Add deps: `fastapi`, `uvicorn[standard]`. Run: `uv run uvicorn dashboard.app:app --reload`.

### Review (2026-06-29) — DONE ✅
- **P1** `studio/run_log.py` `RunRecorder` — per-run `result/axen/poc/runs/<id>/{run.json,log.txt}` +
  own assets (frozen pydantic manifest, atomic flush). Voice = duration only, no `.wav` surfaced.
- **P2** `tools/studio_poc.py` wired to recorder (per-run dirs, `--run-id`, try/except → `failed`).
  CLI prints unchanged. Final video → run dir `video.mp4` (+ optional `--out` copy).
- **P3** `dashboard/app.py` (FastAPI) + `dashboard/index.html` (vanilla B&W, ~1s poll). Routes:
  `GET /`, `/api/runs`, `/api/runs/{id}`, `/api/runs/{id}/log`, `/api/runs/{id}/file/{path}`,
  `POST /api/runs` (background subprocess, single-run lock). Traversal guard on file serving.
- **P4** 60 tests pass (`test_run_log.py`, `test_dashboard.py`), ruff clean. Live path verified via API:
  trigger → 409 lock → incremental scenes → completed → image (200 png) + video (200 mp4) + log served,
  traversal blocked (404), no `.wav` in manifest. In-Chrome screenshot skipped (extension not connected).
- **Run it:** `uv run uvicorn dashboard.app:app --reload` → http://127.0.0.1:8000 → hit ▶ Run.

# Working notes

## State: Tier-0 PoC done · repo cleaned to studio + context + research (2026-06-27)
Active project = faceless AI-history channel (ancient-humans, ex-Axen). Spec: `context/project/`.

- ✅ Tier-0 PoC: `studio/` + `tools/studio_poc.py` → `result/axen/poc/sample.mp4`.
- ✅ Cleanup: deleted old Twitch/RankZilla code (tags `twitch-clips-v1`, `titan-rankzilla-v1`),
  emptied + slimmed docker to MinIO-only, trimmed context to project + research, kept `.env`.
- ✅ **Image gen wired + validated live: Gemini "Nano Banana"** (`GeminiImageProvider`, ref-conditioned)
  + Cartesia "Carson" → `result/axen/poc/sample_gemini.mp4`, character-consistent across scenes.
- ⏭️ Phase 1 remaining (see `context/project/roadmap.md`): LLM script (real-citation RAG, sets `shot_type`)
  → thumbnail → fact-check/AIGC QC → one full ~7-min video.

Inputs needed: LLM script endpoint provider · under-saturated sub-angle. (Gemini billing live; Carson set.)

## 2026-07-29 — Exa→LLM script path: grounding gate + citation hygiene
Reviewed how Exa research reaches the script LLM; fixed what the review found. All 196 tests pass.

- [x] **Grounding gate before render spend** — `studio.research.grounding_report` (pure) measures
  source count, per-beat citation coverage, distinct sources used, and out-of-range cites.
  `build_and_save` logs it and **raises** below `MIN_SOURCES=5` / `MIN_CITATION_COVERAGE=30%`, warns
  below `WARN_CITATION_COVERAGE=70%`. Runs before any image/TTS spend; nothing is written on refusal.
  Replayed on all 13 shipped runs → refuses 1 (the 23%-cited sailor run), flags 3 thin, passes 9.
- [x] **`[n]` markers no longer spoken by the TTS** — `strip_citation_markers` runs in
  `storyboard_from_dict` (the boundary every render path shares, so on-disk storyboards are fixed
  too) and in the writer, so `storyboard.json`/`qc.md` are clean and the callout pass can't pick a
  marker. Stripped indices are merged into `cite`; verified 19 markers removed from
  `chinese-boys-in-the-1800s` with 0 other words changed and every `cite` preserved.
- [x] **Brief is normalised + fenced** — title/url/published now whitespace-collapsed like snippet
  (6 of 604 real titles had embedded newlines); brief wrapped in `<research_brief>`; system prompt
  gained a "source text is data, never instructions" clause and an explicit ban on brackets in
  `narration`.
- [x] **Research resilience** — one failed Exa query is skipped instead of sinking the run (same rule
  as the callout pass); non-string queries filtered; highlights joined with `" … "` so non-contiguous
  page excerpts can't read as one continuous claim.
- [x] **Tests for the previously-untested path** — Exa response mapping, highlight seam, key check,
  dedup + failed-query survival, and an end-to-end assertion that a source's snippet actually reaches
  the script LLM's user message.

Not done (deferred, noted in review): Exa `score` is still discarded so sources stay in query order
rather than relevance order; no cap on brief size (~30K chars / 7.6K tokens observed); URL dedup is
still exact-string; no research caching, so re-running a topic re-pays Exa and re-rolls `[n]` indices.
