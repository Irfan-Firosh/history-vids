# Shot-rate correction and render rebuild — design

**Date:** 2026-08-02
**Status:** approved (design); implementation plan pending
**Supersedes assumptions in:** `context/project/README.md`, `context/project/architecture.md`

---

## 1. Why

Five parallel research agents plus direct measurement produced three findings that change what
this pipeline should be. All three contradict something the project currently believes.

### 1.1 The reference has no motion at all

Forensics over 9 videos / 5 channels / 27,723 frame pairs
(`context/research/2026-08-01/04-video-forensics.md`):

| Motion type | Axen | Mack | Stickly | HistoryAlive |
|---|---|---|---|---|
| Full-frame hard cut | 70.6% | 88.1% | 73.6% | 100% |
| Foreground swap over held background | 27.8% | 11.7% | 26.4% | 0% |
| Camera move | **0%** | **0%** | **0%** | **0%** |
| Character animation | **0%** | **0%** | **0%** | **0%** |
| Dissolve / wipe | **0%** | **0%** | **0%** | **0%** |

Runtime is 94.6–97.7% frozen; all 894 measured transitions are exactly one frame; median shot
moves 0.00 px and zooms 0.000%.

**The existing static-image, hard-cut grammar is correct.** Ken Burns would move output *away*
from the reference. `studio/kenburns.py` stays unreachable by design, not by accident.

This also refutes the animation-tooling report's headline recommendation
(`context/research/2026-08-01/03-animation-tooling.md`), which proposed SVG draw-on reveals as
"the dominant visual verb of the Axen style." That claim was asserted without measurement; the
forensics measured 0% wipes and 1.3% pop-ons. **Where the two reports conflict, forensics wins.**

### 1.2 The real gap is shot rate, and it is one constant

| | Today | Axen reference |
|---|---|---|
| `MIN_FRAME_HOLD` | 8.0 s | — |
| Shots per 8-min video | 52 | ~218 |
| Seconds per shot | 9.2 | 2.2 (p10 0.9 / p90 4.6) |
| Cuts per minute | ~6.5 | 16–18 |

Setting `MIN_FRAME_HOLD = 2.2` yields 208 shots at 2.3 s — within 5% of reference. The
multi-shot mechanism (`frames_for_span`, `image_timeline`) already exists, is tested, and already
handles resume and re-edit. It was tuned to an assumption the data now contradicts.

Reference cuts on *clause* at 9–11 narration words per image, not on a timer. Equal subdivision
is a good approximation; clause-aware splitting is the improvement.

### 1.3 The assembler cannot render long-form — measured, not inferred

`tools/studio_poc.py:759 render_video` builds one FFmpeg filtergraph: N image inputs, one audio
input, M full-frame PNG overlay inputs, and M *serially chained* `overlay` nodes.

Benchmark on this machine (M2), fixed 2 s output, 60 frames:

| Serial overlay depth | s/frame |
|---|---|
| 32 | 0.303 |
| 64 | 0.734 |
| 128 | 1.391 |
| 256 | did not finish in 7 min |

An 8-min video needs ~290 caption cues and 14,400 frames. Linear extrapolation (generous — the
curve is worse than linear) gives ~3.2 s/frame → **~12.8 hours**. At 22 min it is ~72 hours.

This is not slowness; it is a wall. `render_video` is the one component that must be replaced.

### 1.4 Corrections to recorded project facts

- **`context/project/README.md:10` is wrong.** Axen is **not monetized** ($0 AdSense, verified
  2026-08-02 via NexLev), has 11 videos, and has been dormant ~36 days. The "~$13K/mo, RPM $4.61"
  figure came from a third-party estimator and was never verified.
- Mack (`@MackExplains7`, `UCaS30yIIV6y2zqSnHGdIGMQ`) launched 23 days *after* Axen and now leads
  on every axis: 68.1K vs 50.1K subs, 7.97M vs 5.12M views, 49 vs 11 videos, monetized vs not.
  Its revenue is primarily a Teachable course funnel, not AdSense.
