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
- ruff clean · 130 tests pass · NOT committed (awaiting user + CodeRabbit).

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
