# Why the render looks bad — measured against the reference video, not against theory

**Date:** 2026-08-09
**Subject run:** `result/axen/poc/runs/20260803-113248` — "What Did Ancient Humans Do All Day?",
432.6s, 60 images, 1920x1080.
**Reference:** Axen `TQd2k1pEXp4`, "What Did Ancient Humans Do all Day Before Jobs Existed?",
8:33, 3.16M views, channel `UC_7R-sfi7bi8dkzmSlBdUVw`. Near-identical topic, so this is a direct
head-to-head rather than a genre comparison.

Reference observations are SOURCED (multimodal read of 02:00–03:30 via the NexLev
`watch_youtube_video_and_ask` tool, 2026-08-09). Our numbers are measured locally with the code
cited. No competitor media is committed — numbers and descriptions only.

## The finding

The renderer is not the problem. It faithfully displays weak images, and the images are weak
because `studio/style.py::LOCKED_STYLE` mandates the weakness. Seven of the reference's defining
devices are things our prompt explicitly forbids.

## 1. Shot rate: 4.5x too slow

| | Reference | This run | Where ours comes from |
|---|---|---|---|
| seconds per image | ~1.6 | 7.21 | `studio/narration.py:31` `MIN_FRAME_HOLD = 8.0` |
| image changes / min | ~37 | 8.3 | 60 images / 432.6s |

`tools/conformance.py:53` targets `median_shot_sec` of 0.9–4.6. `MIN_FRAME_HOLD = 8.0` is above
the top of that band, so the pipeline is structurally incapable of passing its own gate.

**`studio/shots.py::plan_shots` already solves this** (`WORDS_PER_SHOT=10`, `MIN_SHOT_SEC=0.9`,
`MAX_SHOT_SEC=8.5`) and is fully tested — but `tools/studio_poc.py` never imports it. It calls
`frames_for_span` / `image_timeline` instead (`tools/studio_poc.py:1123`, `:1163`, `:1194`,
`:1323`). Only `studio/__init__.py:36` and the tests reference `plan_shots`. It is dead code in
production. `studio/shots.py:5` documents the gap in its own docstring: "52 shots where the
reference has ~218."

## 2. The subject is 2.5% of the image prompt

Measured over all 52 scenes of this run's storyboard, with `studio.style.styled_prompt`:

- subject: median **8 words** (min 6, max 11)
- full prompt as sent: median **325 words**
- subject share: **2.5%**
- negation tokens per prompt: **27**
- scenes naming any camera/framing term: **2 / 52**
- subjects beginning with the literal word "character" or "wide": **40 / 52**

A representative subject is `character shaping chert flake on a flat stone slab` — what is in the
scene, never how it is framed.

## 3. Composition monotony, measured

Each of the 60 frames reduced to an 8x8 grid of ink density (dark line-work per cell), L2
normalised, compared pairwise. This measures LAYOUT, not palette.

- mean pairwise similarity **0.879**, median 0.888
- **min 0.677** — even the two most different frames in the video are broadly alike
- **34 / 60 frames (57%)** put their heaviest ink in the same horizontal band

Visual read of a 24-frame contact sheet agrees: the dominant frame is five stick figures in a
front-facing row, full body, feet on a horizon at the same height, on flat beige ground.

## 4. Seven inversions — the prompt forbids what the reference does

| Reference does | `studio/style.py` says | Line |
|---|---|---|
| 1–2 figures staged in depth | (emergent) 5+ in a flat row | — |
| crops figures at waist/chest, uses profile | "mid-distance view", "lots of empty space" | `:22` |
| red numbers, labels, arrows, red X marks constantly | `NO_TEXT`, "maximal + on every image-prompt path" | `:66` |
| backgrounds change to match the location | "Plain pale background … one simple flat ground band" | `:22` |
| red as a consistent emphasis colour | "small flat color palette with simple accent colors" | `:22` |
| a recurring "Explorer" figure with a pith helmet | "WITHOUT forcing a named/distinctive protagonist (no signature accessory)" | `:128` |
| elements appear / slide in | project rule: no motion of any kind | `CLAUDE.md` |

The `NO_TEXT` one is the sharpest: on-screen numbers and arrows are among the reference's most
characteristic devices, and we ban them on every prompt path. They were banned because the image
model garbles text — a real constraint — but the conclusion drawn from it (no text anywhere) threw
out the device instead of moving it to a layer that can render text correctly.

## 5. Render-path defects (small, real, already half-fixed)

- **Double encode.** With caption cues, `tools/render/assemble.py:122` re-encodes every frame
  through libx264 a second time; with no cues it stream-copies. Rebuilding this run with no cues:
  8.4s, and **1,412 kbps vs the captioned 551 kbps** — same pixels, one generation instead of two.
  Fixed 2026-08-09: captions now default off.
- **Every frame is an upscale.** Agnes returns 1312x736 regardless of the requested size
  (`studio/agnes.py:21`, probed 2026-08-03), so 1920x1080 output is a 1.46x bicubic upscale.
  `tools/render/segments.py:43` uses ffmpeg's default scaler; `lanczos` plus a light `cas` pass
  would hold the black outlines better. Not yet changed.
- **Style drift between frames.** Some images arrive with a hand-drawn rectangular border and
  white margin (visible at 90s); others are full-bleed. Nothing in the prompt forbids the border.

## 6. What is NOT the problem

- The rubric work landed: this script opens with a literal question, carries numbers, and passed
  with zero repair calls.
- Character look is consistent enough — heads, limbs and line weight hold across 60 frames with
  **no reference conditioning at all** (`log.txt:8`: "character consistency: prompt-only (agnes
  sends no reference image)"). `assets/refs/character.png` and `expressions.png` do not exist, so
  `tools/studio_poc.py:753` returns an empty list. The whole look is coming from prompt text.
- The segment cache works (380ms cold, 0.3ms warm, measured 2026-08-02).

## Implication

Ranked by effect per unit of work:

1. Wire `plan_shots` into `studio_poc` — the module exists and is tested. 4.5x shot rate.
2. Rewrite `LOCKED_STYLE`'s composition clauses and make the storyboard emit a shot type per beat
   (close-up / profile / depth / cropped). Removes the lineup.
3. Move on-screen numbers and arrows to a post pass that draws them deterministically, and lift
   `NO_TEXT` for those specific elements only.
4. `lanczos` + `cas` in `render_segment`, and bump `CACHE_VERSION`.
