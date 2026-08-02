# Script Craft Teardown — Faceless "Ancient Humans / Existential History" Explainers

**Date:** 2026-08-01
**Purpose:** Reverse-engineer the *writing* of successful faceless long-form explainers into a compilable
script specification + automatable grading rubric.
**Primary benchmark:** **Mack** (`@MackExplains`) — 68.1K subs, 6.9M views, 39 videos at ~22 min, launched
2026-05-20. Axen is treated as a secondary reference (see §1.2).

---

## 1. Method & Corpus

### 1.1 How transcripts were obtained

All transcripts pulled with `yt-dlp --write-auto-sub --sub-format vtt --skip-download`.
**Every transcript in this corpus is YouTube ASR (auto-generated).** `youtube_video_details` reports
`hasCaption: false` for every video sampled — no creator-authored captions exist anywhere in this niche.
This materially affects sentence-level metrics (§11).

VTT parsing (`parse_vtt.py`): YouTube's rollup format repeats the previous line in each cue and marks new
words with inline `<HH:MM:SS.mmm><c>word</c>` tags. Harvesting only tagged lines yields a **deduplicated
word stream with per-word timestamps**, which is what makes pacing and time-to-question measurable.

### 1.2 Corpus design and two corrections to the original brief

**Correction 1 — the "4-view failure case" is not a failure case.** `KO_035Jkc2E` (ThenFolk) was published
**2026-07-29, three days before this analysis**, and had 60 views at pull time on a 2.03K-sub channel.
**You cannot infer script quality from the view count of a 3-day-old video on a low-authority channel.**
I originally built a failure diff on it; that was survivorship reasoning running backwards and has been
removed. What that video supports is discussed, carefully bounded, in §10.3.

**Correction 2 — Axen is a weak benchmark.** Axen has 11 videos, has been dormant ~36 days, is not
monetized, and its 3.05M hero is a ~60× outlier against its own channel median (26K). A single viral hit on a
stalled channel is a poor model. **Mack is the stronger benchmark** and analysis is weighted accordingly.

**The replacement failure analysis uses a same-age cohort within Mack.** Mack's absolute view counts are
confounded by channel growth — every Mack video ≥60 days old is *above* the channel median, simply because
it has had longer to accumulate and was published when the channel was hotter. So an absolute
"≥60 days old and below median" filter returns nothing on this channel. Instead I compare **videos published
within the same ~4-week window**, which holds accumulation time and channel authority constant. That
cohort spans **996K down to 24K — a 41× spread with age controlled.** This is a cleaner design than an
absolute age cutoff.

| ID | Channel | Views | Age at pull | Dur | Words | Label |
|---|---|---|---|---|---|---|
| `C27Dd23jZzA` | **Mack** | 1,600,000 | 2 mo | 21:54 | 3187 | WIN |
| `th-0rmRYBSg` | **Mack** | 996,000 | 1 mo | 22:20 | 3253 | WIN (cohort top) |
| `Qgz_k2JQ3UY` | **Mack** | 316,000 | 2 mo | 22:53 | 3538 | WIN |
| `AvF3bPcqZeM` | **Mack** | 292,804 | 1 mo | 21:49 | 3473 | WIN |
| `bft1YyeSY_w` | **Mack** | 31,000 | 1 mo | 26:04 | 3776 | **UNDER (same cohort)** |
| `6mAx4_V1Rdk` | **Mack** | 24,000 | 4 wk | 24:08 | 3489 | **UNDER (same cohort)** |
| `TQd2k1pEXp4` | Axen | 3,052,090 | 2 mo | 8:32 | 1565 | WIN (outlier) |
| `2RJggsjlj4A` | Axen | 1,000,000 | 3 mo | 7:33 | 1438 | WIN |
| `wt_7Hp7d7I8` | Axen | 635,000 | 2 mo | 10:24 | 2231 | WIN |
| `q_Rqvd1ayUE` | Axen | 11,000 | 1 mo | 7:00 | 1356 | UNDER |
| `UFAPaRxXEAo` | Axen | 9,400 | 2 mo | 5:42 | 1070 | **UNDER (≥60 days)** |
| `x0fbZKMFBkA` | ThenFolk | 144,000 | 2 mo | 9:11 | 1557 | WIN |
| `3i8_L2JnE5M` | ThenFolk | 138,000 | 1 mo | 8:28 | 1523 | WIN |
| `KO_035Jkc2E` | ThenFolk | 60 | **3 days** | 8:27 | 1525 | *excluded from conclusions* |
| `cCxzQ_Vv3Dc` | Stickly | 90,000 | — | 24:52 | 3602 | WIN |
| `jy9P9I7QIN0` | HistoryAlive | 187,000 | — | 16:15 | 2505 | WIN |

**16 videos, 6 channels.** Mack cohort median (n=30 videos) = 130,000 views.

### 1.3 How every metric was computed

- **WPM** = words ÷ (duration_seconds/60), from the deduplicated timed stream.
- **Sentences** split on `(?<=[.!?])\s+`. **ASR-inferred punctuation** (§11).
- **Readability** — Flesch–Kincaid grade and Flesch Reading Ease implemented from first principles in
  `metrics.py` (`0.39·(W/S) + 11.8·(Sy/W) − 15.59`; `206.835 − 1.015·(W/S) − 84.6·(Sy/W)`), vowel-group
  syllable heuristic with silent-`e` correction. `textstat` was deliberately dropped so the formula is auditable.
- **Retention devices** — case-insensitive word-boundary regex families, normalised **per 1,000 words**.
  Patterns in `metrics.py::DEV`. Lexical proxies, not semantic parses.
- **Time-to-first-question** — timestamp of the first sentence ending in `?` **after stripping trailing
  quotes/brackets**. This correction matters: Mack's 1.6M video embeds its hook question inside quoted
  dialogue ending `?"`, which a naive detector reads as 313s instead of the true **23s**. Any rubric
  implementation must strip `"”’')]}` before testing.
