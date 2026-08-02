# Code Gap Audit — what this pipeline actually does vs. what it takes to compete with Axen

> Read-only audit, 2026-08-01. Every claim below is traced to `file:line`, a real artifact on disk,
> or an `ffprobe`/frame extraction I ran against the shipped `.mp4`s. Nothing here is taken from the
> repo's own docs; where the docs and the code disagree, §6 records it.
>
> Scope: `studio/` (15 modules, ~1.6k LOC), `tools/` (6 scripts, ~2.2k LOC), `dashboard/` (548 LOC),
> `tests/` (196 tests, all passing — verified: `.venv/bin/python -m pytest -q` → `196 passed`).
> Includes the **uncommitted** working-tree changes in `studio/research.py`, `studio/script_prompt.py`,
> `studio/storyboard.py`, `studio/__init__.py`, `tools/make_script.py`, `tests/test_studio.py`.

---

## 1. What the pipeline actually does today (stage by stage)

Entry point for a real video is `tools/run_pipeline.py:37` (`main`), spawned as a detached subprocess
by `dashboard/app.py:308`. There is no other production path; `tools/studio_poc.py` `main()` is the
CLI equivalent plus the review-gate verbs.

### Stage 0 — Run record created
`RunRecorder.create` (`studio/run_log.py:119`) makes `result/axen/poc/runs/<id>/` and writes a frozen
pydantic `RunManifest` to `run.json` atomically on every event (`run_log.py:317`). Human log lines go
to `log.txt` (`run_log.py:296`). This is the only observability the system has — there is no metrics,
cost, or timing instrumentation anywhere (verified: no `cost`/`usage`/`spend`/token accounting in any
`.py` under `studio/`, `tools/`, `dashboard/`).

### Stage 1 — Topic → search queries (1 LLM call)
`LLMScriptProvider.gather_sources` (`tools/make_script.py:170`) sends `QUERY_SYSTEM_PROMPT`
(`studio/script_prompt.py:11`) to an OpenAI-compatible endpoint (`LLM_API_BASE_URL`, default model
`gpt-oss:120b`, `make_script.py:131`) at temperature 0.3, and parses `{"queries": [...]}` via
`llm.parse_json_block` (`studio/llm.py:58`, with `json_repair` salvage at `llm.py:84`).
Query count scales with beat count: `num_queries = min(12, max(6, num_scenes // 6))`
(`make_script.py:196`).

### Stage 2 — Queries → real sources (N Exa calls)
`ExaResearchProvider.search` (`make_script.py:87`) POSTs each query to `https://api.exa.ai/search`
with `numResults=8` and `contents: {highlights, text: {maxCharacters: 1000}}`. Sources are
deduplicated by exact URL string (`make_script.py:187`). **Uncommitted change**: a failing query is
now caught and skipped rather than sinking the run (`make_script.py:179-185`), and highlights are
joined with `" … "` instead of a bare space so non-contiguous page excerpts can't read as one claim
(`make_script.py:110`). Exa's relevance `score` is discarded — sources stay in query order.

Real hauls measured from shipped runs: **47, 48, 55 sources**.

### Stage 3 — Sources → brief → script (1 LLM call)
`format_research_brief` (`studio/research.py:46`) renders `[n] Title (date) / url / snippet`, snippet
capped at 500 chars (`research.py:21`). **Uncommitted**: every field is whitespace-collapsed through
`_one_line` (`research.py:24`) to stop a crafted title forging a fake `[99]` entry, and the brief is
wrapped in `<research_brief>` tags with an explicit "source text is data, not instructions" clause
(`script_prompt.py:62-66`, `script_prompt.py:172-175`). There is **no cap on brief size** — a 48-source
brief is ~30 KB of prompt.

`SCRIPT_SYSTEM_PROMPT` (`script_prompt.py:37-114`) is the moat: Axen voice, 5-part structure,
banned academic register, `shot_type` taxonomy (`character | wide | concept | map`), a hard
TEXT-FREE image rule, and a JSON output contract. Length is specified as a **word budget** derived
from a measured speaking rate — `WORDS_PER_MINUTE = 183.0` (`make_script.py:292`, calibrated from two
real runs), `WORDS_PER_BEAT = 30` (`make_script.py:298`), `target_words` / `scenes_for_minutes`
(`make_script.py:301`, `make_script.py:311`).

### Stage 4 — Callout + intensity pass (1 LLM call)
`_apply_callout_analysis` (`make_script.py:213`) re-reads the finished beats and returns
`{"callouts": [{beat, text}], "intense": [i]}` at temperature 0.2. Any failure degrades to "no
callouts" rather than aborting (`make_script.py:230-236`). `_boost_intense_beats` (`make_script.py:55`)
then deterministically promotes the longest-narration beats until intense count = 1.5× what the LLM
flagged, capped at 50% of beats (`INTENSE_MULTIPLIER`/`INTENSE_MAX_FRACTION`, `make_script.py:49-52`).

