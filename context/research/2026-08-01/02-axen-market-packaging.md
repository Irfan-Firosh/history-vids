# Axen / "Ancient Humans" Faceless Niche — Market & Packaging Research

**Date:** 2026-08-01 (data pulled 2026-08-01/02)
**Benchmark:** [@AxenCool](https://www.youtube.com/@AxenCool) — `UC_7R-sfi7bi8dkzmSlBdUVw`
**Method:** NexLev MCP (YouTube analytics), `yt-dlp` raw metadata, direct thumbnail inspection.
**Labelling:** every figure is tagged **SOURCED** (tool/URL given) or **ESTIMATE** (reasoning given).

---

## Executive summary

1. **Axen is a 95-day-old channel that hit 5.18M views on 11 videos, then stopped uploading.** First upload 2026-04-28, last upload 2026-06-26 — **36 days dormant as of today**. [SOURCED: `youtube_channel_about`, `yt-dlp` upload_date]
2. **One video is 59% of the channel.** `TQd2k1pEXp4` = 3,052,090 of 5,175,133 total views. Top 4 videos = 96.4%. Median video = 26,001 views. **Top:median = 117x.** [SOURCED: `yt-dlp`, `youtube_video_details`]
3. **Axen is NOT monetized.** NexLev `check_channel_monetization` returns `isMonetized: false` while 9 of 9 comparable peers return `true`. Axen has earned an estimated **$0 AdSense** on 5.18M views. [SOURCED: `check_channel_monetization`, `get_batch_channel_metrics_v2`]
4. **The niche RPM is poor: $2.29–$6.93.** Cohort median **$3.78**. This is a *low*-value niche by NexLev's own scale ($5–10 = average). [SOURCED: `get_video_rpm`, `get_batch_channel_metrics_v2`]
5. **Length is the single strongest economic lever.** Channels averaging ≥20 min earn **2.0x the RPM** ($6.79 vs $3.34 median) and show **7.5x the median views-per-video** of sub-12-min channels in the same 2026 cohort. [SOURCED: `get_batch_channel_metrics_v2`, `get_similar_channels`]
6. **The swarm is real and mostly dead.** 136 similar channels; **63 (46%) launched on or after Axen's own launch date**; of those, **65% have <100 subscribers** and **38% have <1,000 total views**. Zero of the post-Axen cohort has cracked 100K subs. [SOURCED: `get_similar_channels`]
7. **Search saturation is severe.** Last-30-day SERP for "what did ancient humans do": median **3,494 views**, 25% of results under 100 views, only 10% above 100K. [SOURCED: `youtube_search`]
8. **The title formula is measurable and it works** — but only in combination with channel authority. Axen question-form titles median **163,882** views vs statement-form **11,593** (14.1x). Titles containing "Ancient Human(s)" median **445,667** vs **20,517** (21.7x). [SOURCED: computed from `yt-dlp` view counts]

**Verdict: the packaging is worth copying; the business model is not.** Entering as a short-form (~8 min) AdSense play in mid-2026 is a bad trade. The only defensible entry is long-form (20–25 min) plus a non-AdSense revenue line — which is exactly what the actual market leader is doing.

---

## Channel profile — Axen

### Headline metrics [SOURCED: `youtube_channel_about`, `get_channel_analytics`]

| Metric | Value |
|---|---|
| Channel ID | `UC_7R-sfi7bi8dkzmSlBdUVw` |
| Subscribers | 50,100 (NexLev cache showed 49,900 / 46,800 across endpoints — see *Data quality*) |
| Total views | 5,120,325 (about endpoint) / **5,175,133** (sum of live per-video counts) |
| Videos | 11 (0 Shorts) |
| Joined / first upload | **2026-04-28** |
| Last upload | **2026-06-26** (36 days ago) |
| Days since start | 95 |
| Avg video length | 7:51 |
| Country | United States |
| Category | History / Myths and Folktales / Psychology |
| Faceless | **true, 98% confidence**, format = `animation` [SOURCED: `check_faceless_channel`] |
| Monetized | **false** [SOURCED: `check_channel_monetization`, bypassCache=false, cached <24h] |
| Predicted RPM | $3.77 channel-level; $2.29 on top video (range $0.88–$3.70) [SOURCED: `get_batch_channel_metrics_v2`, `get_video_rpm`] |

### Complete video log [SOURCED: `yt-dlp -J` per video + `youtube_video_details`]

Chronological. Views/likes as of 2026-08-01.

| # | Upload | ID | Title | Views | Likes | Cmts | Len | Like% |
|--:|---|---|---|--:|--:|--:|--:|--:|
| 1 | 2026-04-28 | `2RJggsjlj4A` | How Did Ancient Humans Survive the World's Deadliest Predators? | 1,045,083 | 13,792 | — | 7:32 | 1.32% |
| 2 | 2026-04-28 | `ebFhKmweSHo` | Weird Feelings You Get That Your Brain Can't Explain... | 26,001 | 1,052 | 58 | 5:21 | 4.04% |
| 3 | 2026-05-04 | `TQd2k1pEXp4` | **What Did Ancient Humans Do all Day Before Jobs Existed?** | **3,052,090** | 89,419 | 6,400 | 8:32 | 2.93% |
| 4 | 2026-05-05 | `lJVPvTGUftQ` | How Did Ancient Humans Have Privacy? | 255,545 | 10,841 | 687 | 5:14 | 4.24% |
| 5 | 2026-05-27 | `UFAPaRxXEAo` | Napoleon Did Some Truly Bizarre Things... | 9,498 | 252 | 40 | 5:42 | 2.65% |
| 6 | 2026-05-30 | `wt_7Hp7d7I8` | How Did Ancient Humans Survive Deadly Winters? | 635,789 | 11,197 | 688 | 10:24 | 1.76% |
| 7 | 2026-06-03 | `H6pReZzpmfE` | What Was the World Like in Ancient Human Times? | 23,531 | 703 | 97 | 7:03 | 2.99% |
| 8 | 2026-06-05 | `q_Rqvd1ayUE` | Our WORLD is F*cked Up... | 11,593 | 574 | 124 | 6:59 | 4.95% |
| 9 | 2026-06-11 | `9SmcjthU5Yk` | Why Does the OCEAN Get Creepier the Deeper You Go? | 72,219 | 1,833 | 159 | 9:51 | 2.54% |
| 10 | 2026-06-18 | `dpGpFq9RZfg` | What Did Ancient Human Education Look Like? | 23,267 | 568 | 141 | 10:16 | 2.44% |
| 11 | 2026-06-26 | `kEc6rFGrdh4` | Do Animals Live More Freely Than Humans? | 20,517 | 561 | 187 | 9:23 | 2.73% |

### View distribution

- **Total:** 5,175,133 · **Mean:** 470,467 · **Median:** 26,001
- **Top video share:** 59.0% · **Top 2:** 79.2% · **Top 4:** 96.4%
- **Top : median ratio:** **117x**
- Length range 5:14–10:24; mean 7:51. **No video exceeds 10.5 minutes.**

### How the channel ramped

- **Cold-start hit on day 1.** The very first upload (`2RJggsjlj4A`, 2026-04-28) did **1.05M views**. There was no ramp — the channel worked immediately. [SOURCED]
- **Peak on video 3** (day 6): 3.05M views.
- **Then monotonic decay.** Videos 7–11 (June) averaged 30,225 views — a **99.0% drop** from the peak video. [ESTIMATE from SOURCED view counts]
- **Cadence:** Apr 2 videos → May 4 → Jun 5 → **Jul 0**. Roughly 1 video/6.5 days during the active period; **zero for the last 36 days**.

**Interpretation [ESTIMATE]:** The pattern — instant 1M on video #1, no subscriber-driven floor, total stall — is consistent with a channel that won a *browse/suggested* lottery rather than building an audience. 50.1K subs against a 26K median view count means subscribers are not reliably returning. The 36-day silence plus non-monetized status suggests either abandonment or a monetization/policy problem.

---

## The hit formula

### Which videos outperform

Four videos cleared 250K; seven did not. The split is clean and it is **semantic, not production-level** — all 11 use the identical art style, voice, and length band.

**Winners (median 445,667):**
- How Did Ancient Humans Survive the World's Deadliest Predators? — 1.05M
- What Did Ancient Humans Do all Day Before Jobs Existed? — 3.05M
- How Did Ancient Humans Have Privacy? — 255K
- How Did Ancient Humans Survive Deadly Winters? — 636K

**Losers (median 23,267):** the Napoleon video (9.5K), the "Our WORLD is F*cked Up" rant (11.6K), "Weird Feelings" (26K), "Ancient Human Education" (23K), "What Was the World Like" (23.5K), "Do Animals Live More Freely" (20.5K), ocean video (72K).

### The three variables that separate them [SOURCED: computed on Axen's 11 titles]

| Variable | With | Without | Multiple |
|---|--:|--:|--:|
| Title ends in `?` | median **163,882** (n=8) | median 11,593 (n=3) | **14.1x** |
| Contains "Ancient Human(s)" | median **445,667** (n=6) | median 20,517 (n=5) | **21.7x** |
| Named historical figure (Napoleon) | 9,498 (n=1) | — | worst video on channel |

### The actual formula

> **A question about a universal modern experience, relocated into prehistory.**

The winners are not history questions. They are **present-tense anxieties wearing a prehistoric costume**:
- *jobs* → "Do all Day Before Jobs Existed"
- *privacy* → "Have Privacy"
- *winter/comfort* → "Survive Deadly Winters"
- *fear/danger* → "Survive the World's Deadliest Predators"

The losers break this in one of two ways: they drop the modern anchor ("What Was the World Like in Ancient Human Times?" — no modern concept at all, 23.5K), or they drop the prehistoric frame (Napoleon, ocean, "Our WORLD is F*cked Up").

**"Ancient Human Education" (23K) is the instructive failure**: it has both halves — an ancient-human frame *and* a modern concept (education) — but "Look Like?" is a weak, passive verb with no stake. The winners all use a verb implying **threat or deprivation** (*survive*, *do all day without*, *have privacy*). Confirmation from the comment data below: viewers respond to the *stakes*, not the facts.

### Engagement quality

`TQd2k1pEXp4` carries a **2.93% like rate and 6,400 comments** on 3.05M views. Axen's channel-wide like rate is 1.32%–4.95%. For reference, `lJVPvTGUftQ` ("Privacy") has the highest at **4.24%**. High like rates on the modern-anchor videos support the thesis that the emotional payload — not the history — drives performance.

---

## Title grammar

### Corpus: 92 real titles [SOURCED: `yt-dlp` from Axen + Mack + Stickly + Ink Explainer + Before Civilization + ThenFolk + Oddlyhuman]

| Pattern | Count | Share |
|---|--:|--:|
| Ends with `?` | 75/92 | **82%** |
| Starts with an interrogative (How/What/Why/When/Did/Do/Is/Were/Which/At What) | 79/92 | **86%** |
| Contains "Ancient Human(s)" | 51/92 | **55%** |
| Contains ancient/early/prehistoric human | 53/92 | 58% |
| Starts "How Did…" | 19/92 | 21% |
| Starts "Why …" | 21/92 | 23% |
| Starts "What Did…" | 9/92 | 10% |
| Contains a modern-life concept anchor | 22/92 | 24% |
| Contains a threat/superlative word | 15/92 | 16% |
| Contains a survival verb | 10/92 | 11% |
| Uses ellipsis "…" | 4/92 | 4% |
| ALL CAPS | 0/92 | 0% |

**Length: median 7 words / 44 characters** (mean 7.7 words, 45.0 chars; range 4–13 words).

### The reusable title grammar

```
[INTERROGATIVE] + [AUX] + "Ancient Humans" + [HIGH-STAKES VERB] + [MODERN-LIFE NOUN] + "?"
```

Concretely, ranked by observed performance:

1. **`How Did Ancient Humans <SURVIVE|ESCAPE|HANDLE> <THREAT>?`** — highest and most repeated across the swarm.
2. **`What Did Ancient Humans Do <WHEN|BEFORE> <MODERN CONDITION>?`** — the 3M pattern.
3. **`Why <Did|Don't|Couldn't> <Ancient Humans|We|Animals> <VERB> <NOUN>?`** — Mack/Stickly's workhorse.
4. **`<Did|Were> Ancient Humans <TABOO PROPERTY>?`** — yes/no curiosity gap (mating, incest, lifespan, sexuality).

**Rules the data supports:**
- Always end with `?` (82%; 14.1x on Axen).
- Keep it to **6–8 words / ~44 chars**.
- Include the literal string **"Ancient Humans"** (21.7x on Axen) — it is a *search-and-suggest keyword*, not just a theme.
- Use Title Case, never ALL CAPS (0/92).
- Avoid ellipsis (4/92 — and 3 of Axen's 4 worst videos use it).
- Avoid named historical figures — Napoleon was Axen's single worst video.
- The object of the question must be something the viewer **did today** (sleep, work, wash, argue, get bored, get sick, parent, eat).

### 40+ real titles from the corpus

**Axen (11/11):**
1. How Did Ancient Humans Survive the World's Deadliest Predators? — 1,045,083
2. What Did Ancient Humans Do all Day Before Jobs Existed? — 3,052,090
3. How Did Ancient Humans Have Privacy? — 255,545
4. How Did Ancient Humans Survive Deadly Winters? — 635,789
5. What Was the World Like in Ancient Human Times? — 23,531
6. What Did Ancient Human Education Look Like? — 23,267
7. Do Animals Live More Freely Than Humans? — 20,517
8. Why Does the OCEAN Get Creepier the Deeper You Go? — 72,219
9. Weird Feelings You Get That Your Brain Can't Explain... — 26,001
10. Our WORLD is F*cked Up... — 11,593
11. Napoleon Did Some Truly Bizarre Things... — 9,498

**Mack (60.2K subs, ~23 min):**
12. Why Do Humans Mostly Drink Cow's Milk? — 1,800
13. Did Ancient Humans Reproduce With Family Members? — 5,100
14. Why Did Ancient Humans Become Parents at 12? — 9,800
15. How Did the Other 6 Civilizations Disappear? — 5,200
16. What Happens When You Become Conscious Inside a Dream? — 12,000
17. Is Your Inner Voice Really You? — 33,000
18. What Was History's Most Terrifying Disease? — 19,000
19. Why Didn't Ancient Humans Need Exercise? — 5,600
20. Did Cats Actually Domesticate Humans? — 9,200
21. Did Ancient Humans Kill the Other Human Species? — 18,000
22. How Did Ancient Women Give Birth Before Hospitals? — 4,400
23. Why Does Time Feel Faster as You Age? — 25,000
24. How Did Ancient Humans Survive Predators? — 292,804 (`AvF3bPcqZeM`)
25. How Did Ancient Humans Survive Endless Rain? — 324,503

**Stickly (38.3K subs, ~22 min):**
26. What Did Ancient Humans Do Without Jobs — 95,619 (`cCxzQ_Vv3Dc`)
27. Were Ancient Humans Homosexual as Well? — 622
28. Why Couldn't Most Ancient Humans Drink Milk? — 8,600
29. Which Ancient Technologies Have We Lost? — 15,000
30. Why Were Animals Terrified of Ancient Humans? — 27,000
31. Why Don't Orcas Hunt Humans? — 21,000
32. At What Age Did Most Ancient Humans Die? — 26,000
33. When Did Early Humans Start Eating Salt? — 32,000
34. Why Do Falling Dreams Feel Real? — 12,000

**Ink Explainer (38.6K subs, ~8.7 min):**
35. What Did Ancient Humans Do When It Rained All Week? — 1,040,759
36. Why Are We the Only Human Species Left? What happened to others... — 864,000
37. When Did Ancient Humans Start Drinking Alcohol? — 765,000
38. How Did Ancient Humans Travel the World? — 638,000
39. The Real Reason Humans Started Wearing Clothes — 319,000
40. When Did Ancient Humans Started Smoking Weed? — 246,000
41. The Disturbing Ways Ancient Humans Survived Winter — 110,000

**Before Civilization (10.3K subs, ~29 min):**
42. Why Ancient Humans Couldn't Afford to Lose Their Grandparents — 37,000
43. How Did Ancient Humans Sleep Through Endless Rain? — 51,000
44. What Happened After Ancient Humans Killed a Mammoth? — 30,000
45. The Terrifying Sound Every Ancient Human Recognized — 19,000
46. What Did Ancient Humans Do With People Who Heard Voices? — 5,347

**ThenFolk (the failure case, ~8.5 min):**
47. How Did Ancient Humans Make the Wild Obey Them? — 60 (`KO_035Jkc2E`)
48. Why Were Ancient Humans Healthier Than Us? — 132
49. How Did Ancient Humans Escape the Deadliest Predators? — 91
50. When Did Ancient Humans Start Using Cannabis? — 1,100

**Oddlyhuman:**
51. DARKEST things ancient humans did to Survive the cold — 571,000
52. What Did Humans Do Before Jobs Existed? — 4,100
53. How Did Ancient Humans Actually Discover Fire? — 4,900

> **Note on ThenFolk `KO_035Jkc2E`:** prior work recorded this at **4 views**. It is now at **60 views** — it was published **2026-07-29, three days before this report**. It is a *fresh upload on a tiny channel*, not a demonstrated flop. The correct lesson is not "this title failed" but **"a perfect title on a channel with no authority gets ~100 views."** ThenFolk's whole catalogue sits at 48–1,100 views with textbook-correct titles. [SOURCED: `youtube_video_details`, `yt-dlp`]

---

## Thumbnail grammar

Inspected directly at 1280×720 via the Read tool. Files in scratch (not copied into repo).

### Observed rules — Axen

| Element | Rule |
|---|---|
| **Text** | **2–3 words, ~11–14 characters.** Never the title. A *compressed second hook*. |
| Examples | `FREE ALL DAY` (3.05M) · `SURVIVED HOW?` (1.05M) · `COZY ALL DAY?` (636K) · `NO PRIVACY?` (255K) · `WEIRDEST EMPEROR?` (9.5K) |
| **Colour of text** | **Yellow** (#FFE800-ish) on dark scenes; **white** on bright scenes. Always a heavy black outline, 6–10px. |
| **Position** | Top strip, spanning full width, ~20% of frame height. Consistent across every video. |
| **Typeface** | Rounded heavy sans / hand-drawn bubble caps. ALL CAPS. |
| **Face** | **No human face. Round white stick-figure heads with 2-dot eyes + single-line mouth.** Emotion carried entirely by eyebrow + eye-size. Frightened = oversized white eyes with visible iris. |
| **Composition** | Left-to-right threat gradient: protagonist stick figure on the left, danger/subject on the right. Or a centred campfire group. |
| **Contrast** | Single high-saturation focal element (orange fire, black predator silhouette) against a desaturated environment. |
| **Style match** | **Yes — identical to the video.** Same line weight, same characters, same palette. The thumbnail is a frame-quality still from the same art pipeline, not a separate design asset. |
| **Aspect** | 16:9, 1280×720 delivered (maxresdefault present on all). |

### The winner/loser thumbnail contrast

- `FREE ALL DAY` (3.05M): bright blue sky, green savanna, orange fire, 4 stick figures **relaxing** — one lying down. The image sells *envy*, matching the title's modern-work anchor.
- `SURVIVED HOW?` (1.05M): near-black cave, blue cave-mouth, **pure black sabre-tooth silhouette**, terrified stick figure. Sells *threat*.
- `WEIRDEST EMPEROR?` (9,498 — worst video): purple room, Napoleon smirking at a desk. **No threat, no relatable stake, no danger gradient.** Visually competent, semantically empty.

**The rule this implies:** the thumbnail must encode **either envy or threat within 200ms**. Axen's flops are the ones whose thumbnails encode neither.

### Clone thumbnails

- **Mack `AvF3bPcqZeM`** (`CAVE LION?`, 292K): same yellow/black-outline caps, same 2-word text, but **materially higher art quality** — full fur shading, rendered rock formations, expressive lion face. Mack has invested in illustration above Axen's baseline.
- **ThenFolk `KO_035Jkc2E`** (`NO FORCE NEEDED?`, 60 views): correct yellow caps, correct 3-word length, clean vector-cartoon reindeer. **The execution is fine.** The failure is the *phrase* — "NO FORCE NEEDED?" names no threat and no envy. Compare "CAVE LION?" (concrete predator) or "FREE ALL DAY" (concrete envy). Also visibly **AI/vector-generated** rather than hand-drawn, breaking style continuity with the stick-figure convention.

### Reusable thumbnail spec

1. 1280×720, upload a real `maxresdefault`.
2. **2–3 words max**, ALL CAPS, top strip, full width.
3. Yellow on dark scenes / white on bright scenes; black outline ≥6px; add a soft drop shadow.
4. The words must name **a threat** ("CAVE LION?", "SURVIVED HOW?") **or an envy** ("FREE ALL DAY", "COZY ALL DAY?"). Never a neutral noun.
5. Stick figures with round white heads. Eyes do the acting — enlarge them for fear.
6. One saturated focal element (fire / silhouette) against a muted background.
7. Left = protagonist, right = threat.
8. Draw it in the *same* pipeline as the video. Style continuity is a load-bearing trust signal in this niche.

---

## Clone swarm landscape

`get_similar_channels` (level 3, async) returned **136 channels**. [SOURCED]

### Cohort structure

| Segment | Count | Share |
|---|--:|--:|
| Total similar channels | 136 | 100% |
| Founded in 2026 | 80 | **59%** |
| Founded **on/after 2026-04-27** (Axen's launch) | 63 | **46%** |

### Subscriber distribution

| Bucket | All 136 | Post-Axen cohort (n=63) |
|---|--:|--:|
| <100 subs | 61 (45%) | **41 (65%)** |
| 100–1K | 18 (13%) | 11 (17%) |
| 1K–10K | 27 (20%) | 6 (10%) |
| 10K–100K | 11 (8%) | 5 (8%) |
| 100K+ | 19 (14%) | **0 (0%)** |
| **Median subs** | **234** | **23** |

- **38%** of the post-Axen cohort has **<1,000 total views lifetime**.
- **24%** cleared 100K total views.
- Only **5** cleared 1M total views: Axen, Mack, Stickly, Before Civilization, В двух словах.

### Who is winning [SOURCED: `get_similar_channels`, `get_batch_channel_metrics_v2`]

| Channel | Joined | Subs | Views | Vids | Avg len | RPM | Monetized | $/video (est.) |
|---|---|--:|--:|--:|--:|--:|---|--:|
| Super Joy Animations | 2024-06-08 | 434,000 | 58,098,943 | 99 | 8:06 | $3.14 | yes | $1,843 |
| **Mack** | 2026-05-20 | 60,200 | 6,931,857 | 39 | 22:30 | **$6.73** | yes | **$1,095** |
| **Axen** | 2026-04-28 | 50,100 | 5,175,133 | 11 | 7:51 | $3.77 | **NO** | **$0 actual** |
| Ink Explainer | 2026-04-08 | 38,600 | 3,760,225 | 11 | 8:17 | $3.55 | yes | $1,272 |
| Stickly | 2026-05-25 | 38,300 | 4,154,818 | 33 | 21:59 | **$6.79** | yes | $757 |
| The Thought Vortex | 2025-06-18 | 26,400 | 3,527,481 | 30 | 8:53 | $4.17 | yes | $461 |
| Before Civilization | 2026-04-28 | 10,300 | 1,178,566 | 56 | 24:00 | **$6.93** | yes | $145 |
| Banana Explains | 2026-06-07 | 3,820 | 934,068 | 25 | 22:11 | — | — | — |
| Oddlyhuman | 2026-06-11 | 2,870 | 517,282 | 8 | 7:19 | $2.98 | yes | $194 |
| History Alive Animated | — | — | — | — | 14:30 | $3.79 | yes | $53 |
| ThenFolk | — | — | — | ~15 | 8:30 | $2.79 | yes | **$25** |

*$/video = avgViewsPerVideo × RPM ÷ 1000. [ESTIMATE: AdSense only; excludes sponsorship/products.]*

### Who is dying

The long tail is stark. Representative post-Axen entrants: **Life Then** (3 subs, 29 views, 7 videos), **Ancient World** (0 subs, 44 views, 10 videos), **Floki** (7 subs, 112 views), **Bao's Sketchbook** (4 subs, 295 views, 17 videos), **Primal Sketch** (7 subs, 1,772 views), **Modern Habit Origins** (4 subs, 176 views), **Nexora** (6 subs, 769 views), **Life Before Civilization** (16 subs, 1,099 views).

**These channels are not failing on packaging.** ThenFolk's titles are textbook-perfect and its thumbnails are competent. They are failing on **distribution**: YouTube will not seed a new channel into the same browse surface that is already saturated by 10 incumbents with the same title.

### What separates winners from the dead

1. **Length.** Every post-Axen channel above 100K total views except Ink Explainer and Oddlyhuman runs **20+ minutes**. In the 2026 cohort with ≥5 videos: ≥12 min channels have **median 1,907 views/video** and **median 78,118 total views**; <12 min channels have **median 255 views/video** and **median 3,265 total views**. That is **7.5x views-per-video and 24x total views**. [SOURCED: computed from `get_similar_channels`]
2. **Volume.** Mack 39 videos, Stickly 33, Before Civilization 56 — vs Axen's 11. The winners kept shipping.
3. **Multi-channel operation.** See below.
4. **Off-platform monetization.** See *Niche economics*.

### The operator networks (important)

`youtube_search` surfaced results credited to **"Mack and 2 more"**, **"Trenn and 3 more"**, **"Mogo and 3 more"**, **"His Story 404 and 3 more"** — YouTube's grouping label for *the same video published across multiple channels*. All of these descriptions contain the **identical Teachable URL**: `ancient-minds-academy1.teachable.com/p/the-secret-lives-of-ancient-humans`. [SOURCED: `youtube_search`, `youtube_video_details` on `AvF3bPcqZeM`]

**Conclusion [ESTIMATE, high confidence]:** Mack, Trenn, Mogo and His Story 404 are **one operator running a coordinated multi-channel network** funnelling to a single paid course. "Before Civilization and Ancestor Mode" is a second such group. The "clone swarm" is therefore not 136 independent solo builders — a meaningful share is **a handful of operators running channel portfolios**, which is a much harder competitor than it appears.

### Comment-section farming

On `wt_7Hp7d7I8` (636K), **14 of the top 20 comments** are posted by other channels in the niche — @ThenFolk, @PrimalJournalYT, @WhenHumansWereWild-n4i, @TheBiblicalCaseFiles, @Brainveks, @Primalpsyche-s3c, @The5-MinuteMentorbyJack, @AlextheExplainerYT, @EvolutionInInk, @NewtExplains, @scientification-pr, @Myelox.offical, @TheHumanAuditt, @PrehistoricIntelligence. On `TQd2k1pEXp4`, 4 of 20 (@BeforeCivilization-01, @BeforeUsTribe, @InklyExplains7, @LifeasHumansoff). [SOURCED: `youtube_video_comments`]

**70% clone-comment density on a mid-tier video is a severe saturation indicator** — it means the marginal cost of attention in this niche has already been bid up to "manually spam competitors' comment sections."

---

## Niche economics & saturation

### RPM [SOURCED: `get_video_rpm`, `get_batch_channel_metrics_v2`]

- **Cohort median RPM: $3.78** (n=10)
- **Range: $2.79 – $6.93**
- Axen top video: **$2.29** (min $0.88, max $3.70)

Against NexLev's own scale ($2–5 = low, $5–10 = average, $10–20 = high), **this niche is LOW-value.** Reasons [ESTIMATE]: Education/History category, young-skewing audience, and heavy non-US traffic — NexLev's `countryTop` shows **Pakistan** for Super Joy and History Alive, **India** for Oddlyhuman.

### RPM is a function of length

| Segment | n | Median RPM |
|---|--:|--:|
| ≥20 min | 3 | **$6.79** |
| <10 min | 6 | $3.34 |
| **Premium** | | **2.0x** |

Long-form wins twice: **2.0x RPM × 7.5x views-per-video**. Combined, the long-form format is worth roughly **15x** the short-form format per video shipped. [ESTIMATE, compounding two SOURCED medians]

### Search saturation [SOURCED: `youtube_search`, query "what did ancient humans do", `upload_date=month`]

- **420,838 estimated total results**
- Of the 20 top results published in the **last 30 days**:
  - Median views: **3,494**
  - Mean: 73,556 (dragged entirely by two outliers)
  - **≥100K: 2 (10%)**
  - **<1,000: 6 (30%)**
  - **<100: 5 (25%)** — including a 4-view and a 3-view result *ranking on page 1*
  - Median duration: **20.3 min**; **70% are ≥15 min**

Direct title collision is now routine: *"What Did Ancient Humans Do When It Rained All Week?"* exists on **Ink Explainer (1,040,759)**, **Deep Epoch (44,094)** and **TrollTracks (3)** simultaneously.

**The clearest single data point on saturation:** Axen published *"What Did Ancient Humans Do all Day Before Jobs Existed?"* on 2026-05-04 → **3,052,090 views**. Stickly published *"What Did Ancient Humans Do Without Jobs"* on 2026-06-03, 30 days later → **95,619 views**. Oddlyhuman published *"What Did Humans Do Before Jobs Existed?"* → **4,100 views**. Same idea, decaying by roughly an order of magnitude per entrant. [SOURCED]

### Revenue reality check

| Channel | Views | RPM | AdSense (est.) | Other revenue |
|---|--:|--:|--:|---|
| Axen | 5,175,133 | $3.77 | **$0 — not monetized** | none observed |
| Mack | 6,931,857 | $6.73 | ~$46,600 | **Teachable course** (10 modules, 3.5h) |
| Stickly | 4,154,818 | $6.79 | ~$28,200 | none observed |
| Ink Explainer | 3,760,225 | $3.55 | ~$13,300 | none observed |

[ESTIMATE: views × RPM ÷ 1000. AdSense only. Real payouts vary with geography mix and ad fill.]

**The headline economic fact:** the single most viral channel in this niche (Axen, 5.18M views) has monetized **$0**, while the #2 channel by views (Mack) built a **paid course** and a **4-channel network**. The AdSense-only path in this niche is not the winning path.

---

## Audience signal from comments

`TQd2k1pEXp4` has **6,400 comments**; `wt_7Hp7d7I8` has 688. Top comments by likes: [SOURCED: `youtube_video_comments`, sort=top]

### What viewers actually respond to

| Likes | Comment |
|--:|---|
| 21,000 | *"What did people do before jobs were a thing?" / "They lived."* |
| 15,000 | *"So we had 290,000 years of freedom and somehow invented Monday meetings."* |
| 14,000 | *"Boy we really f\*cked it up"* |
| 6,700 | *"As someone who has tried no work, 20h work and 40h of work. Both not working and working too much made me depressed, but 20h just felt perfect"* |
| 6,000 | *"so that's why a 20 hour work week actually feels manageable compared to some 40 hour long bs😭"* |
| 5,700 | *"So I'm hardwired to want to just chill and do nothing. It all makes sense"* |
| 5,200 | *"Remember, not only did they create the pictures, they also had to gather the materials to make paint and implements."* |
| 4,800 | *"Crazy to think 'work' used to mean surviving the day, not sitting in meetings for 8 hours."* |
| 4,600 | *"'Existing without needing to justify your existence through productivity' hits hard 😮‍💨"* |
| 2,300 | *"So, that's why culture is dying in places where all we do is work."* |
| 2,100 | *"'they woke up and they were already enough' damn"* |
| 1,900 | *"7:27 uncensored jumpscare"* |

On the winters video:
| 1,000 | *"Why is it so hard for people to believe that ancient people were so intelligent??? That's absurd!"* |
| 681 | *"1:20 '…We don't have a fat layer like a seal…' Oh dude you haven't been in Walmart lately."* |
| 542 | *"As someone who's been homeless in the north east in the winter, you don't know how creative you are until it's your only option… Happy to report I'm typing this from my couch in my home ❤"* |
| 344 | *"They beat winter so completely that we forgot it was ever a war. Now we call it a bad commute."* |

### What this tells you about "quality" here

1. **Nobody is praising the animation.** Zero top comments mention the art, voice, or production. The stick-figure style is *sufficient*, not a differentiator. **Do not over-invest in animation quality.**
2. **The top comments quote the script.** Four of the top twelve are **verbatim narration lines** ("they woke up and they were already enough", "existing without needing to justify your existence through productivity"). **The script's aphorisms are the product.** Budget should go into writing, not rendering.
3. **The emotional payload is modern-life grievance, not historical curiosity.** Work, burnout, alarm clocks, meetings, productivity guilt. History is the *permission structure* to talk about it.
4. **Viewers self-insert.** The highest-value comments are personal ("I've tried 20h/40h weeks", "I've been homeless in winter"). Scripts that leave a gap for the viewer's own story generate the comment volume that drives the algorithm.
5. **Timestamped moments matter.** *"7:27 uncensored jumpscare"* at 1,900 likes — a single surprising beat generated a top-20 comment. Plant 1–2 discrete shock/humour beats per video.
6. **The one recurring complaint is credibility** — *"Why is it so hard for people to believe that ancient people were so intelligent???"* (1,000 likes) and the general "ancient aliens" derailment. Axen counters this with **full academic source lists in the description** (Sahlins 1972, Henshilwood 2004, Ekirch 2001, Conard 2009). Copy this — it is cheap and it defuses the main objection.

---

## Risks and contrarian case

### 1. Axen is not a success story you can safely copy [HIGH]
5.18M views, **$0 monetized**, 36 days dormant. If the goal is revenue, Axen is a *cautionary* benchmark. Whatever caused non-monetization — reused content policy, ineligibility, abandonment — is a live risk for anyone replicating the format. [SOURCED: `check_channel_monetization`]

### 2. The short-form format Axen used is the worse of the two available [HIGH]
7.5x views-per-video and 2.0x RPM both favour 20+ min. Axen's 8-minute format is what the *dying* half of the cohort uses. Copying Axen's length is copying the losing variable.

### 3. Timing — the window opened ~2026-04 and is closing [HIGH]
Axen's video #1 got 1.05M cold. Today, an equally well-packaged video on a new channel (ThenFolk) gets **60–1,100**. 46% of the swarm launched after Axen; 65% of them are under 100 subs. The cold-start lottery Axen won is no longer being run. [SOURCED]

### 4. Low RPM ceiling [MEDIUM-HIGH]
$2.79–$6.93. Even at Mack's scale (6.9M views) AdSense is ~$46K. To reach meaningful income on AdSense alone you need Super Joy volume (58M views, 99 videos, 2 years).

### 5. Competitors are portfolios, not people [MEDIUM-HIGH]
The Teachable-link evidence shows single operators running 3–4 channels. A solo builder shipping one channel is competing against operators shipping 4x the surface area into the same recommendation pool.

### 6. Comment-spam arms race [MEDIUM]
70% clone-comment density on a mid-tier video means the cheap growth tactics are already exhausted.

### 7. Topic pool is depleting fast [MEDIUM]
Jobs, winter, predators, rain, privacy, sleep, alcohol, cannabis, clothes, shoes, salt, music, education, mating, birth, illness, boredom, mental illness, injury, grandparents, flooding, drought, humour, dirt-eating, bathrooms are **all already taken** by ≥1 channel in the corpus above.

### The contrarian *bull* case (stated fairly)

- **Ink Explainer** launched 2026-04-08 and is at 38.6K subs / 3.76M views on **11 videos at 8.7 min** — proving short-form can still work with strong topic selection, and it *is* monetized.
- **Mack** launched **2026-05-20 — after Axen** — and is now the largest 2026 channel in the niche (60.2K subs, 6.9M views, RPM $6.73) with a course business. Post-Axen entry is demonstrably still viable *at 22 minutes with 39 videos*.
- **24%** of the post-Axen cohort cleared 100K views. That is not a dead niche; it is a *competitive* one.
- Absolute demand remains enormous — 420K+ results and multiple 1M+ videos in the last 30 days.

**Net:** the niche is **entrant-hostile but not dead**. The 8-minute AdSense clone is dead. The 20–25 minute, high-volume, off-platform-monetized version is still being won *right now* by channels that started after the benchmark.

---

## Data quality notes and stale-data flags

1. **NexLev `youtube_channel_videos` publish dates are rounded to month buckets** and were wrong for every Axen video (e.g. it reported `TQd2k1pEXp4` as 2026-06-02; the true date from `youtube_video_details` and `yt-dlp` is **2026-05-04**). All dates in this report come from `youtube_video_details` / `yt-dlp`, not from the channel-videos endpoint.
2. **NexLev comment `publishDate` fields are also bucketed** (many show identical timestamps). Comment *text* and *like counts* are reliable; comment dates are not.
3. **Subscriber count disagreement:** `youtube_channel_about` = 50,100; `get_channel_analytics` = 49,900; `get_similar_channels` cache = 46,800 with viewCount 4,821,830. The similar-channels cache is the stalest. Live per-video sum = 5,175,133 views.
4. **`yt-dlp --flat-playlist` returned `view_count: 0` for all Stickly videos** — an extraction artifact, not real data. Stickly counts were re-pulled with `--print` per video and via `youtube_video_details`.
5. **Prior-work figures corrected:** Mack `AvF3bPcqZeM` was recorded as 274K → now **292,804**. ThenFolk `KO_035Jkc2E` was recorded as 4 views → now **60** (published 2026-07-29). Stickly `cCxzQ_Vv3Dc` 90K → **95,619**. `jy9P9I7QIN0` is **"History Alive Animated"**, not "HistoryAlive" — 187,551 views, 16:16.
6. **All RPM figures are model predictions**, not observed payouts. NexLev reports confidence 0.98–0.99 on the batch metrics.
7. **No tool errors were encountered.** `get_similar_channels_status` returned a 278KB payload exceeding the token limit and was parsed from the saved file with Python — data is complete, not truncated.

---

## Sources

**NexLev MCP tools used (all succeeded):**
- `channel_resolver` — @AxenCool → `UC_7R-sfi7bi8dkzmSlBdUVw`
- `youtube_channel_about` — subs, views, join date, keywords, country
- `youtube_channel_videos` (sort=popular) — 11-video list
- `get_channel_analytics` — days since start, avg length, categories
- `youtube_video_details` — `TQd2k1pEXp4`, `2RJggsjlj4A`, `AvF3bPcqZeM`, `jy9P9I7QIN0`, `KO_035Jkc2E` (exact dates, likes, descriptions, keywords)
- `check_channel_monetization` — Axen `isMonetized: false`
- `check_faceless_channel` — 98% faceless, format=animation
- `get_video_rpm` — `TQd2k1pEXp4` RPM $2.29
- `get_similar_channels` (level 3, async) + `get_similar_channels_status` — 136 channels
- `get_batch_channel_metrics_v2` + `get_batch_channel_metrics_status` — 10-channel RPM/monetization cohort
- `youtube_video_comments` (sort=top) — `TQd2k1pEXp4`, `wt_7Hp7d7I8`
- `youtube_search` — "what did ancient humans do", upload_date=month

**yt-dlp `/opt/homebrew/bin/yt-dlp`:**
- `-J --flat-playlist` on Axen, Mack, Stickly, Ink Explainer, Before Civilization, ThenFolk, Oddlyhuman `/videos`
- `-J` per-video for exact `upload_date`, `view_count`, `like_count`, `comment_count`, `duration`

**Thumbnails inspected visually** (1280×720 `maxresdefault`, downloaded to scratch, not copied into repo):
`TQd2k1pEXp4`, `2RJggsjlj4A`, `wt_7Hp7d7I8`, `lJVPvTGUftQ`, `UFAPaRxXEAo`, `AvF3bPcqZeM`, `KO_035Jkc2E`

**URLs:**
- https://www.youtube.com/@AxenCool
- https://www.youtube.com/channel/UCaS30yIIV6y2zqSnHGdIGMQ (Mack)
- https://www.youtube.com/channel/UC53wkzZ3aXyeH9-eIgi17WA (Stickly)
- https://www.youtube.com/channel/UCpgrEMx8diLrw7YNQ6r3uUw (Ink Explainer)
- https://www.youtube.com/channel/UCeaEMim_qdHozbxH3i7CiyQ (Before Civilization)
- https://www.youtube.com/channel/UC23fUunZglY8lVoQc-Kkfpw (ThenFolk)
- https://www.youtube.com/channel/UC5kZmgakSTK1hmkFQUmwq8g (Super Joy Animations)
- https://ancient-minds-academy1.teachable.com/p/the-secret-lives-of-ancient-humans (Mack network course)
