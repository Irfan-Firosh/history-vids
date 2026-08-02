# Video Forensics — Axen & the "ancient humans" stick-figure niche

Quantitative measurement of the visual and motion grammar of @AxenCool and four
imitator/peer channels, at enough precision to write a renderer spec.

**Headline:** these videos contain **no animation and no camera movement whatsoever**.
They are sequences of static illustrations joined by 1-frame hard cuts. The only
"motion" in the entire corpus is discrete foreground-element swapping over a held
background. A renderer that outputs static images with hard cuts is already producing
the correct motion grammar — the gap to the reference channels is in *cut rate*,
*illustration quality*, and *shot-to-shot continuity*, not in motion.

---

## 1. Method and sample

All measurement code and media are in a scratch dir outside the repo. Nothing was
copied into the project.

### Videos sampled

| Channel | Video ID | Duration | Views | Published | Native |
|---|---|---|---|---|---|
| Axen | `TQd2k1pEXp4` | 512s | 3,052,090 | 2026-05-04 | 3840×2160 @30 |
| Axen | `wt_7Hp7d7I8` | 624s | 635,789 | 2026-05-30 | 3840×2160 @30 |
| Axen | `2RJggsjlj4A` | 452s | 1,045,083 | 2026-04-28 | 3840×2160 @30 |
| Mack | `AvF3bPcqZeM` | 1308s | 292,804 | 2026-06-07 | 1920×1072 @30 |
| Mack | `C27Dd23jZzA` | 1314s | 1,600,000 | — | 1920×1072 @30 |
| Mack | `th-0rmRYBSg` | 1340s | 996,000 | — | 1920×1072 @30 |
| Stickly | `cCxzQ_Vv3Dc` | 1493s | 95,619 | 2026-06-03 | 1920×1080 @25 |
| History Alive Animated | `jy9P9I7QIN0` | 976s | 187,543 | 2026-05-15 | 1920×1080 @30 |
| ThenFolk | `KO_035Jkc2E` | 507s | 60 | 2026-07-29 | 3840×2160 @60 |

Axen channel: 50.1K subs, 11 videos. Mack channel (`@MackExplains7`,
`UCaS30yIIV6y2zqSnHGdIGMQ`): 68.1K subs, 49 videos — weighted with 3 videos per the
coordinator's steer, including its two top performers.

### Windows

Three 100-second windows per video: **early** `t=5–105s`, **mid** `t=0.45·D`,
**late** `t=D−115 → D−15`. This deliberately captures the intro/hook, the body, and
the outro, because pacing does differ between them (see §3.5).

- 27 clips × 100s = **45.0 minutes** of video downloaded at ≤480p.
- Motion: sampled at **10 fps → 27,723 frame pairs** analysed.
- Transition length: **full native-rate decode** of all 27 clips (~81,000 frames).
- Style: **1 fps → 2,703 frames** at 854×480.
- Line weight: 7 videos re-downloaded as 12s **native 1080p** samples (480p cannot
  resolve stroke width).
- Narration: 9 YouTube auto-caption tracks parsed at word-timestamp level (full videos,
  not just the windows).

### Measurement pipeline

1. **Cut/static classification** — per frame pair: mean abs difference, fraction of
   pixels changed >20/255, and luminance shift. Pairs below MAD 0.8 / 0.4% changed are
   "static".
2. **Motion vs. content change** — for every non-static pair, Farneback optical flow,
   then *warp frame A by its own flow and re-difference against B*. Change that
   survives motion compensation is a content change (cut/reveal); change that
   disappears is real motion. This is what makes the cut/motion distinction trustworthy.
3. **Long-baseline drift** — adjacent-frame tests can miss slow Ken Burns moves, so
   every shot was additionally tested **first-frame → last-frame** with ECC affine
   alignment *and* Hanning-windowed phase correlation (subpixel, robust).
4. **Two-tier event detection** — after filmstrip review revealed held-background
   foreground swaps, all change events were re-detected and split by spatial extent:
   `FULL_CUT` ≥25% of frame, `FG_SWAP` 2–25%, `MICRO` 0.5–2%.
5. **Visual adjudication** — labelled contact sheets and 6-panel filmstrips were
   rendered and read directly, not just measured.

---

## 2. Motion table

### 2.1 Frame-interval classification (10 fps, 27,723 pairs pooled)

