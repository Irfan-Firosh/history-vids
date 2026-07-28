# Roadmap — Faceless AI History Channel (instantiates template 07)

## ✅ Phase 0 — Tier-0 PoC (DONE)
Script→images→static hard-cut→voice→assemble runs end-to-end (`tools/studio_poc.py` → `sample.mp4`), free + offline.

## Phase 1 — First real, publishable video (~$2.30/video)
- [x] **Gemini "Nano Banana" images** — `GeminiImageProvider` (REST, 16:9, **ref-conditioned**) in the
      stick-figure cartoon style; each scene prompt carries the **facial expression**. Validated live.
- [~] **Style consistency** — REF-1/REF-2 reference conditioning works (validated on Gemini), but the
      ref sheets are MISSING from `assets/refs/` and the recommended Agnes default sends no reference
      at all, so live runs are **prompt-only**. Regenerate via `tools/make_refs.py` + commit, or accept
      prompt-only. Each run now logs which mode it used. No FLUX LoRA needed either way.
- [x] **Cartesia "Carson" voice** — `CartesiaVoiceProvider` verified live in the full run.
- [ ] `LLMScriptProvider` — generate the storyboard from a topic via an LLM endpoint + **real-citation RAG**.
      Chunk narration into ~5–10s beats → **one image per beat**; assign each scene a `shot_type`.
- [ ] **Thumbnail** generator (the other quality lever) + title from the hook
- [ ] **QC gate**: human/LLM fact-check of citations + AIGC disclosure flag
- [ ] Produce ONE full ~7-min video matching Axen's structure end-to-end
- **Exit:** a publishable video at quality ≥ the clone swarm, cost ≤ ~$3.

## Phase 2 — Channel + cadence + learning loop
- [ ] Publisher (YouTube Data API), scheduled, AIGC-labeled
- [ ] `short_analytics`-style logging → weekly script/title/thumbnail weight re-fit
- [ ] ~1 video / 1–2 days; pick the under-served angle within the niche (avoid the saturated exact-clones)
- [ ] Cross-platform repost (same video → TikTok/Reels/Shorts) for free reach
- **Exit:** channel running mostly unattended; first monetization signal.

## Phase 3 — Scale + defensibility
- [ ] Portfolio of channels / adjacent niches (kill-switch isolation)
- [ ] Distinct locked styles per channel; sponsor-ready once persona/identity forms
- [ ] Productize the pipeline (optional)

## Open inputs needed from user
- ✅ Carson's `CARTESIA_VOICE_ID` set; `CARTESIA_API_KEY` present.
- ✅ **Gemini** `GEMINI_API_KEY` + billing live (validated). fal/FLUX dropped (no free API credits, lost bake-off).
- ⏳ LLM script endpoint (provider TBD) for `LLMScriptProvider`.
- Which exact angle within "ancient humans / existential history" to avoid the most-cloned topics.
- (decided: images via **Gemini 2.5 Flash Image**, ref-conditioned; no AI-motion — static hard cuts.)

## Image providers — current status (2026-07-01)
Per-role selection: `ImageProviders(character, concept, cutaway)` in `tools/studio_poc.py`; the
dashboard `/new` page picks a model per role. Offered providers:
- **Agnes 2.1 Flash** (`agnes`, `studio/agnes.py`) — **RECOMMENDED default.** Free, fast (~15-30s),
  on-style, text-to-image + image-to-image (reference conditioning via `extra_body.image`); RPM-limited
  so the provider retries on 429/5xx. Needs `AGNES_API_KEY`.
- **Gemini 2.5 Flash Image** (`gemini`) — solid, paid, multi-reference conditioning.
- **DEPRECATED, kept in code but NOT offered in the UI:** `cloudflare` (Workers AI FLUX.2 [dev] —
  too slow ~1-2 min + persistent 429 capacity failures) and `hf` (HuggingFace FLUX.1 — weaker quality).
  Both are inferior to Agnes/Gemini; do not reach for them unless the situation changes.
