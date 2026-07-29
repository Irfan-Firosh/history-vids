# Art-Style & Motion Analysis — Axen vs. the Clone Swarm

> Frame-grounded study of the visual system used by Axen and the four closest competing channels,
> measured against our own rendered output. Brief: **how to execute the current stickman style
> better** (not whether to change it). Motion/animation in scope. Concerns only — no fixes.
>
> Pulled **2026-07-29**. Contact sheets + scripts: `result/axen/style_refs/competitors/`
> (**gitignored** — competitor frames are study material and are never committed, per
> `architecture.md`; regenerate with the commands at the bottom).

---

## Executive summary

**Axen has the simplest, cheapest-looking art of every channel sampled — the lowest line density
(4.1 vs. 8.3–12.8), a 6–7 colour palette, and backgrounds that are literally two flat rectangles —
and it has 3.0M views on the hero video. ThenFolk has genuinely accomplished art (labelled
infographics, detailed animals, inset maps, split-screen comparisons) and gets 4 views.**

Visual sophistication is not the lever in this niche. That does not clear our current output,
because it is not failing by being too simple — it is failing by being **busy and empty at the same
time**: 3× Axen's line density (12.5 vs 4.1) from cluttered props, 3× the near-white area (29% vs
11%) from bare backgrounds, and a third of the colour saturation (12 vs 34). That combination reads
as neither clean explainer nor rich illustration. It reads as unfinished.

## Method & evidence

| | |
|---|---|
| Pulled | 2026-07-29 · `yt-dlp` 120s mid-video samples at ≤360p · frames at 0.5 fps (stills) + 2 fps (motion) |
| Channels | Axen `TQd2k1pEXp4` (3.0M) · Mack `AvF3bPcqZeM` (274K) · Stickly `cCxzQ_Vv3Dc` (90K) · History Alive Animated `jy9P9I7QIN0` (187K) · ThenFolk `KO_035Jkc2E` (4 views) |
| Local evidence | 18,709 extracted frames in `assets/refs/` · 9 curated Axen stills + a 135-frame set in `result/axen/style_refs/` |
| Compared against | 50 rendered frames from run `20260707-133324` |
| Caveats | One 120s window per channel. View counts are lifetime, not velocity. Our run predates the current prompts. Channel-age data from `report.md` §6 (2026-06) is ~7 weeks stale. |

**Market shape (fact).** Axen's videos run **5–8.5 min** — our 6–9 min target matches exactly. The
clones run **8.5–25 min** (Stickly 24.9, Mack 21.8, History Alive 16.3). Axen's own view curve is
decaying hard across recent uploads: 3.0M → 1.02M → 253K → 23K.

## The measured baseline

| Channel | Views | Cuts/min | Held still | Animated | Saturation | Line density | Near-white | Dominant colours |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| **Axen** | 3.0M | 9.0 | 76% | **16%** | 34 | **4.1** | 11% | 7 |
| Mack | 274K | 11.5 | 90% | 0% | 27 | 8.3 | 7% | 10 |
| History Alive | 187K | 11.0 | 90% | 0% | 29 | 12.8 | 19% | 11 |
| Stickly | 90K | 19.0 | 77% | 7% | 7 | 5.3 | 32% | 9 |
| ThenFolk | **4** | 21.5 | 82% | 0% | 27 | 9.5 | 8% | 20 |
| **Our run** | — | ~11 | (static) | 0% | **12** | **12.5** | **29%** | **4** |

Cuts/min for our run = 51 frames over 270s. "Animated" = fraction of 0.5s intervals showing
sub-cut movement. Saturation/brightness are mean HSV percentages; line density is mean absolute
gradient (a proxy for how much linework and detail sits in the frame).

---

## 1. What the Axen visual system actually is

**Fact, from the frames:**

- **Two-band backgrounds.** Sky blue over earth brown, one hard horizon. No texture, no gradient,
  no detail — roughly two-thirds of sampled frames are exactly this.