- **Second-person decay** — 2p rate per 1,000 words in the first 90s vs everything after 90s, plus their ratio.
- **Named entities** — capitalised tokens in non-sentence-initial position minus a function-word stoplist.
  Over-counts place names, under-counts ASR-lowercased proper nouns.
- **Passive voice** — `be-verb + (adverb)? + -ed/-en`. Over-counts adjectival participles.

Scripts: `parse_vtt.py`, `metrics.py`, `qfix.py`. No repo file was modified except this document.

---

## 2. Verbatim Opening Teardowns

Short excerpts quoted for structural analysis only. **These are diagnostic references. Never reuse
competitor phrasing, or lightly reworded versions of it, in a produced video.**

### 2.1 Mack `C27Dd23jZzA` — 1.6M (primary benchmark hero)

> "You're standing around a fire. It's 50,000 BC. The sun just went down. There's no Netflix. There's no
> phone. There's no existential dread about your inbox."

**Dissection.** Second person, present tense, and then the defining Mack move: **anachronistic comedy**.
Three parallel "There's no X" clauses escalate from period-appropriate (Netflix, phone) to a modern
psychological joke (inbox dread). The register is wry, not solemn — this is the single biggest stylistic
difference from Axen. The hook question arrives at **0:23** inside quoted ancestral dialogue — roughly
*"what if I did that on purpose?"* — which is a neat trick: the question is dramatised as a character's
thought rather than narrated at the viewer. 8 second-person pronouns in the first 30s.

### 2.2 Mack `th-0rmRYBSg` — 996K (cohort top)

> "Look at your hand right now. Whatever shade it is… that color didn't come from nowhere."

Imperative aimed at the viewer's own body. Question at **0:16**. Then three parallel negations
("It wasn't random. It wasn't an accident. It wasn't some cosmic roll of the dice") — the same
triple-parallel rhythm as 2.1, used to build to a reveal.

### 2.3 Mack `Qgz_k2JQ3UY` — 316K

> "Imagine waking up tomorrow and your job is gone. Money doesn't exist. Your boss doesn't exist. The
> concept of a Monday doesn't exist."

Counterfactual imperative + escalating negation + workplace-jargon comedy ("circle back", "touch base").
Question at **0:13**.

### 2.4 Mack `bft1YyeSY_w` — 31,000 (UNDER, same cohort)

> "Imagine you're living 50,000 years ago. No courts, no judges, no lawyers billing you by the hour for
> services rendered in language you don't fully understand."

**The opening is competent** — same imperative, same negation stack, same anachronistic comedy. But note the
sentence is already 26 words and grammatically nested. The first question does not arrive until **1:01**.
This is where the divergence begins, and it is a *prose* divergence, not a concept divergence.

### 2.5 Mack `6mAx4_V1Rdk` — 24,000 (UNDER, same cohort — the clearest writing failure in the corpus)

> "Sleep is biologically speaking, the single most dangerous thing a human being does on a regular basis.
> Not skydiving, not driving, sleep."

**Third person. Abstract subject noun ("Sleep"). No "you" until the third sentence.** It opens on a
*proposition* rather than a *scene*. First question arrives at **6:51**. Mean sentence length across the
script is **28.4 words** with **only 2.4% of sentences under 8 words** and **51.2% over 25 words** — see §10.

### 2.6 Axen `TQd2k1pEXp4` — 3.05M

> "You wake up when your body is ready. No alarm, no schedule, no place you need to be."

8-word opening sentence, second person, present tense, bodily sensation. Solemn register (contrast Mack).
Stakes conversion at 0:20 turns prehistory into a number about the viewer's life ("90,000 hours…
1/3 of your waking existence"). Central question at 0:33.

### 2.7 Axen `UFAPaRxXEAo` — 9,400 (UNDER, ≥60 days old)

> "Napoleon Bonaparte conquered most of Europe by age 35. He crowned himself emperor."

**Third person. Past tense. A proper noun as the first word.** 1 second-person pronoun in the first 30s vs
7–13 in the winners, and only **one question mark in the entire 1,070-word script**. Same channel, same
voice, same animation as the 3.05M hero — the writing is the variable.

### 2.8 Other channels (secondary)

- **ThenFolk 144K** — *"You're standing in an open field, nothing in your hands, no claws, no fangs, no armor,
  just skin."* Question at 0:27.
- **Stickly 90K** — *"You wake up. Eight hours staring at a screen. Come home. Eat. Sleep. Repeat."*
  Seven sentences under 4 words.
- **HistoryAlive 187K** — *"Look around the room you're in right now."* Slowest to its question (1:13) and
  also the lowest-WPM winner (154).

**Pattern: 14 of 16 openings are second-person and present tense.** The two that are not — Axen's 9.4K and
Mack's 24K — are both underperformers in their own channel's same-period cohort.

---

## 3. Structural Maps

### 3.1 Mack `C27Dd23jZzA` (1.6M) — the 22-minute reference skeleton

| Time | % | Beat | Words |
|---|---|---|---|
| 0:00–0:25 | 2% | **Cold open** — 2p present-tense scene + anachronistic comedy | ~75 |
| 0:25–0:40 | 1% | **Hook question**, dramatised as ancestral dialogue | ~40 |
| 0:40–1:30 | 4% | **Promise / scope** — what the video will resolve | ~120 |
| 1:30–5:00 | 16% | **Evidence block 1** — origin + earliest physical evidence | ~510 |
| 5:00–9:00 | 18% | **Evidence block 2** — mechanism / "how it actually worked" | ~580 |
| 9:00–13:00 | 18% | **Evidence block 3** — cultural spread, named cultures | ~580 |
| 13:00–17:00 | 18% | **Evidence block 4** — complication / counter-evidence | ~580 |
| 17:00–20:00 | 14% | **Evidence block 5** — the modern collision | ~430 |
| 20:00–21:20 | 6% | **The Turn** — reframe of everything prior | ~200 |
| 21:20–21:54 | 3% | **Existential payoff** — 2p reframe, "next time you…" | ~170 |

**The recurring skeleton across all winners, both lengths:**
`COLD OPEN (2p scene) → HOOK QUESTION (≤45s) → PROMISE → N × EVIDENCE BLOCKS →
THE TURN (reversal) → EXISTENTIAL PAYOFF (2p reframe)`