| Class | Pooled | Axen | Mack | Stickly | HistoryAlive | ThenFolk |
|---|---|---|---|---|---|---|
| **Static / held** | **96.56%** | 95.95% | 97.61% | 96.13% | 97.70% | 94.60% |
| Hard cut | 2.69% | 2.77% | 2.10% | 2.83% | 2.30% | 4.43% |
| Reveal (element appears) | 0.58% | 1.10% | 0.28% | 1.01% | 0.00% | 0.00% |
| Local motion | 0.17% | 0.18% | 0.01% | 0.03% | 0.00% | 0.97% |
| **Global camera move** | **0.00%** | 0.00% | 0.00% | 0.00% | 0.00% | 0.00% |

**% of runtime that is truly static: 94.6–97.7%.**
**% of runtime with sub-cut motion: 0.0–1.3%** (and none of it is camera motion).

### 2.2 Cut rate and shot duration

Shot durations are measured between consecutive visual-change events (`FULL_CUT` or
`FG_SWAP`), pooled per channel, discarding the first and last shot of each window
(truncated by the window edge).

| Channel | Runtime | FULL_CUT/min | FG_SWAP/min | **All changes/min** | mean | **median** | p10 | p25 | p75 | p90 |
|---|---|---|---|---|---|---|---|---|---|---|
| Axen | 15.0 min | 16.6 | 6.5 | **23.5** | 2.56s | **2.20s** | 0.90 | 1.40 | 3.38 | 4.60 |
| Mack | 15.0 min | 12.6 | 1.7 | **14.3** | 4.15s | **4.10s** | 1.74 | 2.80 | 5.30 | 6.86 |
| Stickly | 5.0 min | 21.2 | 7.6 | **28.8** | 2.07s | **1.92s** | 0.96 | 1.44 | 2.56 | 3.44 |
| HistoryAlive | 5.0 min | 13.8 | 0.0 | **13.8** | 4.34s | **4.25s** | 1.55 | 2.25 | 5.67 | 8.35 |
| ThenFolk | 5.0 min | 26.6 | 0.0 | **26.6** | 2.24s | **2.10s** | 1.29 | 1.62 | 2.77 | 3.31 |

Per-video full-cut rates: Axen 15.6 / 16.2 / 18.0; Mack 11.8 / 13.0 / 13.0;
Stickly 21.2; HistoryAlive 13.8; ThenFolk 26.6.

Note the two performance benchmarks sit at **opposite ends**: Mack (the growing
channel, 4.10s median shot, 14.3 changes/min) is *half the cut rate* of Axen
(2.20s, 23.5/min). There is no single "correct" pace — but Mack's slower pace comes
with 21-min runtimes, and Axen's faster pace with 8-min runtimes.

### 2.3 Transition type

Full native-frame-rate decode, run-length of elevated-difference frame pairs:

| Channel | n transitions | 1 frame | 2 frames | 3+ frames | median |
|---|---|---|---|---|---|
| Axen | 334 | **100.0%** | 0.0% | 0.0% | 33 ms |
| Mack | 214 | **100.0%** | 0.0% | 0.0% | 33 ms |
| Stickly | 144 | **100.0%** | 0.0% | 0.0% | 40 ms |
| HistoryAlive | 69 | **100.0%** | 0.0% | 0.0% | 33 ms |
| ThenFolk | 133 | **100.0%** | 0.0% | 0.0% | 33 ms |

**Every transition in the corpus is a 1-frame hard cut. Zero dissolves, zero fades,
zero wipes, zero slide transitions.** 894 transitions measured, 0 exceptions.

---

## 3. Motion taxonomy

This is the section the build depends on, so the evidence chain is stated explicitly.

### 3.1 Is there camera motion? No.

Per shot, first frame vs last frame:

| Channel | shots | median translation | median \|zoom\| | median phase-corr drift | shots with drift >1px |
|---|---|---|---|---|---|
| Axen | 254 | 0.00 px | 0.000% | 0.001 px | 11.0% |
| Mack | 190 | 0.00 px | 0.000% | 0.000 px | 5.8% |
| Stickly | 105 | 0.00 px | 0.000% | 0.001 px | 12.4% |
| HistoryAlive | 72 | 0.00 px | 0.000% | 0.000 px | 0.0% |
| ThenFolk | 136 | 0.00 px | 0.000% | 0.002 px | 0.0% |

The median shot moves **0.00 pixels and zooms 0.000%** across its entire duration.
Phase correlation is subpixel-accurate and would detect a Ken Burns move of even
0.1 px/s; it reports drift of 0.000–0.002 px. **There is no pan, no zoom, no
parallax, no drift anywhere in 45 minutes of footage.**