- **Enormous negative space.** The figure occupies ~15–20% of frame height, centred, surrounded by
  empty sky.
- **A ~6-colour palette:** sky blue, earth brown, white, black, gold/tan, fire orange. Measured as
  7 distinct dominants across 50 frames, but with *high scatter* (37.0) — colour changes by scene:
  night navy, cave brown, white for abstract beats, grey for modern.
- **Heads are huge** — about a third of body height — because the face carries the emotional load.
- **Expressions are varied and specific.** One campfire frame carries four different expressions
  (laughing eyes-closed, wide-eyed, side-eye, faint smile). Eyebrows, pupil direction and mouth
  shape are all in play.
- **Line weight is uniform, solid, confident black** — not sketchy, not wobbly, not uneven.
- **Props are the detailed element.** Pottery carries drawn geometric patterns; a beaded necklace
  has individually coloured beads; animals (lion, rhino, wildebeest, deer) get anatomy, fur texture
  and shading — noticeably more finished than the humans.
- **Figures wear almost nothing.** In the hero video most stick figures have *no* clothing markers.
  Period is established by props and environment, not costume.
- **Text is used deliberately** — "EUROPE" hand-lettered on a gold map silhouette; "JOB
  APPLICATION" / "RESUME" / "HIRE" under a giant red X.
- **Modern-life frames are structural**, not decorative: a person on a sofa under a blanket by an
  electric heater (the literal first frame of the winter video); a modern bedroom with an alarm
  clock; office paperwork struck through in red.
- **Simple symbolic devices:** red squiggly arrows for UV rays, thought bubbles, a process row
  (hide → sewn tunic → finished coat) with arrows, split-screen comparisons (dark vs. light skin,
  brown vs. blue iris), anatomical insets (DNA in a torso, skin cross-section, gut diagram).

**Inference:** a system engineered for production speed and instant legibility at thumbnail scale,
not for beauty. Every expensive thing (backgrounds, costume, crowds) is stripped; every cheap
high-signal thing (face, one prop, one symbol) is amplified.

## 2. What the winning clones do that Axen doesn't

**Fact.** Mack (274K) and History Alive (187K) are not "Axen but worse" — they run a distinctly more
**infographic** grammar:

- **Hand-lettered labels on most frames:** "LIVED IN", "FOLLOWED HERDS", "REINDEER HIDES",
  "FUR OUTWARD", "BEFORE GORE-TEX", "PINCEVENT".
- **Named archaeological sites drawn as evidence** — History Alive draws the Pincevent excavation
  with grid squares, trowels, survey markers and archaeologists. The claim is *visually* sourced.
- **Cutaway cross-sections:** shelter interiors with labelled contents; a fur layer in section with
  blue arrows showing water beading off.
- **Explicit comparison frames:** "ANCIENT SYSTEM → MODERN SYSTEM" with a fur tunic morphing into a
  modern ski jacket; Mack's 24-hour clock split day/night with ✓ and ✗; before/after panels divided
  by a white line with an arrow between them.
- **A pictogram vocabulary:** ✗, ✓, skulls for danger, a plus for health, flame icons, fly swarms,
  thought bubbles containing a bone (hunger) or a squiggle (fear).
- **Timelines with real dates** along the frame bottom ("12,000 YEARS AGO → … → MODERN DAY").
- **Shot-scale variety:** Mack fills a frame with a leopard's face plus an anatomical inner-ear
  inset — a macro shot Axen never attempts.
- **A recurring "narrator" character:** History Alive's explainer figure wears round glasses and
  reappears across frames.

**Inference:** these channels hold 16–25 minutes of attention with information design, not drawing
skill. Labels, arrows and comparisons let a viewer follow a long explainer without re-reading the
narration.

## 3. The contrarian case — the most important finding