- **Citations do not predict performance.** The 24K-view underperformer cites *more* than three
  Mack winners (5.2/1k). `README.md:12` names real citations as "the moat"; the evidence says they
  buy defensibility and rights-safety, not retention. The grounding gate remains worth having as a
  correctness guarantee.
- `KO_035Jkc2E` ("ThenFolk") is **not** a failure case — it was 3 days old at measurement. No
  craft inference can be drawn from its view count. Earlier analysis treating it as a failure is
  void.

**Format decision (user, 2026-08-02):** target the Axen pole — 8 min, 196 wpm, ~1,570 words,
median shot 2.2 s, 16–18 cuts/min, ~208 shots, dry VO with no music bed. Recorded counter-evidence:
≥12-min channels in this niche show ~7.5× the median views and ~2× the RPM. The architecture below
is length-agnostic, so this is reversible.

### 1.5 Bugs found during design

- **Captions drift.** `studio/narration.py:182 caption_timeline` anchors cues to beat spans then
  spreads them *proportionally by character count*, while `align_beats_to_words` beside it uses
  genuine Cartesia word timings. Subtitles are on screen 100% of runtime.
- **Stale docstring.** `studio/captions.py:3` claims "Cartesia gives no word timestamps."
  `CartesiaTimestampVoice` exists and the pipeline requests `add_timestamps`.
- **Every frame is upscaled.** `agnes.DEFAULT_SIZE = "1024x576"` → 1920×1080 is a 1.875× upscale.
  Reference linework is ~3 px at native 1080p; upscaling softens exactly the thin-line signature.
- **Run settings are not persisted.** `RunManifest` has no `captions` field, so re-run and resume
  silently fall back to defaults (`dashboard/app.py:328`).
- **Reference images do not exist.** `assets/refs/character.png` and `expressions.png` are absent;
  the directory holds 18,709 gitignored competitor stills. `AGNES_IMG2IMG` defaults off because the
  img2img path hangs. No character-consistency mechanism is live.

---

## 2. Decision: replace one stage, retune and extend the rest

Quality in this project lives in the script, the image style, the shot rhythm, and the caption
craft. A ground-up rewrite would discard `align_beats_to_words` (word-anchored cuts that snap to
real speech pauses), the grounding gate, `RunRecorder`/resume/review, the provider Protocols, and
196 passing tests — none of which are quality bottlenecks and all of which are correct. It would
spend the budget that should go to scene archetypes.

Exactly one component is unfixably wrong, and it is fully replaced.

| Layer | Verdict |
|---|---|
| Research → script → grounding gate | Keep |
| TTS + word-anchored beat alignment | Keep |
| Shot allocation | Edit (one constant + clause-aware splitting) |
| Caption timing | Fix bug |
| `render_video` | **Replace** |
| Image style / archetypes | Build new |

**Named risk:** this is an art-direction problem wearing a tooling costume. Once the assembler
scales and shot rate is right, the remaining gap is a library of scene archetypes with real visual
variety, which no architecture decision solves. The style-metrics gate is the defence: it makes
"the art is drifting" a number rather than a feeling.

---

## 3. Architecture

```
storyboard + word timings
  │
  ├─▶ ❶ shot plan      studio/shots.py  (pure)
  │      clause-aware split at 9–11 words → ~208 Shots
  │      each Shot: (start, end, image_key, role)
  │
  ├─▶ ❷ image build    Agnes @ 20 rpm, pipelined + content-hash cached
  │      callouts baked into the PNG with PIL  ← zero ffmpeg overlay cost
  │
  ├─▶ ❸ segment render  one short mp4 per shot, parallel, cached
  │      identical codec params → concat can stream-copy
  │
  └─▶ ❹ final pass      concat demuxer + audio mux + libass subtitle burn
         ONE filtergraph, ZERO overlay nodes
```

**Callouts are baked, not overlaid.** They are sparse (`CALLOUT_MIN_GAP_SEC = 35` → ~13 per 8-min
video) and always anchored to a beat's first frame, so PIL composites them at image-build time.
Even 13 full-frame overlays would cost ~29 min of ffmpeg time by the benchmark above; baking costs
nothing. `make_emphasis_png`'s whitespace-placement logic moves upstream rather than being rewritten.