**Scaling rule confirmed empirically:** the 8-minute Axen videos run **3 evidence blocks**; the 22-minute Mack
videos run **5–6**. The open, hook, turn and payoff stay almost constant in absolute seconds
(open ~20–25s, payoff ~35–90s) regardless of total runtime. **To lengthen a script, add evidence blocks —
never stretch the open, turn, or payoff.**

Each Mack evidence block internally re-runs a mini hook: sub-question → named evidence → concrete image →
mini-payoff → bridge sentence into the next block. That nested structure is what sustains 22 minutes.

### 3.2 Section transition counts

Winners run 5–11 explicit section transitions; Axen's two underperformers run 3–4.
Mack's `6mAx4_V1Rdk` (24K) is a continuous essay with almost no segmentation signalling.

---

## 4. Retention-Device Rate Table (per 1,000 words)

| ID | Label | 2nd person | 2p immersion | Rhet. Q | Fwd ref | Contradiction | Cliffhanger | Numbers | Authority | Named ent. |
|---|---|---|---|---|---|---|---|---|---|---|
| `C27Dd23jZzA` | **Mack WIN 1.6M** | 11.9 | 0.6 | 0.9 | 0.0 | 12.6 | 3.8 | 12.2 | 7.5 | 30.4 |
| `th-0rmRYBSg` | **Mack WIN 996K** | 12.6 | 0.6 | 2.5 | 0.6 | 15.1 | 2.5 | 14.8 | 1.8 | 33.2 |
| `Qgz_k2JQ3UY` | **Mack WIN 316K** | 15.0 | 0.6 | 1.4 | 0.3 | 11.9 | 4.8 | 16.7 | 4.0 | 15.5 |
| `AvF3bPcqZeM` | **Mack WIN 293K** | 18.7 | 2.6 | 1.4 | 0.3 | 14.4 | 2.3 | 11.5 | 1.4 | 6.3 |
| `bft1YyeSY_w` | **Mack UNDER 31K** | 12.2 | 0.5 | 0.3 | 0.3 | 8.2 | 2.4 | 8.5 | 2.1 | 14.6 |
| `6mAx4_V1Rdk` | **Mack UNDER 24K** | **3.7** | 0.0 | 0.6 | 0.0 | 9.5 | **0.3** | **2.6** | 5.2 | 4.3 |
| `TQd2k1pEXp4` | Axen WIN 3.05M | 26.8 | 2.6 | 2.6 | 0.0 | 12.8 | 3.8 | 28.1 | 9.6 | 20.4 |
| `2RJggsjlj4A` | Axen WIN 1.0M | 19.5 | 2.1 | 2.1 | 0.0 | 16.0 | 5.6 | 36.9 | 3.5 | 22.3 |
| `wt_7Hp7d7I8` | Axen WIN 635K | 12.6 | 0.4 | 0.9 | 0.0 | 9.9 | 2.2 | 12.1 | 2.7 | 15.7 |
| `q_Rqvd1ayUE` | Axen UNDER 11K | 43.5 | 0.7 | 2.9 | 0.0 | 6.6 | 2.2 | 24.3 | 1.5 | 14.7 |
| `UFAPaRxXEAo` | Axen UNDER 9.4K | 8.4 | 0.0 | **0.0** | 0.0 | 22.4 | 3.7 | 15.0 | **0.0** | 28.0 |
| `x0fbZKMFBkA` | ThenFolk WIN 144K | 28.9 | 0.0 | 1.3 | 0.0 | 19.9 | 2.6 | 30.2 | 2.6 | 21.8 |
| `3i8_L2JnE5M` | ThenFolk WIN 138K | 15.1 | 0.0 | 0.7 | 0.7 | 12.5 | 6.6 | 20.4 | 3.9 | 10.5 |
| `cCxzQ_Vv3Dc` | Stickly WIN 90K | 18.6 | 0.8 | 3.9 | 0.0 | 14.2 | 3.1 | 13.9 | 0.6 | 10.3 |
| `jy9P9I7QIN0` | HistoryAlive WIN 187K | 20.4 | 0.4 | 2.0 | 0.8 | 13.6 | 4.8 | 23.6 | 10.0 | 27.9 |

### Findings

**Forward references are essentially absent (0.0–0.8/1k) across the entire genre.** The "but first… we'll
come back to this later" device that dominates generic YouTube scripting advice **does not appear here**.
Do not put it in the prompt. Momentum comes from unresolved narrative tension, not explicit promises.

**Second-person density is a band, not a maximise-me.** Winners span 11.9–28.9/1k. Axen's 11K underperformer
has the corpus *maximum* (43.5) — a philosophy monologue at "you" with almost no evidence (authority 1.5).
Too much "you" without evidence reads as a sermon. Mack's winners sit comfortably at 11.9–18.7.

**Numbers density separates the Mack cohort cleanly.** Mack winners 11.5–16.7/1k; Mack underperformers
8.5 and **2.6**. The 24K video is almost entirely unquantified prose.

**Authority density does *not* separate winners from underperformers.** Mack's 24K underperformer scores
5.2/1k — higher than three Mack winners. See §7, which qualifies the project's citation thesis.

### 4.1 Time-to-first-question (quote-stripped detector)

| ID | Label | First `?` | Q in first 45s |
|---|---|---|---|
| `TQd2k1pEXp4` | Axen WIN 3.05M | 0:06 | 2 |
| `Qgz_k2JQ3UY` | **Mack WIN 316K** | 0:13 | 1 |
| `th-0rmRYBSg` | **Mack WIN 996K** | 0:16 | 2 |
| `cCxzQ_Vv3Dc` | Stickly WIN 90K | 0:19 | 2 |
| `AvF3bPcqZeM` | **Mack WIN 293K** | 0:21 | 1 |
| `C27Dd23jZzA` | **Mack WIN 1.6M** | 0:23 | 1 |
| `2RJggsjlj4A` | Axen WIN 1.0M | 0:23 | 2 |
| `3i8_L2JnE5M` | ThenFolk WIN 138K | 0:23 | 1 |
| `x0fbZKMFBkA` | ThenFolk WIN 144K | 0:27 | 1 |
| `wt_7Hp7d7I8` | Axen WIN 635K | 0:36 | 2 |
| `jy9P9I7QIN0` | HistoryAlive WIN 187K | 1:13 | 0 |
| `bft1YyeSY_w` | **Mack UNDER 31K** | **1:01** | **0** |
| `6mAx4_V1Rdk` | **Mack UNDER 24K** | **6:51** | **0** |
| `UFAPaRxXEAo` | Axen UNDER 9.4K | 0:35 | 1 *(only 1 in whole script)* |