The small "drift >1px" fractions are not camera moves — they are shots where the
*content* changed (see 3.3), which displaces the phase-correlation peak.

### 3.2 Is the picture literally frozen between cuts? Almost always.

Unaligned first-vs-last-frame pixel change per shot:

| Channel | shots frozen (<0.1% of pixels changed) | shots with any content change |
|---|---|---|
| Axen | **84.3%** | 15.7% |
| Mack | **94.2%** | 5.8% |
| Stickly | **86.7%** | 13.3% |
| HistoryAlive | **100.0%** | 0.0% |
| ThenFolk | **100.0%** | 0.0% |

Median pixel change within a shot is **0.000%** for every channel. Two of five
channels are 100% frozen — every single shot is a still image held until the cut.

### 3.3 What is the remaining motion? Discrete foreground swaps.

Of shots that *do* change internally, the change is a **jump**, not a continuum:

| Channel | changing shots | continuous accumulation | discrete jump |
|---|---|---|---|
| Axen | 40 | 37.5% | **62.5%** |
| Mack | 11 | 9.1% | **90.9%** |
| Stickly | 14 | 28.6% | **71.4%** |

The statistically "continuous" cases were then **read as filmstrips**, and all
inspected cases turned out to be discrete swaps too, sampled such that both halves of
the shot changed. Examples:

- `TQd2k1pEXp4` w3 +86: a 23.4s "shot" where the sky and ground are pixel-identical
  throughout while the foreground cycles through digging → meat slabs → a row of
  people → spear-thrower → planting → sprouts. Six distinct compositions, one
  background.
- `C27Dd23jZzA` w2 +411: white background held; character pose and hand-lettered
  caption swap wholesale every ~3.4s.
- `2RJggsjlj4A` w3 +138: sky/ground held, characters and animals replaced; frames at
  +2.8s and +5.6s are bit-identical.

**Conclusion: zero frames of true character or element animation were found.** Limbs
never articulate, nothing tweens, nothing eases.

### 3.4 The taxonomy, with percentages

**By share of visual-change events:**

| Motion type | Axen | Mack | Stickly | HistoryAlive | ThenFolk |
|---|---|---|---|---|---|
| Full-frame hard cut (background replaced) | 70.6% | 88.1% | 73.6% | 100% | 100% |
| Foreground swap over held background | 27.8% | 11.7% | 26.4% | 0% | 0% |
| Micro pop-on (small label/annotation) | 1.3% | 0.2% | 0.0% | 0% | 0% |
| Camera move (pan/zoom/parallax) | **0%** | **0%** | **0%** | **0%** | **0%** |
| Character/element animation | **0%** | **0%** | **0%** | **0%** | **0%** |
| Dissolve / wipe / slide | **0%** | **0%** | **0%** | **0%** | **0%** |

**By share of runtime:** 94.6–97.7% frozen still; 2.1–4.4% cut frames;
0.0–1.3% element pop-on; 0.0% camera; 0.0% animation.

**Background persistence** (`FG_SWAP` per `FULL_CUT`) — how often a background is
reused for a follow-up beat rather than replaced:

| Axen | Mack | Stickly | HistoryAlive | ThenFolk |
|---|---|---|---|---|
| 0.39 | 0.13 | 0.36 | 0.00 | 0.00 |

Axen reuses a background for a second beat roughly **2 times in 5 cuts**. This is
cheap to produce and is a real, copyable device.

### 3.5 Intro vs body vs outro

Visual changes per minute by window:

| Video | Channel | early | mid | late |
|---|---|---|---|---|
| `TQd2k1pEXp4` | Axen | 29.4 | 30.6 | 30.6 |
| `wt_7Hp7d7I8` | Axen | 22.2 | 19.8 | 15.6 |
| `2RJggsjlj4A` | Axen | 20.4 | 18.6 | 21.0 |
| `AvF3bPcqZeM` | Mack | 16.8 | 12.0 | 12.6 |
| `C27Dd23jZzA` | Mack | 19.8 | 11.4 | 13.8 |
| `th-0rmRYBSg` | Mack | 16.2 | 13.2 | 12.6 |
| `cCxzQ_Vv3Dc` | Stickly | 29.4 | 30.6 | 26.4 |
| `jy9P9I7QIN0` | HistoryAlive | 13.8 | 10.2 | 17.4 |
| `KO_035Jkc2E` | ThenFolk | 31.8 | 22.8 | 25.2 |