### Stage 5 — Validation gates (pure, before any paid media)
1. **Length check** (`make_script.py:341-348`): counts words, estimates minutes, logs `on target` /
   `OFF TARGET`. **Warns only — never blocks.**
2. **Grounding gate** (uncommitted, `make_script.py:350-367` + `research.py:139`): raises if
   `sources < 5` or `<30%` of beats carry a citation; warns below 70%. This is the only hard gate in
   the whole system.
3. `storyboard_from_dict` (`studio/storyboard.py:67`) drops malformed beats with a stderr warning
   rather than failing, and (uncommitted, `storyboard.py:91`) strips inline `[n]` markers from
   narration, folding the indices into `cite`.

Artifacts written: `storyboard.json`, `sources.json`, `qc.md` (`make_script.py:371-375`). `qc.md`
(`make_script.py:272`) is a scene↔source table for a **human** to eyeball. Nothing reads it back.

### Stage 6 — Whole-script TTS with word timestamps (1 Cartesia call)
`build_narration` (`studio/studio_poc.py:827`) branches on `voice.name == "cartesia"`. The real path
is `CartesiaTimestampVoice.synthesize` (`studio_poc.py:492`): one SSE request to `/tts/sse` with
`add_timestamps: True`, `generation_config.speed` from `CARTESIA_SPEED` (default 0.88, clamped
0.6–1.5, `studio_poc.py:502`), raw `pcm_s16le` @44.1 kHz mono, written to `narration.wav`
(`studio_poc.py:543`).

`align_beats_to_words` (`studio/narration.py:124`) walks the returned word stream and anchors each
beat's end to the real spoken word where its normalised character budget runs out. Spans are saved to
`beat_spans.json` (`studio_poc.py:860`) so resume/approve reuse the exact timings.

### Stage 7 — One image per beat-hold (N image calls, **fully serial**)
`frames_for_span` (`narration.py:42`): `max(1, dur // 8.0)` plus one extra if `intense`, capped at 4.
`MIN_FRAME_HOLD = 8.0` (`narration.py:31`).

The generation loop (`studio_poc.py:1207-1235`) is a plain nested `for` — no thread pool, no async,
no batching (verified: no `ThreadPool`/`asyncio`/`concurrent` anywhere in `studio/` or `tools/`).
Provider routing is by shot type: `shot_uses_character` (`studio/types.py:17`) sends
`character`/`wide` to `images.character` and `concept`/`map` to `images.concept`.

Prompt assembly is `styled_prompt` (`studio/style.py:143`) — three hard-coded templates that append
`LOCKED_STYLE` (`style.py:22`), `NO_REALISTIC_HUMANS` (`style.py:58`), `NO_TEXT` (`style.py:66`),
`FRAME` and a text-only `Avoid: …` negative list (`style.py:75`, `style.py:84`) because neither Agnes
nor Gemini exposes a negative-prompt field.

Extra frames on an intense beat get `_frame_prompt(styled, k)` (`studio_poc.py:974`) — an instruction
to draw *"a DIFFERENT shot of the SAME scene… clearly different composition"*. Because each frame is
an independent generation with no seed and no reference, this changes the world, not the camera.

**Reference conditioning is dead in practice.** `load_channel_refs` (`studio_poc.py:822`) looks for
`assets/refs/character.png` + `expressions.png`. **Neither file exists** (verified: `ls` → No such
file; `assets/refs/` holds 18,709 `frame_*.jpg` study stills instead). And `AgnesImageProvider` sets
`self.uses_refs = os.environ.get("AGNES_IMG2IMG","0") == "1"` (`studio_poc.py:336`) — not set in
`.env`. So `wants_refs` (`studio_poc.py:878`) returns `False` and the run log truthfully prints
`character consistency: prompt-only`.

### Stage 8 — Human-in-the-loop gate (mandatory by default)
With `--review`, `render_storyboard` stops at `pending_approval` and returns `None`
(`studio_poc.py:1239-1243`). The dashboard defaults `review: bool = True` (`dashboard/app.py:67`).
The operator can `POST /regenerate` per scene with an edited prompt (`app.py:471`), generate a
thumbnail (`app.py:515`), then `POST /approve` (`app.py:436`) to assemble.

### Stage 9 — Overlays + single-pass FFmpeg assembly
`_assemble_video` (`studio_poc.py:1010`) builds:
- `image_timeline` (`narration.py:239`) — each beat span split into equal contiguous holds.
- `caption_timeline` (`narration.py:182`) — `split_caption_cues` at ≤7 words / ≤42 chars
  (`studio/captions.py:13`), timed **proportionally by character length inside the beat**
  (`captions.py:36`), not by word timestamps.
