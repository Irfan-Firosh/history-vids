# Task Board — Faceless AI History Channel

> Claude Code reads this first every session. Keep one item `<- ACTIVE`.
> Spec: `context/project/` (README · architecture · roadmap) · research: `result/axen/`.

## Current phase: Tier-0 PoC ✅ → Phase 1 (first real video)

### Done
- [x] Reverse-engineer **Axen / @AxenCool** + production-stack research → `result/axen/`
- [x] **Tier-0 PoC** — `studio/` (Scene/Storyboard, locked style, scene filter — static hard-cut; 15 tests) +
      `tools/studio_poc.py` → `result/axen/poc/sample.mp4` (script→images→static hard-cut→voice→assemble; free + offline)
- [x] Repo cleanup — deleted old Twitch/RankZilla code (tags `twitch-clips-v1`, `titan-rankzilla-v1`);
      slimmed to `studio/` + context + research; MinIO-only docker (emptied)

### Phase 1 — first real, publishable video (see context/project/roadmap.md)  <- ACTIVE
- [x] **Gemini "Nano Banana" images** — `GeminiImageProvider` wired (REST, 16:9, ref-conditioned),
      validated live end-to-end → `result/axen/poc/sample_gemini.mp4`; character consistent across scenes.
      REF-1/REF-2 bootstrapped via `tools/make_refs.py` → `assets/refs/`. Blueprint: `context/project/blueprints/`.
- [x] **Cartesia "Carson" voice** — `CartesiaVoiceProvider` verified live in the full run; `CARTESIA_VOICE_ID` set.
- [x] `LLMScriptProvider` — **live-validated** (topic → Exa research → `gpt-oss:120b` calm/philosophical
      script + engaging title, cites `[n]`, `shot_type` + `cutaways`). `studio/{llm,research,script_prompt}.py`,
      `storyboard_from_dict`; `tools/make_script.py`; dashboard `tools/run_pipeline.py`. `LLM_API_KEY`+`EXA_API_KEY` set.
- [x] **Hybrid image routing** — **Gemini** for the character (character/wide, ref-conditioned); free
      **HuggingFace FLUX** for concept/map + all **cutaways** (`studio/huggingface.py`, `HuggingFaceImageProvider`,
      `build_providers`). `HUGGINGFACE_TOKEN` set. Pollinations dropped.
- [x] **Run dashboard** — `dashboard/` FastAPI + B&W HTML (dark/light, script, Exa sources, per-scene images,
      live log, **delete run**, Topic→Run whole-pipeline trigger). `./start-dashboard.sh`.
- [x] **First real hybrid render saved** → `assets/generated/ancient-humans-at-night/` (run `20260701-095928`,
      18 beats · 36 imgs · 91s, "What Did Ancient Humans Do at Night?"). Keeper image set.
- [x] **Pacing / image-switching rework** — `studio/narration.py` (pure) + `tools/reassemble.py`:
      one continuous Cartesia-SSE narration (`add_timestamps`) → real word timestamps snap beats to
      speech pauses; forward image schedule (main → cutaway flash → next main, **no cut-back**); synced
      captions with unicode normalisation. Per-model prompt guardrails (`styled_prompt(shot_type)` +
      people-free `CONCEPT_STYLE`, wordless-pictograph cutaways). Verified → `video_v2.mp4` (reused the
      kept images, new audio). 88 tests, ruff clean.
- [x] **Cloudflare Workers AI option** — `--images cloudflare`: char/wide = **FLUX.2 [dev]**
      (`@cf/black-forest-labs/flux-2-dev`, `studio/cloudflare.py` + `CloudflareImageProvider`, up to 4 reference
      images for consistency, Cloudflare-billed); concept/map + cutaways = Gemini. Also on the dashboard picker.
      Verified live (ref-conditioned, on-model). Caveat: FLUX.2 is capacity-limited + slow (~1-2 min/img); 6× retry.
- [x] **Agnes 2.1 Flash provider + per-role model selection** — `studio/agnes.py` + `AgnesImageProvider`
      (free, fast, text-to-image + image-to-image refs, RPM-retry). New engine: `ImageProviders(character,
      concept, cutaway)` — each role picks its own model (`providers_from_roles`, `--char/concept/cutaway-model`).
      **New dashboard page `/new`** (`dashboard/new_run.html`): per-role pickers (Gemini/Agnes) + Recommended
      preset (Agnes×3 + Cartesia). Cloudflare FLUX.2 + HF FLUX kept in code but **not offered** (slow/weak).
      Verified live (Agnes t2i + i2i on-model, per-role CLI render). 109 tests, ruff clean.
- [x] **Pacing overhaul + configurable 6-9 min + integrated emphasis** — longer beats (~8-16s), emphasis
      (numbers/symbols) baked into the character/wide/concept frame (no separate cutaways), every frame fresh,
      each held ≥8s (`MIN_FRAME_HOLD`; long beats split into distinct fresh frames). Duration band
      `--min-minutes`/`--max-minutes` on `/new` + CLI (scenes + research depth ~20→~50 sources derive from it).
      Main render path now uses one-shot continuous narration (`build_narration`) + shared `render_video`
      assembler; dead cutaway code + `cutaway` role removed. Verified offline + Cartesia SSE; 104 tests, ruff clean.
- [ ] produce ONE full 6-9 min Agnes+Cartesia video (real live render, ~15-30 min) at quality ≥ the clone swarm
- [ ] **Thumbnail** generator + title from the hook
- [ ] **QC gate** — fact-check citations + AIGC-disclosure flag
- [ ] produce ONE full ~5-min video at quality ≥ the clone swarm

### Open inputs needed
- ✅ Carson `CARTESIA_VOICE_ID`, ✅ **Gemini** billing, ✅ **LLM_API_KEY**+**EXA_API_KEY**, ✅ **HUGGINGFACE_TOKEN** — all set + validated.
- Decided: **Gemini** (character, ref-conditioned) + **HuggingFace FLUX** (free, non-character/cutaways); static hard cuts, no AI-motion.