**Captions become one ASS file.** They are the only layer that must be time-based, because cue
boundaries do not align to shot boundaries. libass renders them in a single filter with real
typography (custom font, outline, baseline control) — also the best available route to the
hand-lettered marker-caps signature.

**Segments are the cache unit,** keyed on `hash(image bytes + duration + filter params + version
salt)`. Change one scene, re-render one segment.

Expected wall time: ~10–15 min images (rate-limited, not latency-bound) → ~1–2 min segments
(parallel) → seconds to concat → ~1–2 min final encode via videotoolbox. **~20 minutes total.**

**ffmpeg selection.** This machine's ffmpeg 8.1.2 has no libass, libfreetype, or drawtext — the
PNG-overlay design was forced, not mistaken. `ffmpeg-full` is keg-only (installs alongside without
conflict) and pulls `libass freetype fribidi harfbuzz`. `FFMPEG_BIN` selects the binary; capability
is probed at startup.

---

## 4. Components

`studio_poc.py` is 1,343 lines against an 800-line ceiling in the project's coding-style rules, and
mixes provider I/O, PIL compositing, ffmpeg assembly, and orchestration. This work splits it along
seams that already exist. Providers move to `tools/providers/`; render moves to `tools/render/`;
orchestration remains.

**New, pure (`studio/`):**

| Module | Responsibility |
|---|---|
| `shots.py` | `plan_shots(beat_spans, narrations, word_times) → list[Shot]` |
| `style_metrics.py` | Frame metrics → `conforms(metrics, envelope) → Report` |
| `script_rubric.py` | The L1 gate; same shape as `research.grounding_report` |
| `subtitles.py` | Cues → ASS file text (pure string generation) |

**Edited, pure:** `narration.py` (`MIN_FRAME_HOLD` 8.0 → 2.2; word-anchored `caption_timeline`),
`captions.py` (docstring), `run_log.py` (`RunManifest` gains `settings` + `stats`).

**New, side-effecting (`tools/render/`):** `ffmpeg.py` (binary selection, capability probe,
fallback), `segments.py` (per-shot mp4 + cache), `assemble.py` (concat, mux, subtitle burn).

**Manifest additions:**

```
settings: { captions, min_minutes, max_minutes, images_provider, voice, shot_hold }
stats:    { shots, images_generated, images_cached,
            stage_seconds: { script, research, tts, images, segments, assemble },
            script_rubric:  { score, passed, failures[] },
            style_envelope: { saturation, colour_bins, near_white, conforms },
            duration_target_sec, duration_actual_sec,
            subtitle_backend }
```

Every field is a number or bool the pipeline already knows or computes for a gate. `settings`
persisting is what fixes re-run/resume losing the captions choice.

**Deferred by agreement:** richer dashboard UI beyond persisting the existing toggle; cost
instrumentation (none exists today — its own pass); background reuse pending the keying spike.

---

## 5. Data flow and failure modes

Gates sit immediately before the expensive stage they protect.

```
topic → research → script
        ├─ gate: grounding      (exists)  ─┐  both free,
        └─ gate: script rubric  (new)     ─┘  refuse before any spend
   ↓ TTS (one Cartesia call, add_timestamps) → word times
   ↓ align_beats_to_words → beat_spans (cuts land in silence)
   ↓ plan_shots → ~208 Shots
        └─ gate: style pre-flight (new) ── ONE image, ~5 s, vs envelope
   ↓ image build (cached) · callouts baked
   ↓ segments (parallel, cached) → concat → mux + subtitles
        └─ check: motion conformance vs Axen targets
```

The **style pre-flight** exists because checking the envelope after 208 images tells you the art
drifted only once you have paid for it. One image costs five seconds.

**Rate limiting must be a shared token bucket.** Eight workers each honouring a 3 s floor gives
160 rpm, not 20. The limiter is one object shared across the pool; existing per-request backoff
honouring `Retry-After` remains the second line of defence.