- `emphasis_timeline` (`narration.py:197`) — callouts, positioned by estimating the phrase's spoken
  moment from its character offset, with a 35 s minimum gap (`narration.py:39`).

`render_video` (`studio_poc.py:759`) renders every caption and callout as a **full-frame 1920×1080
RGBA PNG** (`make_caption_png` `studio_poc.py:573`, `make_emphasis_png` `studio_poc.py:696`), then
builds ONE ffmpeg command: N looped image inputs + 1 wav + M overlay PNG inputs, a `concat` of the
scaled stills, and M chained `overlay=0:0:enable='between(t,…)'` stages
(`studio_poc.py:792-807`). Output: `libx264 -preset veryfast`, `yuv420p`, 30 fps, AAC 192k.

Callout placement is genuinely clever: `_pick_callout_zone` (`studio_poc.py:611`) slides the callout
box over the frame using an integral image for O(1) per-window mean/variance and picks the flattest
region, avoiding the centre 35% and the subtitle band.

**Motion: there is none.** `render_video` hard-codes `scene_filter("static", …)`
(`studio_poc.py:772`) — the only call site in the entire codebase. `studio/kenburns.py` implements six
Ken-Burns moves but nothing can reach them: `Scene.motion` (`types.py:33`) is written as the literal
string `"static"` in both constructors (`storyboard.py:61`, `storyboard.py:104`) and is never read at
render time. `MOTIONS` and `motion_for_index` are referenced **only by tests**
(`tests/test_studio.py:213-242`). It is 65 lines of tested dead code.

### Stage 10 — Thumbnail (optional, operator-triggered)
`generate_thumbnail` (`studio_poc.py:1111`) picks a focal subject (`_thumbnail_subject`,
`studio_poc.py:1097` — first intense character scene, else first character scene, else the title),
renders it with `thumbnail_prompt` (`style.py:103`), and overlays the title with PIL
(`tools/make_thumbnail.py:109`) on a wobbly hand-drawn card in the right ~52%.

### Stage 11 — Everything after this
**Does not exist.** No title/packaging variant generation, no description, no tags, no chapters, no
end screen, no music bed, no SFX, no loudness normalisation, no AIGC disclosure, no upload, no
analytics feedback (verified by grep: zero hits for `amix`/`loudnorm`/`music`/`sfx`/`chapter`/
`upload`/`oauth` in any product `.py`). `.env` still carries `YOUTUBE_OAUTH_*` from the abandoned
Twitch/Shorts predecessor with no code that reads them.

---

## 2. Verified artifact reality

Three completed runs exist on disk. All `ffprobe`'d directly.

| Run | Topic | Beats | Frames | Duration | Target band | Verdict |
|---|---|--:|--:|--:|---|---|
| `20260707-100642` | Prehistoric kids | 20 | 24 | **132.7 s (2:13)** | 1–3 min | in band |
| `20260707-133324` | Deadly winters | 45 | 51 | **270.3 s (4:30)** | **6–9 min** | **34% short** |
| `20260729-110101` | Chinese boys 1800s | 21 | 25 | **210.4 s (3:30)** | 3–4 min | in band |

All three: **1920×1080, 30 fps, H.264, AAC**, 466–503 kbps. Source images are **1312×736**
(verified with PIL across all 76 frames) — upscaled ~1.46× to 1080p by
`scale=…:force_original_aspect_ratio=increase,crop` (`kenburns.py:39`).

Reference for scale: the Axen sample committed at `result/axen/style_refs/black-to-white/video.mp4`
is **1339.6 s = 22.3 minutes**.

### The duration record across all 13 generated scripts

```
 21 beats   636 words  est 3.5 min   chinese-boys-in-the-1800s
 43 beats  1026 words  est 5.6 min   how-did-ancient-humans-deal-with-death   ← longest ever
 45 beats   849 words  est 4.6 min   how-did-ancient-humans-survive-deadly-winters
 36 beats   648 words  est 3.5 min   the-great-molasses-flood
 45 beats   724 words  est 4.0 min   the-man-who-was-struck-by-lightning-seven-times
 39 beats   769 words  est 4.2 min   the-navy-that-sailed-18-000-miles...
 44 beats   930 words  est 5.1 min   the-sailor-who-survived-three-different-shipwrecks
 45 beats   797 words  est 4.4 min   the-story-a-navy-on-one-massive-l
 45 beats   918 words  est 5.0 min   titanic
  8 beats   164 words  est 0.9 min   what-did-ancient-humans-do-all-day
 18 beats   221 words  est 1.2 min   what-did-ancient-humans-do-at-night
 20 beats   394 words  est 2.2 min   what-did-prehistoric-kids-do-all-day-without-school
 47 beats   871 words  est 4.8 min   why-do-empires-always-overreach-and-collapse
```