Mack cuts **~40% faster in the first 100 seconds** than in the body (19.8 → 11.4 on
its 1.6M video), then settles. ThenFolk does the same (31.8 → 22.8). Axen's hero
video does not vary. The hook is paced faster than the body on 6 of 9 videos.

---

## 4. Style metrics

1 fps sampling, 2,703 frames, measured at 854×480. Line weight measured separately at
native 1080p.

| Metric | Axen | Mack | Stickly | HistoryAlive | ThenFolk |
|---|---|---|---|---|---|
| Mean saturation (0–1) | 0.270 | **0.161** | 0.117 | 0.277 | **0.348** |
| Mean brightness (0–1) | 0.786 | 0.760 | 0.793 | 0.715 | 0.756 |
| Edge/line density | 4.28% | 4.24% | **2.73%** | 7.91% | 7.56% |
| Near-white fraction | 29.3% | 33.2% | **44.5%** | 14.6% | **7.4%** |
| Ink fraction (<90/255) | 12.87% | 9.39% | 13.09% | 16.38% | 9.62% |
| Distinct colour bins | 16.2 | 15.5 | **13.1** | 28.1 | **28.7** |
| Foreground/background contrast | 169.5 | 170.3 | **183.3** | 146.6 | 148.0 |
| **Modal stroke @1920px wide** | **5.5 px** | **9.0 px** | 6.0 px | 6.0 px | **3.0 px** |
| Frames containing text | 25.7% | 32.8% | **7.3%** | 73.3% | **73.6%** |

### Dominant palettes (k-means, k=6, with coverage)

**Axen** — warm savanna, high-key
`#EAD6A0` 27.9% · `#F6F9FB` 24.5% · `#E59348` 15.1% · `#C59F78` 14.2% · `#778D53` 11.0% · `#32291B` 7.3%

**Mack** — desaturated grey/ochre, the most muted of the set
`#8B8B8B` 35.2% · `#C99964` 33.7% · `#706B65` 10.4% · `#F0F2F2` 9.6% · `#453B37` 6.0% · `#13100F` 5.2%

**Stickly** — cool sage/off-white, most minimal
`#FBFBFB` 42.0% · `#DFE5DC` 26.7% · `#B8C9B6` 11.9% · `#909A88` 11.2% · `#686357` 4.6% · `#131412` 3.5%

**History Alive** — cool blue/tan, busiest
`#B3D4E1` 23.9% · `#ECF3EF` 22.1% · `#BEAA7E` 19.6% · `#715A4E` 12.9% · `#778891` 10.8% · `#29231D` 10.7%

**ThenFolk** — saturated amber, most colourful, least white
`#DFA265` 47.8% · `#9D8963` 16.3% · `#F0E29D` 14.2% · `#66583C` 8.3% · `#EFF1EC` 8.2% · `#1E150E` 5.1%

The two channels with real traction (Axen, Mack) sit in the **low-saturation,
high-near-white, low-colour-count** corner: 13–16 distinct colour bins, 29–33%
near-white, saturation 0.16–0.27. The palette is deliberately impoverished.

---

## 5. Character and composition design spec

Derived from reading labelled contact sheets (24 tiles per channel). Numbers marked
*(measured)* come from the metrics above; the rest are visual observations.

### Character construction

- **Axen**: true stick figure. Circular pure-white head with a **heavy black outline**,
  2 dot eyes and a small mouth, messy black scribble hair drawn as a solid cap. Limbs
  and torso are **single strokes with no volume** — no shoulders, no hands, no feet.
  Bodies are drawn at roughly 25–45% of frame height standing on a groundline.
- **Mack**: notably *less* stick-like. Head circle plus a **drawn body with volume** —
  fur garment, beard, visible hands and feet, shading. Closer to a cartoon than a
  stick figure. Heaviest line in the set at **9.0 px @1920** *(measured)*.
- **Stickly**: round white head, thin stick limbs, but dressed in **filled-shape modern
  clothing** (t-shirts, trousers) and set in contemporary interiors. Lowest edge
  density and highest near-white *(measured)* — the cleanest, most "corporate" look.
- **ThenFolk**: thinnest line in the set at **3.0 px @1920** *(measured)*, most detailed
  rendering, painterly textured backgrounds.

### The single strongest shared convention

**Humans are drawn crudely; animals and threats are drawn well.** In Axen and Mack,
the human is a 4-stroke stick figure while the lion, sabre-tooth, bear or mammoth in
the same frame is a semi-realistic, shaded, correctly-proportioned illustration. This
asymmetry is consistent across every Axen and Mack frame examined and is the most
recognisable signature of the style. It is also economically rational: the character
is trivial to generate, the animal carries the production value.