**Fact.** ThenFolk's frames are, by craft standards, the best of the swarm: a honeyguide bird with
real plumage, "HUMAN CALLS / BRRR-HM" with a sound-wave arrow, dolphins herding fish along dashed
motion paths, a labelled "SONAR"/"GPS" comparison, a "SURVIVAL CHART" with two plotted lines, a
bushfire landscape with an Australia inset map, a consistent capped protagonist. **The video has 4
views.** Its sibling has 1,676.

**Fact.** ThenFolk also has the highest palette scatter of any channel (20 distinct dominant colours
vs. Axen's 7) and the fastest cutting (21.5/min).

**Inference.** Art quality has a *floor* here (below which output looks like slop) but effectively
no *ceiling* that converts to views. Above the floor, distribution comes from topic, title,
thumbnail, hook and voice. Effort spent making frames prettier than Axen's two-rectangle
backgrounds is, on this evidence, spent in the wrong place — while any inconsistency that drops us
below the floor is expensive.

## 4. Where our output sits — the concerns

**C1. Busy and empty simultaneously.** Line density 12.5 vs Axen's 4.1 — three times the detail per
frame — while 29% of the frame is near-white vs Axen's 11%. Clutter floating in a void: props
scattered across an unfurnished pale background. No channel in the swarm looks like this.

**C2. Colour is doing no work at all.** Saturation 12 vs Axen 34. **Only 4 distinct dominant colours
across 50 frames, the lowest scatter of anything measured (28.3).** Axen changes background colour
to mark night, cave, modern, abstract; History Alive shifts green/brown/blue by scene. Our video is
one continuous cream wash start to finish — no chapter signal, no day/night, no temperature. A
video about surviving *deadly winters* rendered in beige.

**C3. Locally inconsistent while globally monotonous.** Both are true at once. Beat 0's two frames —
same beat, cut mid-narration — show yellow sand in the first and grey-blue snow in the second, with
a different cast in different clothes. Palette is uniform across the *video* but unstable within a
*beat*.

**C4. Costume detail is the opposite of the reference.** Axen's figures wear essentially nothing;
period comes from props and environment. Our prompt requires "one or two crude cultural markers" on
every person, and the model resolves that into fedoras, bowler hats, peaked caps, trench coats and
modern boots — anachronisms in every sampled frame. The reference establishes period by *removing*
costume; our instruction set does it by *adding* costume.

**C5. No information-design vocabulary exists.** Zero arrows, cutaways, split-screens, process
diagrams, timelines or pictograms across 45 beats. Both winning clones use these constantly, and
Axen uses them for its most-quoted beats. Our `shot_type` taxonomy (character / wide / concept /
map) has no category that produces any of them.

**C6. The no-text rule is a structural exclusion, not just a style choice.** Axen hand-letters
"EUROPE"; History Alive labels nearly every frame; Mack marks ✓/✗. Our `NO_TEXT` guardrail is
maximal and applied on every prompt path — for a defensible reason (the model garbles text) — but
the consequence is that we cannot produce the single most common frame type in the two
best-performing clones.

**C7. Faces are inert.** Axen's four-figure campfire frame carries four distinct expressions; our
figures are near-uniformly neutral dot-eyes with no eyebrows. The head is the largest element in
this style, so an expressionless face wastes the frame's highest-value real estate. The prompt does
ask for an explicit facial expression per scene — the rendered evidence says it isn't landing.

**C8. Crowd counts are inverted.** Axen shows one figure, occasionally five. Our hook frame rendered
eleven figures from a prompt that said "empty interior" — the locked style's "EVERY human is a stick
person" phrasing appears to invite populating the frame.

**C9. Animals are under-specified.** In the reference, animals are the *most* finished objects in
frame (the wildebeest has fur texture, shading, a lolling tongue). Our instruction treats them as an
afterthought — "animals and objects are normal simple cartoons" — so the one element the reference
invests in is the one we explicitly de-prioritise.

## 5. Motion grammar

**Fact.** Axen is the only channel in the sample with meaningful animation — **16% of half-second
intervals show sub-cut movement**, at 9.0 cuts/min (a new image every 6.7s). Mack, History Alive and
ThenFolk measure **0% animated, 90% held still**: static image slideshows with hard cuts, exactly
like our pipeline.

**Inference.** Static frames are not what separates the 274K channel from the 4-view channel — both
are static. Animation looks like an Axen-specific signature contributing to perceived production
value, not a table-stakes requirement.

**Concern (cut rate).** Our effective rate (~11/min) is faster than the 3M-view reference (9.0/min)
and matches the mid-tier clones. The fastest cutters in the sample are the *worst* performers
(ThenFolk 21.5, Stickly 19.0). `MIN_FRAME_HOLD = 8s` intends a calmer rhythm than we actually ship,
because short beats collapse it back to ~5–6s.

**Concern (mid-beat cuts).** The "intense beat gets a second distinct frame" device produces our
fastest cuts at the moments the narration is most dramatic — and because each frame is an
independent generation, those cuts change the world rather than the camera angle. Axen's animation
does the opposite: it holds the same world and moves within it.

## Risks & caveats

- **One 120s window per channel.** Axen's animation share in particular may vary across the video.
- **Correlation, not causation.** ThenFolk's 4 views may be a distribution failure (new channel, no
  algorithmic push) rather than evidence about art. "Art quality doesn't convert" is an inference
  from five channels, not a controlled result.