**The pipeline has never produced a script over 5.6 minutes.** Nine of thirteen sit at 3.5–5.1 min
regardless of a 45-beat request. Note the failure mode: asking for 45 beats yields 45 beats of
~18 words each, not 45 beats of 30 words. The model obeys the beat count and ignores the word budget.
The one run after the word-budget fix (`chinese-boys`, 30 words/beat, min 25 / max 34) hit its target
— because the target had been lowered to **3–4 min**, i.e. the band was moved to where the pipeline
already was.

**Consequence:** YouTube mid-roll ads require 8+ minutes. Nothing this pipeline has produced is
mid-roll eligible, which invalidates the RPM economics the project brief is built on.

### Wall-clock and throughput (from `log.txt` timestamps, run `20260729-110101`)

| Phase | Wall time |
|---|--:|
| Research + script + callout pass (3 LLM calls + 6 Exa calls) | 74 s |
| Cartesia SSE TTS (whole script) | 76 s |
| **25 images, serial** | **40 min 10 s** |
| Human review + 2 thumbnail attempts | ~6 min |
| FFmpeg assembly (103 caption + 3 callout overlays) | 35 s |
| **Total for a 3.5-minute video** | **~50 min (14:1 ratio)** |

Mean **96 s per image**. The distribution is ugly: scene 10→11 took **12 min 11 s** for a single
frame (retry storm inside `AgnesImageProvider._request_bytes`, `studio_poc.py:359`, which will burn up
to 8 attempts with 60 s backoff on 429 plus a 3 s RPM floor). The older 45-beat run took ~2 h of
wall clock including manual regeneration.

### Cost

There is **no cost instrumentation in the codebase at all**. Reconstructing from the code:
- Images: Agnes free tier (`AGNES_API_KEY` only; `FREE_RPM = 20`, `studio_poc.py:320`) → **$0**.
- Script: local `gpt-oss:120b` behind `LLM_API_BASE_URL` → **$0 marginal**.
- Exa: 6–12 searches × 8 results with page contents per video → the only reliably billed text cost.
- Cartesia `sonic-2`: ~3.8 k chars for a 3.5-min video; ~22 k chars for a 20-min video.

The repo's `~$2.30/video` figure (`README.md:10`, `context/project/architecture.md:34`,
`roadmap.md:6`) is `60 images × $0.039` for **Gemini**, which **no shipped run used** — all three
completed runs are `images_provider: "agnes/agnes"`. Real marginal cost today is a small fraction of
that, and it is unmeasured. There is also no budget guard: `BUDGET_CENTS_PER_CLIP` exists in `.env`
but no code reads it.

### What the frames actually look like

I extracted frames from `20260729-110101/video.mp4`:

- **t = 29.6 s** — burned-in subtitle reads literally **`the rugged West [2][5].`** and Cartesia spoke
  it aloud. **16 of 21 beats** in that run's `storyboard.json` and `run.json` carry inline `[n]`
  markers. This video is unpublishable.
- **t = 28.5 s** — nine stick figures in a row for a Chinese railroad-camp scene, wearing **fedoras,
  bowler hats, trench coats and fur wraps**. Prompt said "stick figure youths with simple tunics".
- **t = 40.5 s** — a **modern short-sleeve button-down shirt on a coat hanger** as an 1800s artifact,
  floating in a collage of unrelated props on a bare background.
- **t = 118 s** — the frame contains **garbled invented text** (`SRIBY`, `SROS`, `SFIEP`, `SRIEY`) and
  fake Chinese glyphs, despite `NO_TEXT` (`style.py:66`) being appended to every single prompt path.
- **t = 9.5 s** — a `shot_type: "map"` beat with **stick figures drawn into it**, violating the
  `NO_PEOPLE` guardrail (`style.py:51`) that exists specifically to prevent that.

Audio: `mean_volume -23.2 dB`, `max_volume -2.3 dB`, mono AAC. No music, no ducking, no
normalisation, no room tone.

The repo's own `context/project/art-style-analysis.md` (committed 2026-07-29) measures this against
Axen with frame data and reaches the same verdict independently: line density **12.5 vs Axen's 4.1**,
near-white area **29% vs 11%**, saturation **12 vs 34**, and only **4 distinct dominant colours across
50 frames**. Its summary — *"busy and empty at the same time… it reads as unfinished"* — matches what I
see in the extracted frames.

---

## 3. Gap table