### Composition rules

- **Full-bleed 16:9**, no borders, no frames, no letterboxing, no logo bug, no
  progress furniture.
- **Flat side-on "stage" view at eye level.** No perspective camera, no vanishing
  points, no foreshortening. Figures stand on a single groundline.
- **Two-band background**: a flat or lightly-graded sky band over a flat ground band,
  horizon around 40–55% of frame height. Backgrounds carry almost no detail —
  Axen's near-white fraction of 29.3% *(measured)* is mostly empty sky.
- Recurring frame archetypes, in observed frequency order:
  1. Stage shot — 1–6 figures on a groundline against the two-band background.
  2. Split-panel comparison — a hard vertical divider, two states side by side
     (Axen "RAW MEAT | COOKED MEAT"; Mack before/after).
  3. Diagram/infographic on white or near-white — maps, timelines, stacked-layer
     explainers, scale comparisons.
  4. Big-head close-up — a single face filling much of the frame for an emotional beat.
- **Icon vocabulary instead of text** (heaviest in Mack `AvF3bPcqZeM`, which is only
  8.3% text *(measured)*): red ✗, green ✓, ❓, ⚠, arrows, hearts, lightbulbs, skulls,
  magnifying glasses, shields, balance scales.

---

## 6. On-screen text conventions

Detector validated visually against labelled overlay sheets — it correctly boxed
hand-lettered captions and correctly returned zero on text-free frames, with a low
false-positive rate on map/label art.

| Video | Channel | Overall | early | mid | late |
|---|---|---|---|---|---|
| `TQd2k1pEXp4` | Axen | 14.7% | 27.0% | 17.0% | 0.0% |
| `wt_7Hp7d7I8` | Axen | 29.3% | 30.0% | 24.0% | 34.0% |
| `AvF3bPcqZeM` | Mack | 8.3% | 8.0% | 0.0% | 17.0% |
| `th-0rmRYBSg` | Mack | 8.3% | 15.0% | 10.0% | 0.0% |
| `C27Dd23jZzA` | Mack | **81.7%** | 59.0% | 100.0% | 86.0% |
| `cCxzQ_Vv3Dc` | Stickly | 7.3% | 17.0% | 2.0% | 3.0% |
| `jy9P9I7QIN0` | HistoryAlive | 73.3% | 56.0% | 87.0% | 77.0% |
| `KO_035Jkc2E` | ThenFolk | 73.6% | 50.5% | 81.2% | 89.1% |

**There are no burned-in subtitles anywhere in the corpus.** No channel captions its
narration. All on-screen text is editorial.

Two distinct strategies, and note they are **not** split by channel — Mack runs both:

- **Sparse-label** (Axen, Stickly, Mack's `AvF3bPcqZeM`/`th-0rmRYBSg`): 7–29% of
  frames. Text is short and diegetic — panel labels ("RAW MEAT"/"COOKED MEAT"),
  sound effects ("HUFF!", "PUFF!"), state markers ("(before)"), axis labels.
- **Caption-driven** (Mack's `C27Dd23jZzA`, HistoryAlive, ThenFolk): 73–82% of frames.
  Large hand-lettered all-caps phrases carrying the narrative beat — "MIGHT SOUND
  WILD…", "THE INTOXICATION HYPOTHESIS", "SHELTER WAS EVERYTHING", "1,000,000 YEARS
  AGO", "IT GETS STRANGER".

Mack's **highest-performing video (1.6M) is its most text-heavy (81.7%)** while its
293K video is its least (8.3%) — worth noting, though n=3 proves nothing causal.

**Typography**: hand-lettered / marker-style all-caps sans, irregular baselines,
heavy weight, pure black on light ground, frequently with a hand-drawn underline,
bracket, arrow or starburst. No system fonts, no drop shadows, no boxes-with-opacity.

**Placement** (fraction of detected text boxes):

| Channel | top third | middle | bottom third |
|---|---|---|---|
| Axen | 28.4% | 26.4% | 45.2% |
| Mack | 40.7% | 16.7% | 42.6% |
| HistoryAlive | 56.8% | 10.7% | 32.5% |
| ThenFolk | 40.3% | 19.3% | 40.4% |
| Stickly | 20.8% | 20.8% | 58.3% |

Text goes **top or bottom, rarely middle** — the middle band is reserved for the
illustration.

---

## 7. Narration pacing and audio

WPM computed from word-level caption timestamps over the **full** videos.

| Video | Channel | words | span | **WPM** | median inter-word gap | gaps >0.6s |
|---|---|---|---|---|---|---|
| `wt_7Hp7d7I8` | Axen | 2,231 | 625s | **214.2** | 0.240s | 6.4% |
| `2RJggsjlj4A` | Axen | 1,438 | 454s | **190.2** | 0.280s | 9.1% |
| `TQd2k1pEXp4` | Axen | 1,565 | 514s | **182.5** | 0.280s | 10.6% |
| `KO_035Jkc2E` | ThenFolk | 1,525 | 509s | **179.8** | 0.240s | 15.0% |
| `AvF3bPcqZeM` | Mack | 3,473 | 1310s | **159.1** | 0.320s | 17.7% |
| `jy9P9I7QIN0` | HistoryAlive | 2,505 | 978s | **153.7** | 0.320s | 20.8% |
| `th-0rmRYBSg` | Mack | 3,253 | 1341s | **145.5** | 0.320s | 22.2% |
| `C27Dd23jZzA` | Mack | 3,187 | 1315s | **145.4** | 0.320s | 20.2% |
| `cCxzQ_Vv3Dc` | Stickly | 3,602 | 1494s | **144.6** | 0.320s | 21.0% |

Channel means: **Axen 195.6, ThenFolk 179.8, HistoryAlive 153.7, Mack 150.0,
Stickly 144.6.**

Axen narrates **~30% faster than Mack**. Axen also pauses far less — only 6–11% of
inter-word gaps exceed 0.6s, versus 18–22% for Mack/Stickly/HistoryAlive. Axen is
relentless; Mack breathes.

### Words per visual shot

| Channel | WPM | changes/min | **words per shot** | sec per shot |
|---|---|---|---|---|
| Axen | 195.6 | 23.1 | **8.9** | 2.59 |
| Mack | 150.0 | 14.3 | **10.5** | 4.21 |
| HistoryAlive | 153.7 | 13.8 | **11.1** | 4.35 |
| ThenFolk | 179.8 | 26.6 | **6.8** | 2.26 |
| Stickly | 144.6 | 28.8 | **5.0** | 2.08 |

The two channels with traction land at **9–11 narration words per visual** — roughly
one image per sentence or clause. This is the single most useful scheduling number in
the report: **cut on the clause, not on a timer.**

### Music and SFX

40ms RMS envelope; comparison of speech level (p75) against the pause floor (p05):

| Channel | speech | pause floor | delta | verdict |
|---|---|---|---|---|
| Axen | −21.7 dB | **−65.3 dB** | 43.6 dB | dry narration, no bed |
| Mack | −25.1 dB | **−73.0 dB** | 47.9 dB | dry narration, no bed |
| Stickly | −30.7 dB | **−82.0 dB** | 51.3 dB | dry narration, no bed |
| HistoryAlive | −21.1 dB | **−63.2 dB** | 42.1 dB | dry narration, faint at most |
| ThenFolk | −16.6 dB | **−72.8 dB** | 56.2 dB | dry narration, no bed |

**No channel uses a music bed, and no SFX were detected.** Pause floors of −63 to
−82 dBFS are effectively digital silence. This is pure dry voiceover end to end — a
significant and cheap-to-copy finding.

Integrated loudness (100s windows): ThenFolk −15.7, Axen −20.4, HistoryAlive −20.6,
Mack −23.4, Stickly −29.2 LUFS. Against YouTube's ≈−14 LUFS normalisation target,
ThenFolk is the best-mastered and Stickly is ~15 LU under.

Speech/silence ratio: Axen is near-continuous (1.6% silence), Mack 10.7%,
ThenFolk 19.3%, Stickly 16.7%, HistoryAlive 6.2%.

---

## 8. ThenFolk (`KO_035Jkc2E`) — new-entrant sample, not a failure case

**This video was published 2026-07-29 and had 60 views when measured (3 days old, from
a channel with no accumulated authority). Its view count reflects channel age and
distribution, not visual craft. No inference about visual quality can be drawn from
its performance, and none is drawn here.** It is reported as a *new-entrant execution
sample*.

Measured against Axen and Mack, its execution is **not worse — on several axes it is
better**:

| Metric | ThenFolk | Axen | Mack | Read |
|---|---|---|---|---|
| Illustration detail (edge density) | **7.56%** | 4.28% | 4.24% | ~1.8× more detailed |
| Distinct colour bins | **28.7** | 16.2 | 15.5 | far richer palette |
| Near-white fraction | **7.4%** | 29.3% | 33.2% | fully painted, no empty space |
| Saturation | **0.348** | 0.270 | 0.161 | most saturated |
| Line weight @1920 | **3.0 px** | 5.5 px | 9.0 px | finest linework |
| Integrated loudness | **−15.7 LUFS** | −20.4 | −23.4 | closest to YouTube target |
| Text density | 73.6% | 25.7% | 32.8% | caption-driven, like Mack's 1.6M video |
| Native resolution | 3840×2160 @60 | 3840×2160 @30 | 1920×1072 @30 | highest spec |

Visual review of its contact sheet confirms this: painterly textured backgrounds,
composed infographic panels (balance scales, contracts, timelines, 2×2 comparison
grids), consistent warm palette, competent hand-lettering. It is a **higher-production
artefact than Axen** by every style metric measured.

Where it differs measurably in *grammar*:

- **Cuts 2.1× faster than Mack** (26.6 vs 12.6 full cuts/min) and holds the shortest
  shots in the corpus (median 2.10s, p90 3.31s — it essentially never holds a shot
  past 3.3s).
- **6.8 narration words per visual**, versus 9–11 for Axen/Mack. Images change faster
  than the sentences do.
- **Zero background reuse** (0.00 FG_SWAP per cut) — every beat is a brand-new
  full-frame illustration, the most expensive possible strategy.
- **100% of shots pixel-frozen**, same as HistoryAlive.

So the honest summary: ThenFolk is a *more expensive, faster-cut, text-denser*
execution of the same fundamentally static grammar. If anything it demonstrates that
the visual bar in this niche is now higher than Axen's own hero video.

---

## 9. Reproducible spec

Concrete numeric rules a renderer must satisfy to sit inside the reference
distribution. Targets are given for the **Axen pole** (fast, 8-min) and the
**Mack pole** (slower, 20-min); pick one and be internally consistent.

### Motion

1. **Render static images only. Do not implement animation.** 0 of 894 transitions and
   0 of 757 shots in this corpus contain character or element animation.
2. **Do not implement camera moves.** No Ken Burns, no pan, no zoom, no parallax.
   Measured median drift across a shot: 0.000–0.002 px. Adding a slow zoom would make
   the output *less* like the reference, not more.
3. **All transitions are 1-frame hard cuts.** No dissolves, fades, wipes or slides.
   Transition duration = exactly 1 frame (33 ms @30fps). 100% of 894 measured.
4. Target **≥94.5% of runtime as frozen frames**. Anything below ~94% means something
   is moving that should not be.
5. Optional, and the only "motion" worth building: **foreground swap on a held
   background** — keep the background bitmap byte-identical and replace only the
   figures. Budget **0.35–0.40 swaps per full cut** (Axen/Stickly) or 0.13 (Mack).
   Zero is also valid (HistoryAlive, ThenFolk).

### Pacing

6. **Cut rate**: Axen pole **16–18 full cuts/min** (23.5 total changes/min);
   Mack pole **12–13 full cuts/min** (14.3 total changes/min). Avoid >27/min.
7. **Shot duration**: Axen pole median **2.2s**, p10 0.9s, p90 4.6s;
   Mack pole median **4.1s**, p10 1.7s, p90 6.9s.
8. **Never hold a shot past ~8.5s** (p90 ceiling across all channels is 3.3–8.4s).
9. **Cut on clause boundaries at 9–11 narration words per image** (Axen 8.9,
   Mack 10.5, HistoryAlive 11.1). Do not cut on a fixed timer.
10. **Pace the hook faster**: 1.4–1.7× the body cut rate for the first 100 seconds,
    then settle (observed on 6 of 9 videos).

### Narration

11. **WPM**: Axen pole **185–215**; Mack pole **145–160**.
12. **Inter-word gap** median 0.24s (fast) to 0.32s (slower); keep gaps >0.6s to
    6–11% (Axen) or 18–22% (Mack) of word boundaries.
13. **No music bed and no SFX.** Pause floor must sit below −60 dBFS. This is the
    reference behaviour for all 5 channels.
14. **Master to −14 to −16 LUFS integrated.** Only ThenFolk is close; Axen (−20.4) and
    especially Stickly (−29.2) are leaving loudness on the table.

### Style

15. **Palette: 13–16 distinct colour bins per frame.** Hard-cap the palette. This is
    the single most objective style constraint and the most commonly violated by
    generative renderers.
16. **Mean saturation 0.16–0.27.** Mack, the growing channel, sits at 0.161.
17. **Near-white fraction 29–45%.** Backgrounds must be mostly empty.
18. **Edge/line density 2.7–4.3%.** ThenFolk/HistoryAlive at 7.5–7.9% are the
    detail-heavy outliers; Axen/Mack are sparse.
19. **Stroke weight 5.5–9.0 px at 1920px wide** (≈11–18 px at 4K). Uniform weight —
    no tapering, no variable-width calligraphic strokes.
20. **Foreground/background luminance contrast ≈170** (0–255 scale). Pure-black ink on
    high-key ground.
21. **Two-band background**: flat sky over flat ground, horizon at 40–55% frame height,
    minimal background detail.
22. **Asymmetric fidelity — the key signature**: render humans as crude stick figures
    (circular white head, heavy outline, single-stroke limbs, no volume) and animals /
    threats as detailed shaded illustrations, in the same frame.
23. **Flat eye-level side-on staging.** No perspective camera, no vanishing point.
24. Frame archetype mix, approximately: stage shot dominant, plus split-panel
    comparison, white-ground diagram/map/timeline, and occasional big-head close-up.

### Text

25. **Pick one text strategy and hold it.** Sparse-label: 7–29% of frames.
    Caption-driven: 73–82% of frames. Do not land in between.
26. **No burned-in subtitles.** Zero channels caption their narration.
27. **Hand-lettered all-caps marker-style sans**, irregular baseline, heavy weight,
    pure black, with hand-drawn underlines/brackets/arrows. No system fonts, no drop
    shadows, no translucent boxes.
28. **Place text in the top or bottom third** (~85% of observed placements); keep the
    middle band for the illustration.
29. Use an **icon vocabulary** (✗ ✓ ❓ ⚠ arrows hearts skulls scales lightbulbs) as a
    substitute for prose — heaviest in Mack's sparse-text videos.

---

## 10. Caveats and what could not be measured

- **Sampling is 45 min of ~139 min of total runtime.** Three 100s windows per video
  cover 20–39% of an Axen video but only 23% of a Mack video. Shots longer than 100s
  are structurally unobservable, and the first/last shot of each window is truncated
  (excluded from duration stats), which biases the duration distribution slightly
  **downward**. True median shot length may be marginally higher than reported.
- **Motion was measured at 480p.** A subpixel effect below ~0.05 px at 480p would be
  invisible. Phase correlation puts the ceiling on undetected drift at well under
  0.01 px/frame, so this does not threaten the "no camera motion" conclusion, but it
  is a stated limit.
- **Line weight is from 12s native-1080p samples of 7 videos**, not the full corpus.
  Axen and ThenFolk are natively 4K; measuring their 1080p rendition slightly
  underestimates true authored stroke width. Two earlier estimators
  (area/perimeter and distance-transform mode) were discarded as biased — the reported
  figures use horizontal run-length mode, which is the reliable one.
- **Text detection is a morphological detector, not OCR.** It was validated visually
  and performs well on large hand-lettering, but likely **under-counts small text**
  and occasionally fires on dense map labels. Treat the percentages as ±5–10 points.
  Text *content* was read manually from contact sheets, not extracted.
- **WPM comes from YouTube auto-captions**, which drop or mis-segment some words;
  expect ±5%. Speech/silence ratios come from the 100s windows only.
- **Music detection is level- and flatness-based, not source separation.** A very quiet
  bed more than 60 dB below speech would read as "no bed". Given floors of −63 to
  −82 dBFS this is a safe conclusion, but it is inference, not stem isolation.
- **Two downloads initially failed** (`cCxzQ_Vv3Dc` w2, `jy9P9I7QIN0` w2,
  `th-0rmRYBSg` w2 — ffmpeg exit 8) and were successfully retried. No window is
  missing from the final dataset. All 9 video IDs resolved.
- **n is small per channel outside Axen and Mack** — Stickly, HistoryAlive and
  ThenFolk are 1 video / 5 minutes each. Their per-channel figures are indicative only.
- **Not measured**: thumbnail/packaging design, title conventions, retention curves,
  audience data, colour-grading pipeline, the actual generation tooling used, and
  whether Mack/Trenn/Mogo/"His Story 404" share a pipeline (only Mack was sampled
  here — if they are one operator, Mack's conventions should be read as a deliberate,
  repeatable formula rather than one channel's taste).
- Character proportion figures in §5 (head size, body height as % of frame) are
  **visual estimates from contact sheets, not measured statistics**, and are flagged
  as such inline.