- **Our run predates the current prompts** — C4, C7 and C8 may be partially mitigated already; no
  render exists to check.
- **Axen's own decay (3.0M → 23K)** suggests the format may be past peak. Optimising art inside a
  declining format carries its own risk; the brief here was execution, not repositioning.
- **Text-in-image is genuinely hard.** C6 names a gap, not an oversight — the reason for `NO_TEXT`
  is sound.

## The areas, in priority order

Areas only, no fixes:

1. **Colour as a storytelling variable** (C2) — the largest measured gap to the reference and the
   cheapest signal we currently don't send at all.
2. **Detail budget inversion** (C1, C9) — line density goes to cluttered props while backgrounds,
   faces and animals are starved; the reference does the reverse.
3. **Period fidelity via subtraction** (C4) — costume markers are producing anachronism; the
   3M-view reference solves period by removing costume entirely.
4. **Absent information-design vocabulary** (C5, C6) — the dominant frame type in both winning
   clones has no representation in our shot taxonomy.
5. **Expression as the primary emotional channel** (C7) — the largest element in the frame is blank.
6. **Frame population discipline** (C8) — crowds where the reference shows one figure.
7. **Cut rhythm and mid-beat continuity** (§5) — faster than the best performer, slower than the
   worst; mid-beat cuts break the world instead of moving the camera.
8. **Animation as a differentiator** — the only thing Axen does that no clone does; also the most
   expensive to add and unproven as a driver.

## Reproducing this study

```bash
cd result/axen/style_refs/competitors
./grab.sh                                   # yt-dlp 120s samples → clips/ + frames/
python metrics.py axen mack stickly historyalive thenfolk \
    ../../poc/runs/<run_id>                 # the comparison table
python sheet.py out.png 6 3 $(ls frames/axen/s_*.jpg | head -6)   # a contact sheet
```

Needs `yt-dlp` and `ffmpeg` on PATH (`brew install yt-dlp ffmpeg`). Video ids and start offsets are
at the bottom of `grab.sh`. Everything in that folder is gitignored on purpose.

## Sources

- YouTube samples pulled 2026-07-29: Axen `TQd2k1pEXp4`, Mack `AvF3bPcqZeM`, Stickly `cCxzQ_Vv3Dc`,
  History Alive Animated `jy9P9I7QIN0`, ThenFolk `KO_035Jkc2E`
- `assets/refs/` (18,709 frames) · `result/axen/style_refs/` (9 curated stills + 135-frame set)
- `result/axen/report.md` §3, §6 — NexLev competitive scan (2026-06, ~7 weeks stale)
- `result/axen/poc/runs/20260707-133324/` — 50 rendered frames, same metrics
- View counts and durations from `yt-dlp` metadata at pull time