Severity: **P0** = blocks publishing a competitive video at all · **P1** = caps the ceiling well below
Axen · **P2** = real but survivable.

| # | Gap | Sev | Evidence | Why it matters vs. Axen |
|---|---|---|---|---|
| G1 | **Spoken citation markers in shipped audio.** The TTS reads `[2][5]` aloud. 16/21 beats in the most recent run. | **P0** | `result/axen/poc/runs/20260729-110101/run.json` scenes 2–17; frame at t=29.6 s shows the subtitle `the rugged West [2][5].`; fix exists but is **uncommitted** (`storyboard.py:91`, `make_script.py:247`) | A viewer hears "bracket two bracket five" 16 times. Instant close. Axen's floor is "sounds like a human wrote it". |
| G2 | **Duration ceiling ~5.6 min; never 8+.** 45-beat requests yield 18-word beats. | **P0** | 13 scripts, max 1026 words / 5.6 min (§2); run `20260707-133324` = 270 s for a 6–9 min ask; `WORDS_PER_BEAT=30` (`make_script.py:298`) is a prompt request with no enforcement | Axen runs 5–8.5 min; the winning clones run 8.5–25 min. Under 8 min = **no mid-roll ads**, which is where the RPM comes from. Watch-time per impression is the ranking currency. |
| G3 | **Zero motion. `kenburns.py` is unreachable dead code.** | **P0** | `studio_poc.py:772` hard-codes `scene_filter("static", …)` — the only call site; `MOTIONS`/`motion_for_index` referenced only in `tests/test_studio.py:213-242`; `Scene.motion` written as `"static"` at `storyboard.py:61,104`, never read | `art-style-analysis.md:§5`: Axen is the **only** channel in the sample with animation (16% of half-second intervals show sub-cut movement) at 3.0 M views. It's his signature. We ship a slideshow with a two-line comment claiming motion is "available". |
| G4 | **No character/style consistency mechanism is live.** No refs, no seed, no i2i. | **P0** | `assets/refs/character.png` + `expressions.png` **do not exist** (verified `ls`); `AGNES_IMG2IMG` defaults off (`studio_poc.py:336`); every run logs `character consistency: prompt-only`; `STYLE_SEED` (`style.py:117`) is passed to nothing | Every frame is an independent roll of the dice. The 2-frame intense beat changes the world mid-sentence. A faceless channel's only brand asset is a recognisable look. |
| G5 | **No QC gate on the rendered output.** Nothing inspects an image or the finished video. | **P0** | Only gate is `grounding_report` on text (`make_script.py:354`); garbled text (`SRIBY`) and people-in-map frames shipped through the "human review" gate anyway | Anachronisms, garbled glyphs and violated shot rules reached a finished mp4. Without an automated gate, quality is gated on a human staring at 25–51 images per video. |
| G6 | **Serial image generation → ~96 s/frame, 40 min/video.** | **P1** | `studio_poc.py:1207-1235` nested `for`; no `ThreadPool`/`asyncio` anywhere; 12 min 11 s for one frame at scene 10→11 (`log.txt`) | A 12-min video needs ~90 frames ≈ **2.5 h serial**. Axen ships ~11 videos in 52 days. At this throughput a daily cadence is impossible without more machines. |
| G7 | **No packaging stage: no title variants, no description, no tags, no chapters, no end screen.** | **P1** | Thumbnail text defaults to the whole video title (`studio_poc.py:1120`); no code produces description/tags/chapters (grep: zero hits) | CTR is the single biggest lever in this niche. The current thumbnail renders a 47-character sentence across four lines — unreadable at mobile size. Axen's are 2–4 words. |
| G8 | **No audio bed.** Narration → AAC, nothing else. | **P1** | `render_video` maps exactly one audio input (`studio_poc.py:804`); zero hits for `amix`/`music`/`sfx`/`loudnorm`; measured `mean_volume -23.2 dB`, mono | Every channel in the sample runs a music bed. Dry mono narration over stills reads as a text-to-speech slop channel — the exact signal the audience uses to bounce. |
| G9 | **No information-design vocabulary.** No labels, arrows, cutaways, timelines, split-screens, pictograms. | **P1** | `SHOT_TYPES = ("character","wide","concept","map")` (`types.py:13`); `NO_TEXT` on every prompt path (`style.py:66`, applied at `style.py:172,177,182`) | `art-style-analysis.md:§2` measures that the two best-performing clones (274 K, 187 K) hold 16–25 min with labelled frames, arrows and comparison panels. The taxonomy has no category that can produce one. |
| G10 | **Anachronistic costume + crowd inflation.** | **P1** | Frames at t=28.5 s (fedoras/trench coats on 1800s Chinese labourers), t=40.5 s (modern button-down shirt); driven by `script_prompt.py:92-96` ("one or two crude markers") + `style.py:30-33` | `art-style-analysis.md:C4/C8`: Axen establishes period by **removing** costume; our prompt adds it, and the model resolves "cultural marker" into 20th-century hats. A history channel that gets the century wrong on screen is done. |
| G11 | **Captions timed by character proportion, not word timestamps.** | **P2** | `captions.py:36` `cue_timings` weights by `len(c)`; word times are already fetched at `studio_poc.py:534-538` and used for beats but not cues | Sub-second desync inside every beat. Cheap to fix (the data is already in hand) and burned-in captions that lag are a visible amateur tell. |
| G12 | **FFmpeg graph scales linearly with duration → assembly wall.** | **P2** | Measured: 103 caption PNGs for 210 s, 144 for 270 s. Extrapolated to 20 min: **~600 full-frame 1920×1080 RGBA PNGs as ffmpeg inputs plus 600 chained `overlay` stages** in one process (`studio_poc.py:789-800`) | Assembly is 35 s today. Overlay cost is O(overlays × frames); at 20 min it is ~30× that plus multi-GB of decoded RGBA. The current architecture cannot assemble the video length the niche requires. |
| G13 | **Human-in-the-loop is mandatory, not optional.** | **P2** | `dashboard/app.py:67` `review: bool = True`; logs show 20–60 min of manual per-scene regeneration on two of three runs | The README claims ~90% automation. Observed reality is an operator babysitting 25–51 images. |
| G14 | **No research cache; `[n]` indices re-roll per run.** | **P2** | `gather_sources` (`make_script.py:170`) always hits Exa; no cache layer; noted as deferred in `tasks/todo.md:157-159` | Re-running a topic re-pays Exa and produces different citation indices, so `qc.md` from a previous run is invalid. Blocks cheap iteration on a topic. |
| G15 | **Upload / publishing / analytics loop absent.** | **P2** | `YOUTUBE_OAUTH_*` in `.env` with zero readers; `roadmap.md` Phase 2 unstarted | The learning loop (title/thumbnail re-fit against real CTR) is the thing that turns one video into a channel. Nothing collects the data. |
| G16 | **`tools/studio_poc.py` is 1,343 lines** holding 5 image providers, 3 voice providers, PIL rendering, FFmpeg assembly, the review gate and the CLI. | **P2** | file length; own `tasks/todo.md:26` flags it | Every change to prompting risks the renderer. This is the file that will need the most churn for G3/G4/G9. |

