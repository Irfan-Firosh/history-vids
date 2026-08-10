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

## 1. Shot rate: ~2x too slow

**Corrected 2026-08-09.** The first version of this note said 4.5x, from a multimodal read that
estimated ~1.6s per image. A deterministic measurement disagrees and supersedes it.

`assets/refs/frame_*.jpg` is a contiguous frame sequence, so consecutive-frame mean absolute
difference gives a cut count with no model in the loop. Using `tools/conformance.py:47`'s
calibrated `HARD_CUT_THRESHOLD = 26.0`, over three separate 3,000-frame blocks:

| block | cuts / 2,999 pairs | held | @24fps | @30fps |
|---|---|---|---|---|
| 1–3000 | 37 (1.2%) | 98.8% | 17.8 cuts/min, 3.38s | 22.2 cuts/min, 2.70s |
| 7000–10000 | 32 (1.1%) | 98.8% | 15.4 cuts/min, 3.90s | 19.2 cuts/min, 3.12s |
| 14000–17000 | 25 (0.8%) | 99.1% | 12.0 cuts/min, 5.00s | 15.0 cuts/min, 4.00s |

So the reference sits at roughly **2.7–5.0s per shot**, not 1.6s.

| | Reference (measured) | This run | Where ours comes from |
|---|---|---|---|
| seconds per image | ~3.0–4.0 | 7.21 | `studio/narration.py:31` `MIN_FRAME_HOLD = 8.0` |
| full cuts / min | ~15–22 | 8.3 | 60 images / 432.6s |
| held frames | 98.8–99.1% | ~100% | static hard cuts, no motion |

**Two consequences.**

The `TARGETS` band in `tools/conformance.py:52` (`cuts_per_min` 16–18, `frozen_pct` 94.6–100) is
consistent with this measurement, which is weak corroboration — both may derive from the same
unverified corpus, so this does not establish provenance. But the earlier claim that the cut-rate
target was incoherent is not supported: 15–22 measured against a 16–18 band is a good match.

The multimodal read counted ~37 changes/min where hard cuts are ~15–22. The gap is most likely
partial changes — an arrow appearing, an element sliding in — which a full-frame threshold does not
see and which `conformance.py`'s own docstring flags as the FULL_CUT-vs-all-changes ambiguity.
Those are two different quantities, and the reference plausibly does both.

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

### 4b. Verified directly against the frame corpus (2026-08-09)

The table above came from one multimodal read of one 90-second window. A 20-frame contact sheet
sampled evenly across all 18,709 frames confirms it and adds three findings the read missed. All
of this is observable in `assets/refs/` — no new media fetched, none committed.

**Confirmed, with examples:**

- **Burned-in labels.** `FAT/BLUBBER` with leader lines onto a seal; `HIBERNATION IDEA`,
  `SICKNESS`, `SCAVENGERS` labelling a diagram; a `10:00` clock face. Text is a core device.
- **Arrows everywhere.** Leader lines, curved flow arrows, and directional sets in nearly a third
  of sampled frames.
- **Red as emphasis.** Large red `?` marks over investigation scenes.
- **1–3 figures**, never a five-across lineup.

**New — three things neither the read nor this note had:**

1. **Colour-coded semantic overlay.** Orange squiggles and arrows mean heat; blue arrows and lines
   mean cold; yellow fill highlights the anatomical part under discussion. This is a systematic
   visual language for abstract quantities, applied on top of the drawing. The pipeline has no
   equivalent — `emphasis` renders a text callout and nothing else.
2. **Cutaway and cross-section staging.** A pit house sliced open, a cave shown in section with
   people inside, a barn with livestock in the layer below. A recurring way to show interiors.
3. **Backgrounds are rich, varied and location-specific** — deep blue night snow, brown earth
   strata, cave interiors, pine forest, ice shelf. `LOCKED_STYLE:22`'s "Plain pale background
   (white, light grey, pale blue, or pale yellow)" is not a description of this reference; it is
   the opposite of it. Scale ranges from one tiny figure alone on white to a face filling the
   frame — our 60 frames have no such range (see §3).

**One correction to our own style dogma.** `LOCKED_STYLE` requires that *every* human be a white
round-headed stick person. The reference does not: it mixes plain white-headed stick figures with
more fleshed characters that have hair, skin tone and drawn bodies. The rule is stricter than the
thing it is imitating.

**Provenance, partial.** These frames show winter and cold-survival subject matter, not the
"all day" video. So the corpus is consistent with the Axen channel but is not the video compared
in §1. Provenance is still not established from the code.

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

Ranked by effect per unit of work. The ordering changed once §4b was verified: the largest gap is
not pacing, it is that `LOCKED_STYLE` bans or omits most of the reference's visual vocabulary.

1. **Rewrite `LOCKED_STYLE`.** Three clauses do the damage: "plain pale background", "mid-distance
   view / lots of empty space / diagram-like composition", and the absolute `NO_TEXT`. Replace the
   background rule with location-specific environments, the framing rule with an explicit per-beat
   shot type (close-up / profile / depth / cutaway / wide), and narrow `NO_TEXT` to prose only.
2. **Add the label-and-arrow layer.** Labels, leader lines and the orange-hot / blue-cold overlay
   are the reference's signature and we render none of it. The existing PIL callout machinery
   (`emphasis`, `emphasis_timeline`) is the right home — it already draws text deterministically,
   which sidesteps the garbled-model-text problem that motivated `NO_TEXT`.
3. **Wire `plan_shots` into `studio_poc`** — the module exists and is tested. `WORDS_PER_SHOT = 10`
   at the measured 172 wpm gives **3.5s per shot**, inside the measured 2.7–5.0s band. Costs
   roughly 2x the images per video (60 -> ~124 for this run's length).
4. **Widen the image prompt.** 8 words carrying 2.5% of the prompt cannot specify a shot; the
   storyboard LLM needs to emit framing, scale and staging per beat, not just a subject.
5. `lanczos` + `cas` in `render_segment`, and bump `CACHE_VERSION`.

## Confidence

Measured locally, high confidence: §1 (shot rate), §2 (prompt ratio), §3 (composition similarity),
§5 (encode and upscale), and the `plan_shots` wiring gap.

Verified by direct inspection of frames on disk, high confidence: §4b.

Single-source and still soft: the recurring pith-helmet "Explorer" character, and whether the
reference's partial-change rate really is ~37/min. Neither is load-bearing for the ranking above.

Unresolved: corpus provenance. Everything here describes `assets/refs/`, which is Axen-consistent
but unverified from the code.