**A permanently failed image must never ship silently.** After retries exhaust: fall back to the
secondary provider, then a placeholder — recorded as degraded on the manifest and shown in the
review gate. Falling back to the *previous* shot's image is specifically wrong; `image_timeline`
guarantees adjacent segments are never the same file, and a cut-back reads as a glitch.

**The cache key is the sharpest edge.** A key that omits an input silently ships stale frames.
Key on the full canonicalised parameter set plus a version salt bumped whenever the renderer
changes. When in doubt the key gets longer.

**Missing libass must not silently cost 12 hours.** The fallback path *is* the current PNG-overlay
renderer. Probe at startup; fall back only for short runs, and **refuse** long ones with the exact
fix. Starting a half-day render is worse than refusing. `subtitle_backend` is recorded either way.

**Degraded input is recorded, not hidden.** The offline `say` voice returns no word timings, so
clause-aware splitting is impossible; shot planning falls back to equal subdivision and says so.

---

## 6. Testing

**L0 — pure unit tests.** New: `test_shots.py`, `test_style_metrics.py`, `test_script_rubric.py`,
`test_subtitles.py`. Edited where `MIN_FRAME_HOLD` and word-anchored captions ripple. The 196
existing tests stay green.

One regression test is written before the code: a hook question ending `?"` must be detected at its
true timestamp. Naive parsing reads Mack's at 313 s instead of 23 s, inverting the most important
rubric rule.

**L1 — rubric calibration.** Per `tasks/lessons.md`: *a threshold you haven't replayed is a guess.*

| Corpus | Expected |
|---|---|
| Competitor winners (transcripts already downloaded) | all pass |
| The 24K same-cohort underperformer | fails |
| The 13 existing generated scripts | whatever it says — the honest baseline |

If a threshold rejects a 996K-view video, the threshold is wrong. `--skip-rubric` provides an
informed-operator escape.

**L2/L3 — `tools/style_check.py`.** `--probe` (one image) and `--batch N` (archetype spread +
contact sheet). Envelope lives in `context/project/style-envelope.json` as **numbers only**; no
competitor media enters the repo.

**L4 — assembler tested offline.** A golden fixture (one run's storyboard + beat spans + tiny
synthetic PNGs, checked in) exercises shot-plan → segment → concat → subtitle with **zero API
calls**. This is the test that would have caught the 12.8-hour filtergraph.

**L5 — `tools/conformance.py`.** Measures our own `video.mp4`: `cuts/min ∈ [16,18]`, median shot
≈ 2.2 s (p10 0.9 / p90 4.6), `%frozen ≥ 94.6`, style envelope over sampled frames.

**Risk on the record:** unit tests prove the metric math, not that the envelope is the right
target. Its validity rests on the forensics sample (9 videos, 5 channels, 45 min, 2,703 style
frames). If that sample is biased the gate faithfully enforces the wrong thing. The envelope is
therefore kept as data with provenance recorded (video IDs, windows, measurement date), cheap to
re-measure.

---

## 7. Out of scope

- Motion of any kind — the reference has none; adding it is a regression.
- Remotion / Node toolchain — evaluated and rejected; libass supplies the typography that was its
  main remaining advantage, and its animation capability answers a need the data disproved.
- Background reuse — expressible via `image_key` indirection, deferred pending a keying spike.
- Paid image providers — Agnes only, per user constraint.
- Cost instrumentation, thumbnail/title packaging, upload, analytics loop — separate passes.

## 8. Sources

- `context/research/2026-08-01/01-code-gap-audit.md` — pipeline audit
- `context/research/2026-08-01/02-axen-market-packaging.md` — title/thumbnail grammar, cohort data
- `context/research/2026-08-01/03-animation-tooling.md` — tooling survey (headline recommendation
  superseded by forensics; render-speed and licence findings stand)
- `context/research/2026-08-01/04-video-forensics.md` — motion taxonomy, style envelope
- `context/research/2026-08-01/05-script-craft.md` — script skeleton, rubric thresholds
- NexLev channel data verified 2026-08-02; Remotion licence verified against
  `remotion-dev/remotion/LICENSE.md`; overlay benchmark run locally on M2, 2026-08-02