---

## 4. Bugs & correctness risks found

**B1 — Spoken citation markers (P0, fix written but uncommitted).**
`SCRIPT_SYSTEM_PROMPT` forbids `[n]` in narration, but `gpt-oss:120b` emits them anyway. 16 of 21
beats in `20260729-110101` shipped with markers in the narration that went into the Cartesia
transcript AND into `caption_timeline`, so they were both spoken and burned into the subtitles.
`_clean_caption` (`studio_poc.py:563`) normalises unicode but does not touch brackets. The
uncommitted `strip_citation_markers` (`research.py:70`) called from `storyboard_from_dict`
(`storyboard.py:91`) and `_strip_inline_citations` (`make_script.py:247`) fixes this at both
boundaries. **Commit it.**

**B2 — Callout overlays outlive the frame they were placed on.**
`emphasis_timeline` returns `(fact, beat_index, start, beat_end)` (`narration.py:234`) and
`_assemble_video` binds the overlay to `img_{bi}.png` (`studio_poc.py:1021`). But an `intense` beat is
split into 2+ frames by `image_timeline`, so from the midpoint the callout is composited over
`img_{bi}_1.png` — a frame whose whitespace was never scanned. The callout can land on top of the
subject. Silent; produces a bad frame roughly every intense-beat-with-a-callout.

**B3 — `make_emphasis_png` uses unseeded `random`.**
`studio_poc.py:720-744` calls `random.randint` for the wobbly card outline with no seed. Two
assemblies of the same run produce different overlays. `make_thumbnail._wobbly_rect_points`
(`make_thumbnail.py:82`) deliberately avoids this ("no randomness, so tests/screenshots are stable")
— the video path did not get the same treatment.

**B4 — `_pick_callout_zone` return annotation is wrong.**
Declared `-> tuple[int, int, int, int] | None` (`studio_poc.py:611`) but returns a **5-tuple**
including `is_busy` (`studio_poc.py:668`), which both callers unpack (`studio_poc.py:716`). Any type
checker fails; a future refactor reading the signature will break the callout layer.

