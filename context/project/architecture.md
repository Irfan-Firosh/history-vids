# Architecture — Faceless AI History Pipeline (Tier-0 → scale)

> Instantiates template `02/03/06`. The Tier-0 PoC is built; this documents how it works and how each
> stage swaps from free → paid without touching the orchestration.

## Pipeline
```
TOPIC ─▶ [SCRIPT] ─▶ [STORYBOARD: scenes = narration + image_prompt + motion]
      ─▶ per scene:  [IMAGE (style-locked)] ─▶ [VOICE → duration] ─▶ [STATIC clip (held; hard cut) + caption]
      ─▶ [CONCAT] ─▶ video ─▶ [QC: fact-check + AIGC label] ─▶ [PUBLISH] ─▶ [ANALYTICS → weights]
```

## Code map
| Piece | Where | Status |
|---|---|---|
| Pure logic (Scene/Storyboard + `shot_type`, locked style, scene filter — static hard-cut default) | `studio/` | ✅ built + 27 tests |
| Runner + side-effecting providers (PIL/say/ffmpeg) | `tools/studio_poc.py` | ✅ runs → `result/axen/poc/sample.mp4` |
| Canned demo storyboard (offline) | `studio/storyboard.py` | ✅ (→ `LLMScriptProvider` via an LLM endpoint) |
| FFmpeg motion + caption + assembly | `tools/studio_poc.py` (system ffmpeg) | ✅ built |
| Gemini request/parse (pure) | `studio/gemini.py` | ✅ built + 8 tests |
| External services | Cartesia ✅ · **Gemini** ✅ (key+billing) · LLM endpoint (TBD) | Gemini+voice live |

## Provider seams (swap free → paid; orchestration unchanged)
| Stage | Tier-0 (now, free) | Production swap |
|---|---|---|
| Script | canned `DEMO_STORYBOARD` | `LLMScriptProvider` → an LLM endpoint + RAG for **real citations** |
| Image | `PlaceholderImageProvider` (PIL title-cards) | ✅ **`GeminiImageProvider`** — Gemini 2.5 Flash Image (~$0.039/img, 16:9, **ref-conditioned** REF-1/REF-2 from `assets/refs/`). Pure logic in `studio/gemini.py`. **Validated live.** |
| Voice | `SayVoiceProvider` (macOS `say`) | **`CartesiaVoiceProvider`** (Carson) — `CARTESIA_API_KEY` set; needs `CARTESIA_VOICE_ID` |
| Motion | **static hard cuts** (`scene_filter` default) — image held for its narration beat | unchanged — **no AI-motion**. (Optional Ken-Burns built but off.) |
| Captions | PIL **PNG overlay** (this ffmpeg lacks `drawtext`/libass — matches repo's existing pattern) | same |
| Assemble | FFmpeg `concat` filter (per-scene mux) | same |

## Cost
Gemini is used for **images only** (2.5 Flash Image, **flat ~$0.039/image** regardless of prompt; input
text + reference images are negligible, <0.1¢/scene). Motion is free (static FFmpeg). ~60 images/video →
**~$2.30/video** (×~1.5 for regens ≈ $2–3.50). No AI-video spend. Cartesia voice is separate (cents/video).
See `context/project/blueprints/gemini-image-provider.md` for the full cost model.

## Visual style + consistency
**Style** (grounded in real Axen frames): **minimalist stick-figure cartoon** — round off-white heads,
simple **expressive faces (dot eyes, eyebrows, line mouth)**, thin black stick limbs, thick hand-drawn
outlines, flat muted colors, no shading, **minimal backgrounds** (also maps/props, not only characters).
Locked in `studio/style.py::LOCKED_STYLE` (+ `STYLE_SEED`). Per-scene prompts must carry the **facial
expression** (the only emotional signal) — the style block stays fixed.

**Consistency (the hard part) — two modes, and the live one is NOT reference conditioning:**

| Mode | When | Status |
|---|---|---|
| **Reference-conditioned** — every `character`/`wide` shot generated with **REF-1** (model sheet) + **REF-2** (expressions) | `--char-model gemini` (or Cloudflare, or Agnes with `AGNES_IMG2IMG=1`) **and** `assets/refs/character.png` + `expressions.png` present | ⚠️ **not currently available** — the ref sheets are absent from `assets/refs/` (only gitignored study frames are there). Regenerate with `python tools/make_refs.py` (needs `GEMINI_API_KEY` + billing) and commit them. |
| **Prompt-only** — consistency rides entirely on `LOCKED_STYLE` | the recommended Agnes default (`AGNES_IMG2IMG=0`, text-to-image) | ✅ what every recent run actually used |

Validated once on the live Gemini PoC (same head/line-weight/palette across cave, forest, night,
campfire shots), so the mechanism works — but **capability is read per provider INSTANCE**
(`tools.studio_poc.wants_refs`), not per provider name, and each run logs which mode it used
(`character consistency: …`). `concept`/`map` shots never pass refs
(`studio.types.shot_uses_character`). Refs are generated from **our own** prompts
(`tools/make_refs.py`), rights-clean, never scraped competitor frames.

## Output spec
1920×1080, 30 fps, H.264, scene length = its narration audio length (natural sync). Long-form (mid-roll eligible).
