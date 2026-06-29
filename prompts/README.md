# Prompt Kit — faceless AI-history / psychology video generation

A reusable prompt kit, **split by API** so each part pastes where it belongs:

```
[TOPIC] ─▶ 01 SCRIPT (LLM: ChatGPT/Gemini/Claude) ─▶ a 1-row-per-scene storyboard
                                   │
            ┌──────────────────────┼───────────────────────┐
            ▼                      ▼                        ▼
   02 IMAGE PROMPTS         03 VOICEOVER (Cartesia)   (motion: NONE — static)
   → Gemini (Nano Banana)   → Carson TTS
   + 04 REF images          (voice 86e3…fb49)
            └──────────────► studio/ pipeline → static hard-cut video ◄───────┘
```

| File | Paste into | Purpose |
|---|---|---|
| [01-script-generation.md](01-script-generation.md) | a chat LLM | topic → full storyboard (per scene: shot type · image prompt · voiceover) |
| [02-image-prompts.md](02-image-prompts.md) | Gemini image API | the locked **style base** + **character base** + how each scene's image prompt is built |
| [04-gemini-reference-images.md](04-gemini-reference-images.md) | Gemini (REF setup) | the REF-1/REF-2 reference sheets that keep the character on-model (`assets/refs/`, `tools/make_refs.py`) |
| [03-voiceover-cartesia.md](03-voiceover-cartesia.md) | Cartesia TTS | turn the voiceover lines into Carson narration |

## What I changed vs the draft (on purpose — flag me if you disagree)
1. **Not every frame is a stickman.** Each scene picks a **shot type** to fit the line — *character*, *concept/prop*, *map/diagram*, or *wide scene* — exactly like Axen (a map, a job-application-with-a-red-✗, a crowd). The character stays identical *when present*; props/maps don't need it.
2. **No motion.** We do **static images, hard cuts** (decided earlier; fal/image-gen only). So I dropped the "animation" part. Each image is just held for its narration beat. *(If you ever want subtle motion, the optional Ken-Burns toggle exists in `studio/`.)*
3. **Parameterized length.** Set `[DURATION]` + `[SCENES]` — works for a 59s short (10 scenes) **or** our long-form Axen target (~7 min, ~60–80 scenes; 1 image per ~5–10s beat).
4. **Our locked style + consistency** baked in (flat stick-figure cartoon, thick outlines, expressive faces, minimal bg, **no text inside images** — captions are overlaid later; fixed character + seed).
5. **Truth gate:** for any factual/historical claim, use **real** facts/figures — no invented studies, names, or dates (fact-check before publish).
6. Output maps 1:1 to the pipeline's `Scene` (narration, image_prompt) so it drops into `studio/`.

## Example topic (generated, per request — motivational / psychology / personal growth)
Pick one and drop it into `[INSERT_TOPIC]`:
1. **"Why You Always Feel Behind in Life (And Why You're Not)"** ← my pick (curiosity-gap + relatable + growth payoff)
2. "The Hidden Reason You Can't Just Relax"
3. "Why Doing Nothing Is Secretly a Superpower"