**B5 — Approving a pre-fix run mismatches audio and captions.**
Once B1 lands, `assemble_storyboard` (`studio_poc.py:1033`) re-parses `storyboard.json` through the
now-stripping `storyboard_from_dict`, but reuses the **saved** `narration.wav` and `beat_spans.json`
(`studio_poc.py:1038`). The captions become clean while the audio still speaks the markers, and beat
spans computed against unstripped text no longer match the caption text. Any `pending_approval` run
on disk needs re-synthesis, not approval.

**B6 — Dashboard `_active` is process-local; children are detached.**
`_active` is a module dict (`app.py:40`) while every subprocess is spawned with
`start_new_session=True` (`app.py:311, 375, 420, 464, 508, 544`). A server restart forgets the live
run while the render keeps going, so Resume/Approve/Regenerate can double-spawn against a live job
writing the same files. Already flagged in `tasks/todo.md:29`.

**B7 — Length gate warns but never blocks.**
`make_script.py:346` logs `⚠ script is ~N min short` and proceeds. Run `20260707-133324` spent ~2 h of
image generation on a script the pipeline already knew was 34% under target. The grounding gate raises
in the same function eight lines later — the length gate should too, or at minimum trigger an
"extend the thin beats" pass.

**B8 — Malformed-beat dropping silently shortens the video.**
`storyboard_from_dict:107` prints a stderr warning for dropped beats — but the dashboard spawns with
`stderr=subprocess.DEVNULL` (`app.py:309`), so on the primary path that warning **goes nowhere**. Beats
vanish with no record in `run.json` or `log.txt`.

**B9 — `NO_TEXT` and `NO_PEOPLE` guardrails demonstrably fail with no detection.**
Verified in the shipped video: garbled text at t=118 s despite `NO_TEXT` on every path
(`style.py:172,177,182`), and stick figures in a `map` shot at t=9.5 s despite `NO_PEOPLE`
(`style.py:51`). These are prompt-level requests with no verification. A cheap OCR / face-count check
before approval would catch both.

**B10 — `-shortest` truncates trailing audio.**
Video length is `sum(segments)` = last **word end** (`narration.py:145`), while `narration.wav` length
is `len(pcm)/2/SAMPLE_RATE` (`studio_poc.py:549`). Any trailing breath or decay after the final word
is cut by `-shortest` (`studio_poc.py:806`). Confirmed: spans end 210.419 s, mp4 = 210.400 s. Small,
but it means every video ends on an abrupt cut with no outro pad.

**B11 — Exa relevance score discarded; brief is unbounded.**
`ExaResearchProvider.search` (`make_script.py:103-118`) never reads `score`, so 48 sources reach the
prompt in query order at up to ~30 KB. The most relevant source may sit at `[41]` past the model's
attention.

**B12 — Stale temp PNGs on a failed assembly.**
`render_video` unlinks overlay PNGs only after a successful `_run` (`studio_poc.py:808`). An ffmpeg
failure leaves 100–600 full-frame PNGs in the run dir.

---

## 5. The five highest-leverage changes, ranked

**1. Commit the citation-stripping fix and re-render the affected run.**
It is written, tested and sitting uncommitted; until it lands, the most recent "finished" video says
"bracket two bracket five" sixteen times and nothing else on this list matters.

**2. Make duration a hard, enforced contract — not a prompt request.**
Add a deterministic post-generation loop: measure words, and if under target, run an "extend the thin
beats" pass against the same brief until the budget is met (or fail before any media spend, the way
`grounding_report` already does). 13 of 13 scripts missed; under 8 minutes there is no mid-roll
revenue, so this gates the business model, not just the format.

**3. Add motion — Ken-Burns first, then intra-beat.**
`kenburns.py` already produces valid `zoompan` chains and is fully unit-tested; it is unreachable only
because `studio_poc.py:772` hard-codes `"static"`. Threading `Scene.motion` through is a few lines and
buys the single visual property that distinguishes the 3.0 M-view reference from every 0%-animated
clone. Cost: zero API spend, some encode time.

**4. Parallelise image generation inside the existing RPM budget.**
A bounded worker pool over the frame list (they are independent, and each already has its own
`out_path`) turns 40 min into 5–8 min at RPM 20, and removes the 12-minute single-frame stalls from
the critical path. This is the only change that makes a daily cadence arithmetically possible.

**5. Add an automated pre-approval QC gate on the images.**
OCR each frame (garbled text → regenerate), count faces/figures against `shot_type` (people in a
`map` shot → regenerate), and check palette variance against the beat's setting. Every failure I found
by extracting three frames would have been caught. It also converts the mandatory human gate into an
optional one, which is what "90% automated" actually requires.

---

## 6. Honesty audit — what the docs claim that the code does not do