**Ten of eleven winners pose their first question within 36 seconds (median 23s). Both Mack same-age
underperformers pose zero questions in the first 45 seconds.** This is the strongest single discriminator
found, and it now replicates on the primary benchmark channel with age controlled.

---

## 5. Sentence-Craft Metrics

| ID | Label | WPM | Mean sent. | SD | % <8w | % >25w | FK grade | Read. ease | Abstract/1k | Passive/1k |
|---|---|---|---|---|---|---|---|---|---|---|
| `C27Dd23jZzA` | **Mack WIN 1.6M** | 146 | 16.3 | 13.8 | 32.7 | 21.4 | 10.7 | 46.8 | 22.6 | 5.3 |
| `th-0rmRYBSg` | **Mack WIN 996K** | 146 | 14.0 | 10.6 | 31.0 | 14.2 | 10.3 | 46.1 | 37.8 | 3.7 |
| `Qgz_k2JQ3UY` | **Mack WIN 316K** | 155 | 15.9 | 12.1 | 26.1 | 18.5 | 10.1 | 51.0 | 22.6 | 3.1 |
| `AvF3bPcqZeM` | **Mack WIN 293K** | 159 | 12.9 | 9.1 | 36.4 | 10.0 | 9.1 | 52.5 | 23.0 | 2.9 |
| `bft1YyeSY_w` | **Mack UNDER 31K** | 145 | **21.8** | 17.4 | **18.5** | **27.2** | **15.0** | **26.3** | **48.5** | 7.2 |
| `6mAx4_V1Rdk` | **Mack UNDER 24K** | 145 | **28.4** | 15.6 | **2.4** | **51.2** | **19.5** | **6.0** | **45.9** | 1.1 |
| `TQd2k1pEXp4` | Axen WIN 3.05M | 183 | 10.5 | 6.7 | 37.6 | 3.4 | 7.1 | 62.4 | 19.2 | 5.1 |
| `2RJggsjlj4A` | Axen WIN 1.0M | 190 | 9.8 | 5.4 | 43.8 | 1.4 | 5.4 | 73.3 | 11.8 | 1.4 |
| `wt_7Hp7d7I8` | Axen WIN 635K | 215 | 13.9 | 7.8 | 25.0 | 9.4 | 5.6 | 79.4 | 3.6 | 1.3 |
| `q_Rqvd1ayUE` | Axen UNDER 11K | 194 | 15.4 | 8.9 | 19.3 | 9.1 | 8.0 | 65.1 | 22.1 | 5.2 |
| `UFAPaRxXEAo` | Axen UNDER 9.4K | 188 | 9.3 | 5.8 | 49.6 | 1.7 | 6.1 | 67.9 | 17.8 | **9.3** |
| `x0fbZKMFBkA` | ThenFolk WIN 144K | 170 | 13.1 | 8.1 | 28.6 | 7.6 | 7.8 | 61.9 | 19.3 | 1.3 |
| `3i8_L2JnE5M` | ThenFolk WIN 138K | 180 | 13.4 | 10.5 | 35.1 | 10.5 | 5.8 | 77.3 | 7.2 | 0.7 |
| `cCxzQ_Vv3Dc` | Stickly WIN 90K | 145 | 14.2 | 12.3 | 36.2 | 15.4 | 9.6 | 51.6 | 32.5 | 5.8 |
| `jy9P9I7QIN0` | HistoryAlive WIN 187K | 154 | 13.6 | 8.4 | 26.1 | 8.7 | 9.0 | 54.4 | 20.8 | 5.2 |

**Long-form winner envelope (Mack/Stickly, ~22 min):** mean sentence **12.9–16.3**; SD **9.1–13.8**;
≥26% of sentences under 8 words; ≤22% over 25 words; FK grade **9.1–10.7**; reading ease **46–53**.

**Short-form winner envelope (Axen/ThenFolk, ~8 min):** mean sentence 9.8–13.9; FK 5.4–7.8;
reading ease 62–79; WPM 170–215. **Short-form is written measurably simpler and delivered faster.**

**Sentence-length variance is the craft signal, not mean length.** Every winner runs SD ≥ 5.4, most ≥ 9 —
long explanatory sentences alternating with 3–6 word hammer sentences. Uniform rhythm reads as machine output.

---

## 6. Pacing

**Words per minute is a function of runtime, not channel preference:**
- 8–10 min videos: **170–215 WPM**
- 16–25 min videos: **145–160 WPM**

**Important correction for generation:** Mack's four winners run **146, 146, 155, 159 WPM — mean ≈ 151.**
A 22-minute Mack-style script is therefore **≈3,200–3,550 words, not 4,000.** Generating 4,000 words at an
assumed 183 WPM would produce a script that either overruns to ~26 minutes at Mack's actual delivery pace,
or forces a 20% faster read that breaks the register. **Use ~150 WPM for 22-minute scripts.**
(Note both Mack underperformers are also ~145 WPM but *longer* — 26:04 and 24:08 — which is consistent with
padding rather than pacing.)

**Information density (words per 30s bucket, SD across buckets):** winners breathe (Axen hero 9.6,
Axen 1.0M 12.1, Stickly 8.9); underperformers are flat (Axen 9.4K 7.0, Axen 11K 6.5). Density peaks during
*narrative reconstruction* and troughs during *meaning-making* — fast prose for story, slow prose for payoff.
**A flat density curve is a machine-writing fingerprint.**

---

