# Active Project — Faceless AI History Channel ("Ancient Humans" lane)

> The chosen build. Niche locked 2026-06-27 from the Axen
> reverse-engineering. Detailed research lives in `result/axen/`; this folder is the working spec.

## Decisions (locked)
| Decision | Choice | Source |
|---|---|---|
| **Niche** | Faceless **"ancient humans / existential history"** — narration-driven explainer | [result/axen/report.md](../../result/axen/report.md) |
| **Target to beat** | **Axen (@AxenCool)** — ~$13K/mo, 11 videos, 52 days, RPM $4.61 | result/axen/report.md |
| **Format** | Long-form (~7 min, 16:9), evergreen "How/What Did Ancient Humans …?" series | §2 of report |
| **The moat** | **Script structure** (immersive hook → real citations → reconstruction → existential payoff) — fully automatable; it's what beats the clone swarm | §3 of report |
| **Visual system** | **Consistent-style AI images, STATIC, HARD CUTS** (no transitions/motion) — each image held ~5–10s, timed to the narration beat. Images via **Gemini 2.5 Flash Image ("Nano Banana")**, ref-conditioned for character consistency; images only | [blueprints/gemini-image-provider.md](blueprints/gemini-image-provider.md) |
| **Voice** | **Cartesia "Carson"** narration (key in `.env`; `CARTESIA_VOICE_ID` set) — validated live | research |
| **Automation target** | **Tier-0 ≈ 90%**, **~$2.30/video** (Gemini images + free static FFmpeg + Cartesia) | research |

## Status
- ✅ **Tier-0 runs end-to-end with REAL images + voice** — `tools/studio_poc.py --images gemini --voice cartesia` → `result/axen/poc/sample_gemini.mp4`. Gemini images are **character-consistent across scenes** (ref-conditioned). Free offline default (`placeholder` + `say`) still works. Pure logic in `studio/` (27 tests, ruff clean).
- ✅ Image generator decided: **Gemini** (won the bake-off; fal/FLUX dropped — no free API credits, weaker consistency). REF-1/REF-2 in `assets/refs/` via `tools/make_refs.py`.
- ⏭️ Next: `LLMScriptProvider` (real-citation RAG) → thumbnail → QC gate → first full ~7-min video. See [roadmap.md](roadmap.md).

## Monetization (from Axen, see result/axen)
RPM ~$4.61; ~$2,200 est. revenue/video at Axen's scale. Tier-0 cost ≈ **$0–2/video** (FFmpeg motion +
local/cheap images + Cartesia) → hugely positive unit economics. Long-form = mid-roll ad eligible.

## Risk & compliance (this niche is unusually clean)
- **No copyright / reused-content risk** — visuals are **AI-generated**, narration is original → **rights-clean by construction** (a big advantage over the found-clip path; the FAIL-CLOSED rights gate still applies to any external asset).
- **AIGC disclosure:** label AI-generated/altered visuals per YouTube policy (cheap, removes that risk).
- **Factual accuracy (the real risk):** scripts cite real studies → **human/LLM fact-check gate** required before publish (history is lower-stakes than health, but citations must be real, not hallucinated).
- **Saturation:** the "ancient humans + animation" micro-niche is a live gold rush (dozens of <60-day clones) — **differentiate on script quality + a distinct visual style**, move fast, or pick an adjacent under-served angle. See report §6.

## Files
- [architecture.md](architecture.md) — the Tier-0 pipeline, provider seams, stack tiers (instantiates template 02/03/06)
- [roadmap.md](roadmap.md) — build phases (instantiates template 07)
- [blueprints/gemini-image-provider.md](blueprints/gemini-image-provider.md) — **the image-stage design** (Gemini seam, ref workflow, cost, error handling) + optimized execution prompt
- [image-tool-testing.md](image-tool-testing.md) — image-generator bake-off notes (winner: **Gemini**; archived — decision made)
- [`prompts/`](../../prompts/) — content-generation kit (01 script · 02 image prompts · 03 Cartesia voiceover · **04 Gemini reference images**)
- Detailed research (committed): `result/axen/{report.md, production_stack_research.md, video_performance.png}`