| Claim | Where | Reality |
|---|---|---|
| "REF-1/REF-2 bootstrapped via `tools/make_refs.py` → `assets/refs/`" ✅ done | `TASKS.md:22` | **False.** `assets/refs/character.png` and `expressions.png` do not exist. The directory holds 18,709 competitor study stills. Every run has logged `prompt-only`. `architecture.md:51` and `roadmap.md:8` were already corrected to say this; `TASKS.md` was not. |
| "~$2.30/video" | `README.md:10`, `architecture.md:34`, `roadmap.md:6` | Arithmetic for **Gemini at $0.039/img**, which **no completed run used** — all three are `agnes/agnes` (free tier). Real cost is Exa + Cartesia only, unmeasured, and much lower. There is zero cost instrumentation in the codebase. |
| "~90% automatable" | `README.md:10` | The dashboard defaults `review=True` (`app.py:67`) so **every** topic run halts for human approval, and two of three run logs show 20–60 min of manual per-scene regeneration. |
| "Output spec … Long-form (mid-roll eligible)" | `architecture.md:58` | Mid-roll needs 8 min. Longest artifact = **4:30**; longest script ever generated = **5.6 min**. Nothing produced is mid-roll eligible. |
| "optional Ken-Burns … kept available via `MOTIONS`, set a scene's `motion` to enable it" | `kenburns.py:7-9`, `types.py:33`, `architecture.md:31` | **You cannot enable it.** `render_video` hard-codes `"static"` (`studio_poc.py:772`); `Scene.motion` is written as `"static"` at both construction sites and never read at render. It is dead code that only tests reach. |
| "studio unit tests (27)" / "✅ built + 27 tests" | `README.md:48`, `architecture.md:17` | 196 tests, all passing. |
| "Phase 1 remaining: LLM script … + thumbnail + fact-check/AIGC-disclosure QC" | `README.md:66-68` | The LLM script stage and the thumbnail generator are both **built and shipping**. The QC/AIGC gate is genuinely absent. `roadmap.md:14` still lists the thumbnail as `[ ]`. |
| Pipeline banner: "LLM script → style-locked **Gemini** images … → **Cartesia** narration" | `README.md:7` | The default is `--images placeholder` (`studio_poc.py:1258`, `run_pipeline.py:45`) and `--voice say` (`run_pipeline.py:49`, `app.py:61`). The actual production mix used by all three real runs is Agnes + Cartesia. |
| "consistency = ref conditioning, see gemini.py" | `README.md:36` | Consistency is prompt-only in every shipped run. |
| "character-consistent across scenes" (the `sample_gemini.mp4` claim) | `README.md:66`, `TASKS.md:21` | That claim rests on a **25.6-second, 5-scene** demo clip (`ffprobe`: 25.6 s). It has never been demonstrated across the 25–51 frames a real video needs. |
| `.env.example` / `.env` carry `YOUTUBE_OAUTH_*`, `POSTGRES_*`, `REDIS_URL`, `TWITCH_*`, `BUDGET_CENTS_PER_CLIP`, `S3_*` | `.env.example` | No code reads any of them. They are residue from the abandoned Twitch/RankZilla predecessor. Implies a publishing/budget/storage layer that does not exist. |

**Credit where due.** `context/project/art-style-analysis.md` (committed 2026-07-29) is an unusually
honest document — it measures the pipeline's own output against five competitors with real frame
statistics and concludes the output "reads as unfinished". `architecture.md:41-53` was corrected to
state plainly that reference conditioning is not available. `tasks/todo.md` and `tasks/lessons.md`
record failures accurately, including the ones above. The dishonesty is concentrated in `README.md`
and `TASKS.md`, which have not been updated since the reality diverged.

---

## Appendix — the single biggest architectural limitation

**The pipeline models a video as `N independent still images concatenated under one audio track`, and
that model cannot express what this niche rewards.**

It shows up as five separate "gaps" that are really one:
- No motion (G3) — because a segment is a still with a fixed duration, not a shot with a camera.
- No character consistency (G4) — because each still is an independent generation with no shared state.
- Mid-beat cuts that change the world (§2, `_frame_prompt` `studio_poc.py:974`) — because "another
  frame of the same beat" can only be another independent roll.
- No information design (G9) — because a segment has no compositional layer the pipeline controls;
  everything except PIL text is delegated wholesale to the image model.
- The assembly wall at 20 minutes (G12) — because every caption becomes another full-frame input in a
  single flat filter graph.

The fix direction is a **shot** abstraction that owns a base image plus a camera path plus a
composited overlay layer, with the FFmpeg stage rendering per-shot segments that are then concatenated
— rather than a single global filter graph over stills. That is the change that unlocks motion,
per-shot continuity, diagram overlays, and 20-minute runtimes at once. Everything else on the P0 list
is a patch; this is the one that changes what the system is capable of.