## 7. Citation & Authority Analysis — a correction to the project thesis

The project's stated differentiator is "real citations". **The data supports citations as a floor, not a lever.**

**What winners do — in-script named authority (Axen 3.05M hero, 1,565 words):** Richard Lee (1963, Dobe
Ju/'hoansi, 17 hrs/week); cross-validation across Hadza / Aché / Martu; Chauvet Cave (1994, ~30,000 yrs);
Blombos Cave shell beads (20 km coastline, 40 km round trip); a 40,000-year bone flute (2008, Germany, five
finger holes); James Suzman (~6 hrs/day social time); Polly Wiessner (2014, 81% of night conversations).
≈**2 named authorities per 1,000 words, each fused to a specific number.**

**But the counter-evidence is decisive:**
- Mack's **24K underperformer** has authority density **5.2/1k — higher than three Mack winners** — and
  still failed within its own cohort.
- Axen's **9.4K underperformer** has authority **0.0/1k** and no named researchers at all; its problem is
  clearly not citations.
- ThenFolk's 3-day-old video names Spottiswoode, Wood, Cantor, Bonta, Gosford, Losey and Anderson and cites
  *Science*, *PNAS* and *Journal of Ethnobiology* — the densest citation load in the corpus.

**Conclusion: citations buy defensibility, description-box credibility and protection from "AI slop"
accusations — all real and worth keeping. They do not drive retention or sharing.**

**The operative rule is not "cite more" but "never state a number without an owner."** The unit is
`[named person or place] + [date] + [specific number]`. The failure modes are (a) a vague "scientists believe"
in the script with the real citation buried in the description, and (b) a correctly-cited fact with no
narrative job.

**Anti-pattern found in the ThenFolk script:** it undercuts its own most striking claim in the same breath —
noting that intent is disputed, nobody filmed it, and some researchers read the behaviour as accidental —
*immediately after* delivering the claim. No winner does this. Winners handle uncertainty **before** the
payoff and convert it into a question the audience wants answered (Axen: *"some of you are thinking… Fair
question. And the answer comes from bones."*).

---

## 8. Endings — and a correction to the "no CTA" rule

Last ~30 seconds:

- **Mack 1.6M** — *"next time you flip a light switch or sit around a summer fire… you're participating in
  something far older than you realize."* A **second-person "next time you…" reframe**. No CTA.
- **Mack 996K** — closes on every skin tone being "an answer to a question asked by a star". No CTA.
- **Mack 316K** — *"Would you want to go back? Let me know in the comments… I'll see you soon."*
  **A full CTA + comment-bait question + signoff.**
- **Mack 293K** — *"the most dangerous thing to ever walk on this planet."* No CTA.
- **Axen 3.05M** — a you-vs-them ledger ending on what was traded away. No CTA.
- **Stickly 90K** — absolves the viewer: not lazy, not broken, merely "300,000 years old".
- **HistoryAlive 187K** — instructs the viewer's future self to remember next time they touch a thermostat.
- **Axen 9.4K (UNDER)** — *"he was also just a person, a very strange person."* A shrug. No reframe, no
  stakes, nothing quotable.

**Corrected finding: 12 of 13 winners end without a subscribe CTA — but one Mack winner (316K) ends with an
explicit comment-bait question and signoff.** So a CTA is **permitted but not required**, and Mack's two
biggest videos (1.6M, 996K) do *not* use one. My earlier "never CTA" formulation was over-fitted to Axen and
has been softened.

**What is universal is the second-person existential reframe.** Every winner's final beat re-describes the
*viewer's* life in light of what was learned. The "next time you [ordinary modern action]…" construction
appears in Mack 1.6M and HistoryAlive 187K and is the most portable version of it.

---

## 9. Audience Evidence — partially refutes the reported comment finding

I was asked to confirm or refute: *"comments never mention the art; four of ~40 top comments quote narration
verbatim; the recurring complaint is credibility/sourcing."*

**Pulled top-20 comments on Mack 1.6M (1.8K comments) and Axen 3.05M (6.4K comments).**

**CONFIRMED — nobody discusses the archaeology or the sources.** Across 40 top comments, not one mentions
Richard Lee, Wiessner, Chauvet, Blombos, or any cited researcher.

**CONFIRMED for Axen — verbatim narration quoting is real, and it is the highest-value engagement.**
Two of Axen's top 20 quote script text directly, at **4.6K** and **2.1K likes**; the single top comment
(**21K likes**) is a two-line compression of the video's thesis. Others: **15K** ("290,000 years of freedom
and somehow invented Monday meetings"), **14K** ("we really f\*cked it up"), **6.7K / 6K** viewers comparing
their own working week.

**REFUTED for Mack — Mack's top comments are jokes and personal identification, not narration quotes.**
Top-liked: **2.2K** ("Me watching this while smoking"), **1.5K** ("everyone's just hotboxing with the boys
through time"), **768** (a self-deprecating joke), **562 / 51 / 30 / 248** (viewers volunteering their *own*
causal theories and facts), plus repeated **timestamp callouts** (0:25, 2:35, 4:40, 5:20) marking moments
that landed.

**REFUTED — I found no credibility/sourcing complaint in either top-20 pull.** Zero occurrences. I cannot
confirm that claim from my data; if it came from a wider or differently-sorted sample it may still hold, but
it is not visible in top comments on the two biggest videos in the niche.

**What this actually means for the spec — engagement register is channel-dependent:**
- **Solemn/existential register (Axen, Stickly)** → viewers quote payoff lines verbatim. Optimise for
  quotable abstractions in the final beat.
- **Wry/comedic register (Mack)** → viewers self-identify and joke, volunteer their own theories, and cite
  timestamps. Optimise for **anachronistic comic beats** and for **leaving one genuinely open question** the
  audience can theorise about in the comments.

Since Mack is the benchmark, **the comedic-identification register should be the default**, with 2–4
quotable existential lines reserved for the payoff. The archaeology is the permission structure that makes
the payoff feel earned; it is not itself the product.

---

## 10. Underperformance Diff — Mack same-age cohort

This replaces the discarded ThenFolk analysis. All three videos below were published within ~4 weeks of each
other on the same channel, with the same narrator, animation, thumbnail language and subscriber base.

### 10.1 `6mAx4_V1Rdk` (24K) vs `th-0rmRYBSg` (996K) — 41× spread, age controlled

| Metric | 996K WIN | 24K UNDER | Δ |
|---|---|---|---|
| First question | **0:16** | **6:51** | **26× later** |
| Questions in first 45s | 2 | **0** | — |
| Opening person/tense | 2nd, present | **3rd, abstract proposition** | — |
| 2p density (whole) | 12.6/1k | **3.7/1k** | −71% |
| 2p density after 90s | 11.3/1k | **2.5/1k** | −78% |
| 2p retention ratio | 0.39 | **0.12** | — |
| Mean sentence length | 14.0 w | **28.4 w** | +103% |
| % sentences < 8 words | 31.0% | **2.4%** | −92% |
| % sentences > 25 words | 14.2% | **51.2%** | +260% |
| Flesch–Kincaid grade | 10.3 | **19.5** | postgraduate |
| Reading ease | 46.1 | **6.0** | near-unreadable |
| Numbers / 1k | 14.8 | **2.6** | −82% |
| Abstract nouns / 1k | 37.8 | 45.9 | +21% |
| Cliffhanger markers / 1k | 2.5 | **0.3** | −88% |
| Authority / 1k | 1.8 | 5.2 | **UNDER scores higher** |

### 10.2 `bft1YyeSY_w` (31K) — the same failure, less extreme

Mean sentence **21.8 w**, %<8w **18.5%**, %>25w **27.2%**, FK **15.0**, reading ease **26.3**,
abstract nouns **48.5/1k** (corpus maximum), passive **7.2/1k**, numbers **8.5/1k**, first question **1:01**.

**The two underperformers replicate the same pattern independently.** That replication is what makes this
diff trustworthy where a single video would not be.

### 10.3 The named writing failures

1. **The hook question is absent from the opening.** Both underperformers pose zero questions in the first
   45 seconds; every winner poses one within 36. Without a question there is no open loop and no reason to
   stay. (`6mAx4_V1Rdk`: 6:51 — 28% into a 24-minute video.)
2. **Sentence bloat.** Mean length roughly doubles (14 → 28 words) and short hammer sentences nearly vanish
   (31% → 2.4%). Narrated aloud, 28-word average sentences give the listener no cadence to lock onto.
3. **Reading level collapse.** FK 19.5 and reading ease 6.0 vs the winner envelope of 9–11 / 46–53.
   These scripts are written like academic prose and performed like documentaries.
4. **Loss of the second person.** 2p falls to 3.7/1k overall and **2.5/1k after the 90-second mark** —
   the viewer is invited in and then evicted. Winners hold ≥8/1k through the body.
5. **De-quantification.** Numbers fall to 2.6/1k. Abstractions rise to ~46–48/1k. The prose argues rather
   than shows.
6. **Padding, not pacing.** Both underperformers are *longer* (26:04, 24:08) than the winners (21:49–22:53)
   at the same WPM — more words, less signal.

**Note on §10.1's authority row:** the underperformer cites *more* than the winner. This is the third
independent confirmation that citation density does not predict performance (§7).

### 10.4 What the ThenFolk 3-day-old video can and cannot support

`KO_035Jkc2E` **is excluded from all performance conclusions** — 60 views at 72 hours on a 2.03K-sub channel
is uninformative, and its packaging is reportedly correct for the niche. Two observations are worth
recording as *hypotheses only*, because they are properties of the text rather than of the view count, and
because they match the Mack cohort findings:
- Its first question falls at **6:42 of 8:27** — the same defect measured in the Mack underperformers.
- Its 2p density collapses from 43.0/1k (first 90s) to **4.8/1k** thereafter (ratio 0.11).

These are flagged for the rubric because they replicate an effect *established elsewhere*, not because this
video's view count demonstrates anything.

---

## 11. Caveats

1. **All transcripts are ASR.** `hasCaption: false` everywhere. Modern YouTube ASR inserts punctuation, so
   sentence splitting is possible, but **sentence boundaries are model-inferred, not authored.** Therefore:
   - Mean/SD sentence length, % short, % long, and FK grade are **approximations**. Between-video comparison
     stays valid (same ASR system, same error class); absolute values must not be quoted as writer intent.
   - The §10 sentence-length findings are partly punctuation-dependent. However **2p density (3.7 vs 12.6),
     numbers density (2.6 vs 14.8) and time-to-first-question are punctuation-independent** and show the
     same direction — so the underperformance diagnosis does not rest on ASR punctuation alone.
   - ASR clips words mid-clause occasionally, slightly deflating word counts and WPM.
2. **n = 16 across 6 channels.** The strongest evidence is the Mack same-age cohort (4 winners, 2
   underperformers). Treat thresholds as **design targets, not statistical findings.**
3. **Views are not a clean outcome variable** even within a cohort — title, thumbnail, topic appetite and
   session context are unmeasured. Script quality is one input among several.
4. **Regex device counts are lexical proxies**, especially "cliffhanger" and "contradiction".
5. **The question-mark detector must strip trailing quotes.** Failing to do so misreads Mack's 1.6M video as
   313s-to-first-question instead of 23s — an error that would invert the single most important rule.
6. **Axen's 3.05M hero is a ~60× channel outlier** on a stalled, unmonetized channel; weight accordingly.
7. All quoted excerpts are short, used for analysis, and **must not be reused as script text.**

---

# 12. THE SCRIPT SPECIFICATION

## 12.A Primary target — 22-minute video (Mack format)

**≈3,300 words at ~150 WPM.** (Not 4,000 at 183 — see §6.)

| # | Beat | Timing | Words | Requirements |
|---|---|---|---|---|
| 1 | **Cold open** | 0:00–0:25 | **70–85** | 2nd person, present tense, concrete scene. First sentence ≤12 words. No branding, no "in this video". Include one **anachronistic comic beat** (modern object/annoyance transplanted into the ancient scene). ≥5 second-person pronouns. |
| 2 | **Hook question** | 0:25–0:45 | **35–50** | One sentence ending in `?`. May be dramatised as a character's quoted thought. **Hard deadline: 45 seconds.** |
| 3 | **Promise / scope** | 0:45–1:30 | **110–130** | State what will be resolved and why it matters to the viewer. One number tied to the viewer's own life. |
| 4 | **Evidence block 1** | 1:30–5:00 | **480–540** | Sub-question → named source + date + number → concrete physical image → mini-payoff → bridge sentence. |
| 5 | **Evidence block 2** | 5:00–9:00 | **550–610** | Mechanism: *how it actually worked*. Highest density of concrete nouns. |
| 6 | **Evidence block 3** | 9:00–13:00 | **550–610** | Cultural/geographic spread. Name at least 3 specific peoples, sites or places. |
| 7 | **Evidence block 4** | 13:00–17:00 | **550–610** | Complication or counter-evidence. Voice the viewer's skepticism, then answer it with a different evidence *type*. |
| 8 | **Evidence block 5** | 17:00–20:00 | **420–470** | The modern collision — where this reaches the viewer's present. |
| 9 | **The Turn** | 20:00–21:20 | **190–220** | Reversal that reframes everything prior. Sentence length drops sharply here. |
| 10 | **Existential payoff** | 21:20–22:00 | **150–180** | 2nd-person reframe, ideally "next time you [ordinary modern action]…". 2–4 quotable lines. Final sentence ≤25 words. CTA optional (§8). |

**Scaling:** for 25 min add one evidence block (~550 w); for 18 min drop one. **Never** stretch beats 1, 2, 9, 10.

## 12.B Secondary target — 10-minute video

**≈1,800 words at ~180 WPM.** Same skeleton with **3** evidence blocks.

| Beat | Timing | Words |
|---|---|---|
| Cold open | 0:00–0:20 | 60–75 |
| Hook question | 0:20–0:35 | 20–30 |
| Stakes conversion | 0:35–0:50 | 45–60 |
| Evidence block 1 | 0:50–2:40 | 320–350 |
| Objection handling | 2:40–3:05 | 70–90 |
| Evidence block 2 | 3:05–5:00 | 340–370 |
| Reconstruction (2p narrative) | 5:00–6:50 | 330–360 |
| Evidence block 3 | 6:50–8:00 | 200–230 |
| The Turn | 8:00–9:05 | 190–210 |
| Existential payoff | 9:05–10:00 | 160–190 |

Short-form is written **simpler and faster**: target FK 6–8 and 170–190 WPM (vs FK 9–11 and ~150 WPM long-form).

## 12.C Hard rules

**DO:**
1. Open in second person, present tense, inside a concrete scene.
2. Land the hook question — one sentence ending `?` — **within 45 seconds**.
3. Attach an owner to every number: `[named person or place] + [date] + [figure]`.
4. Hold second person through the body: **≥8 per 1,000 words after the 90-second mark**.
5. Vary sentence length hard: alternate 15–25 word explanatory sentences with 3–6 word hammers.
   Keep **≥25% of sentences under 8 words**.
6. Use anachronistic comedy — modern annoyances transplanted into ancient scenes (the Mack signature).
7. End on a second-person reframe of the viewer's life; "next time you…" is the most portable form.
8. Leave exactly one genuinely open question for the comments (drives Mack's theory-volunteering pattern).
9. Build one escalating argument — each evidence block must depend on the previous.

**NEVER:**
1. Never open in third person, in the past tense, or on an abstract noun. (Both underperformers do.)
2. Never write a script with fewer than 4 question marks.
3. Never delay the hook question past 45s.
4. Never let mean sentence length exceed ~17 words, or `>25-word` sentences exceed ~22%.
5. Never write above ~11th-grade reading level (long-form) or ~8th (short-form).
6. Never use "but first…", "we'll come back to this", "later in this video" — **absent from this entire
   genre (0.0–0.8/1k).**
7. Never undercut a striking claim with hedging in the same breath — handle uncertainty *before* the payoff.
8. Never say "scientists believe" / "researchers say" without a name.
9. Never let numbers density fall below ~10/1,000 words.
10. Never pad to length — the underperformers are *longer* than the winners at the same WPM.
11. Never write uniform paragraph sizes; flat density is the machine-writing fingerprint.

---

# 13. THE AUTOMATABLE RUBRIC

Computable from script text alone. `T(w) = w / WPM * 60` converts word offset → seconds
(**WPM = 150 long-form, 180 short-form**). **Pass ≥ 85; any CRITICAL failure blocks.**

| # | Check | Threshold | Sev | Pts |
|---|---|---|---|---|
| 1 | Time to first `?` **(strip trailing `"”’')]}` first)** | **≤ 45s** | **CRIT** | 14 |
| 2 | Question marks in whole script | **≥ 4** | **CRIT** | 5 |
| 3 | 2p pronouns in first 30s | **≥ 5** | **CRIT** | 9 |
| 4 | First sentence: 2nd person, present tense, ≤12 words | true | **CRIT** | 9 |
| 5 | First word is not a proper noun or abstract subject noun | true | HIGH | 3 |
| 6 | 2p density, whole script | **11–32 / 1k** | HIGH | 5 |
| 7 | **2p density after the 90s mark** | **≥ 8 / 1k** | **CRIT** | 9 |
| 8 | 2p retention ratio (post-90s ÷ first-90s) | **≥ 0.20** | HIGH | 4 |
| 9 | Mean sentence length | **≤ 17.0 w** (long) / **≤ 15.0** (short) | **CRIT** | 7 |
| 10 | % sentences < 8 words | **≥ 25%** | HIGH | 6 |
| 11 | % sentences > 25 words | **≤ 22%** | HIGH | 4 |
| 12 | Sentence-length SD | **≥ 6.0** | HIGH | 4 |
| 13 | Flesch–Kincaid grade | **8.5–11.5** (long) / **5.0–8.5** (short) | HIGH | 5 |
| 14 | Flesch Reading Ease | **≥ 44** | HIGH | 4 |
| 15 | Numbers/specifics | **≥ 10 / 1k** | HIGH | 5 |
| 16 | Named authorities (person/site + date) | **≥ 1.5 / 1k** | MED | 4 |
| 17 | Distinct named researchers/sites | **≥ 8** (22-min) / **≥ 5** (10-min) | MED | 3 |
| 18 | Bare "scientists/researchers say" with no name | **0** | HIGH | 3 |
| 19 | Abstract-suffix nouns | **≤ 40 / 1k** | MED | 3 |
| 20 | Passive constructions | **≤ 7 / 1k** | MED | 2 |
| 21 | Forward-reference phrases | **≤ 1 total** | MED | 2 |
| 22 | Density SD across 30s buckets | **≥ 7.0 words** | MED | 3 |
| 23 | Contradiction/reversal markers | **≥ 9 / 1k** | MED | 2 |
| 24 | Final 200 words contain ≥3 second-person pronouns | true | HIGH | 4 |
| 25 | Final sentence ≤ 25 words | true | LOW | 1 |
| 26 | Total words within ±8% of target (3,300 / 1,800) | true | MED | 3 |

**Validation against the corpus:**
- Mack 996K, Mack 1.6M, Mack 316K, Mack 293K, Axen 3.05M — pass all CRITICALs.
- **Mack 24K** fails #1 (6:51), #3, #4, #7 (2.5/1k), #9 (28.4w), #10 (2.4%), #11 (51.2%), #13 (19.5),
  #14 (6.0), #15 (2.6/1k) → **blocked**.
- **Mack 31K** fails #1 (1:01), #9 (21.8w), #10 (18.5%), #11 (27.2%), #13 (15.0), #14 (26.3), #15 (8.5/1k)
  → **blocked**.
- **Axen 9.4K** fails #2 (1 question), #3 (1 pronoun), #4, #7 (6.4/1k) → **blocked**.

**Regex anchors** (mirroring `metrics.py`):
```
2p          \b(you|your|you're|yours|yourself)\b
question    sentence.rstrip('"”’\')]} ').endswith('?')     # MUST strip quotes
named_auth  (?:archaeolog|anthropolog|research|professor|biolog|historian)\w*\s+[A-Z][a-z]+\s+[A-Z][a-z]+
            |[A-Z][a-z]+\s+(?:and\s+[A-Z][a-z]+\s+)?(?:published|documented|found|argued|analyzed)
vague_auth  \b(scientists|researchers|experts|historians)\s+(?:say|believe|think|agree)\b
fwd_ref     \b(but first|we'?ll come back|later in this video|more on that|coming up)\b
abstract    \w+(?:tion|sion|ness|ity|ism|ance|ence|ment|ship|hood)\b
passive     \b(is|are|was|were|been|being|be)\s+(?:\w+ly\s+)?\w+(?:ed|en)\b
```

---

# 14. Few-Shot Examples — Verbatim Winner Openings

**Structural calibration only. Do not reuse this text or lightly reworded versions in any produced video.
Instruct the model to match the *shape* — pronoun, tense, sentence length, question timing, comic register —
and invent entirely new content.**

1. **Mack, 1.6M** — *scene + escalating anachronistic negation; question at 0:23*
   > "You're standing around a fire. It's 50,000 BC. The sun just went down. There's no Netflix. There's no
   > phone. There's no existential dread about your inbox."

2. **Mack, 996K** — *imperative at the viewer's own body; question at 0:16*
   > "Look at your hand right now. Whatever shade it is… that color didn't come from nowhere."

3. **Mack, 316K** — *counterfactual imperative + workplace-jargon comedy; question at 0:13*
   > "Imagine waking up tomorrow and your job is gone. Money doesn't exist. Your boss doesn't exist. The
   > concept of a Monday doesn't exist."

4. **Mack, 293K** — *anaphora, five parallel negations*
   > "You wake up. It's dark. You don't have walls. You don't have a door. You don't have a lock. You don't
   > even have shoes."

5. **Axen, 3.05M** — *bodily-autonomy open, 8-word first sentence*
   > "You wake up when your body is ready. No alarm, no schedule, no place you need to be."

6. **Axen, 1.0M** — *threat open, 13 second-person pronouns in 30s*
   > "You're walking through tall grass 100,000 years ago. The sun is setting. You hear something move
   > behind you."

7. **Stickly, 90K** — *modern-misery open, seven sentences under 4 words*
   > "You wake up. Eight hours staring at a screen. Come home. Eat. Sleep. Repeat. That's your life."

8. **HistoryAlive, 187K** — *imperative aimed at the viewer's literal surroundings*
   > "Look around the room you're in right now. Four walls, a roof, maybe some insulation you've never
   > actually seen but trust is there."

**Payoff-shape calibration** (final beat — the second-person reframe):

- **Mack 1.6M** closes by telling the viewer that next time they flip a light switch or catch woodsmoke on a
  cold night, they are participating in something far older than they realise.
- **Axen 3.05M** closes by contrasting an ancestor who woke "already free, already enough" with a viewer
  working their whole life to retire into that same condition, ending on what was traded away.
- **Stickly 90K** closes by absolving the viewer — not lazy, not broken, merely "300,000 years old".

All three: second person, present tense, abstract, morally loaded, final sentence ≤25 words.

**Anti-example — do not write openings like this** (Mack 24K, same channel, same month):
> "Sleep is biologically speaking, the single most dangerous thing a human being does on a regular basis."

Third person, abstract subject noun, proposition instead of scene, no "you" until sentence three,
first question at 6:51.

---

## Appendix — Reproduction

```
scratchpad/research/
  parse_vtt.py      # rollup-VTT → word-level timed stream (+ .txt, timed.json)
  metrics.py        # all metrics; META maps id → channel/views/duration/label
  qfix.py           # quote-stripped question timing + CTA + 2p-decay
  metrics.tsv       # computed output
  scripts/*.en.vtt  # 16 source transcripts (ASR)
```
Run: `uv venv && uv pip install regex && .venv/bin/python parse_vtt.py scripts/ && .venv/bin/python metrics.py`
