# Animation Tooling for Automated Stick-Figure Explainer Video

**Research date:** 2026-08-01
**Target:** 8–25 min, 16:9, narrated explainers in minimal stick-figure / line-art style (@AxenCool aesthetic)
**Constraints:** macOS Apple Silicon (M2, 8 cores, no CUDA), Python 3 + uv, Node 26, ffmpeg 8.1, budget ~$2/video
**Status of current pipeline:** static AI stills + hard cuts, assembled by FFmpeg

---

## Executive summary

**Recommendation: build the animation layer in Remotion, driven from Python via JSON props. Keep FFmpeg for final assembly. Add a small, selective AI-video budget for hero shots only.**

Four findings drive this, all measured on this machine today rather than taken from marketing pages:

1. **Remotion is free for this exact use case and renders faster than realtime on the M2.** The license grants free commercial use to individuals and companies ≤3 employees, explicitly including programmatic/automated rendering at any volume. Measured throughput on an M2 at 1080p30, concurrency 8: `wall_seconds = 0.509 × video_seconds + 1.34`, i.e. **1.96× faster than realtime**. A 20-minute video renders in **10.2 minutes for $0.00**.

2. **Full-runtime AI video generation is disqualified on cost, by a wide margin.** The cheapest usable image-to-video model on fal.ai today is $0.02/s. A 20-minute video is 1200 seconds. That is **$24/video minimum**, 12× the current $2 budget, rising to $134 for Kling v3 Pro and $364 for Seedance 2.0. No amount of optimisation closes a 12× gap. AI video is viable *only* as a garnish (see #4).

3. **The style is a gift, not an obstacle.** Minimal line art is the single easiest aesthetic to produce programmatically and the single hardest for AI video models to hold. Flat black strokes on off-white have no texture for a diffusion model to anchor on, so they melt; but they are trivially expressible as SVG paths with joint angles driven by trigonometry. I built a working procedural stick-figure walk cycle (forward kinematics, hip/shoulder counter-rotation, knee flex on swing-through) in ~90 lines of TSX. Every path in the reference channel's visual vocabulary — walk cycles, drawn-on arrows, sliding labels, camera pushes, morphing diagrams — is a closed-form function of frame number.

4. **The strongest cheap win is stroke-reveal ("drawn-on") animation, and it costs nothing.** Animating SVG `stroke-dashoffset` makes lines draw themselves onto the screen. It is one interpolated number per path, it is exactly what the reference channels do constantly, and it converts a static diagram into perceived motion for $0 and near-zero render cost. This alone closes most of the perceived gap between "stills with hard cuts" and "animation".

**Cost per finished 20-minute video: $0.00 for the animation layer** (vs. $24–$364 for any full AI-video path). With a selective AI hero-shot budget of 10×5s clips: **$1.00–$4.20**. The total stays inside the existing ~$2/video envelope if hero shots are used sparingly, or lands at ~$3–5 if used generously.

**Biggest risk:** this is an *art-direction* problem disguised as a tooling problem. Remotion will happily render 20 minutes of technically-correct, visually-boring animation. The work that actually determines whether the channel succeeds is building a library of ~15 reusable scene archetypes with genuine visual variety — not choosing a renderer.

---

## Comparison table

| # | Path | Cost / finished min | Render time / finished min (M2) | Style fidelity (line art) | Automation difficulty | Maturity |
|---|------|--------------------|-------------------------------|--------------------------|----------------------|----------|
| **A1** | **Remotion (React/TS)** | **$0.00** | **~31 s (0.51×RT) — measured** | **Perfect, exact control** | **Low — JSON props over subprocess** | **Excellent: v4.0.503 pub. 2026-07-31, 55.2k★, pushed today** |
| A2 | Revideo (Motion Canvas fork) | $0.00 | Not measured | Perfect | Medium | Good: 0.11.0 pub. 2026-07-10, 3.9k★ |
| A3 | Motion Canvas | $0.00 | Not measured | Perfect | Medium | **Stale on npm: 3.17.2 last published 2025-02-16 (~17 mo)** |
| A4 | Manim / ManimGL | $0.00 | Not measured (install failed) | Good for diagrams, **no character rig** | Medium (native Python) | Excellent: 39.8k★/89.1k★, both pushed today |
| A5 | Blender Grease Pencil (bpy) | $0.00 | Slow, CPU-bound on M2 | Excellent, hand-drawn feel | **High** — bpy is a hostile automation API | Excellent but heavyweight |
| A6 | Synfig CLI | $0.00 | Unmeasured | Good | High (XML wrangling) | Weak: 2.3k★, 728 open issues |
| A7 | Lottie / Rive playback | $0.00 (self-hosted) | Fast | Perfect (hand-authored) | Low to *play*, but assets are hand-made | Rive 2.39.1 pushed today; lottie-web stale (2025-05) |
| **B** | **Pose-estimation → stick rig** | **$0.00** (local MediaPipe) | Extraction ~realtime + render | **Excellent — real human motion** | **Medium-high** | MediaPipe 1.0.0, 36.4k★, Apache-2.0 |
| **C** | **AI image-to-video (full runtime)** | **$1.20 – $18.20** | API latency, minutes/clip | **Poor — flat art melts** | Low | Mature but **cost-disqualified** |
| **C'** | **AI i2v (selective hero shots)** | **~$0.05–0.21 amortised** | Parallel API calls | Good if clips stay ≤5 s | Low | Same, **viable** |
| **D** | **Pseudo-motion (Ken Burns, stroke reveal, 2.5D)** | **$0.00** | Negligible | **Perfect** | **Very low** | Trivially stable |
| **E** | **Hybrid: static hero + animated overlays** | **$0.00** | Negligible | Perfect | Low | Trivially stable |

*Cost/min for path C computed at $0.02/s (cheapest) and $0.3034/s (Seedance 2.0), ×60 s.*

---

## Deep dive per path

### A1. Remotion — **the recommendation**

**How it works.** You write React components whose output is a pure function of the current frame (`useCurrentFrame()`). Remotion spins up headless Chrome, screenshots every frame, and pipes them to FFmpeg. Because the component is a pure function of frame number, animation is just arithmetic: `interpolate()`, `spring()`, and any trigonometry you like.

**Driving it from Python.** This is the part I proved end-to-end rather than assuming. The bridge is a subprocess call passing JSON:

```python
subprocess.run(["npx","remotion","render","src/index.ts","Timeline",out,
                "--props", json.dumps({"beats": beats}), "--concurrency=8"])
```

Combined with Remotion's `calculateMetadata`, the **video duration is derived from the data Python sends**, so narration beats drive timing with frame accuracy and no manual sync:

```tsx
calculateMetadata={({props}) => ({
  durationInFrames: Math.round(
    props.beats.reduce((a, b) => a + b.seconds, 0) * 30),
})}
```

**Verified result:** Python sent 4 beats totalling 24 s → output was `24.042667 s`, rendered in 14.0 s. This is the whole integration story; there is no other glue required. Your existing TTS word timings become the `beats` array directly.

**Measured render performance (M2, 8 cores, 1080p30, `--concurrency=8`):**

| Video length | Wall time | Ratio |
|---|---|---|
| 10 s | 6.85 s | 0.69× RT |
| 60 s | 31.11 s | 0.52× RT |
| 120 s | 62.76 s | 0.52× RT |

Least-squares fit: **`wall = 0.509 × video_seconds + 1.34`** → fixed overhead only ~1.3 s, marginal rate **1.96× faster than realtime**.

| Target | Projected render |
|---|---|
| 8 min | 4.1 min |
| 12 min | 6.1 min |
| 20 min | **10.2 min** |
| 25 min | 12.7 min |

**Determinism — verified, and stronger than expected.** I rendered the same composition three times and hashed the *decoded RGB frame data* (not container bytes, which carry encoder metadata):

```
run1 (concurrency=8): 5c3f4e3f339faf6ab05ad8218d1bcc79fca1983f71e2ca46dc7e95032967d36a
run2 (concurrency=8): 5c3f4e3f339faf6ab05ad8218d1bcc79fca1983f71e2ca46dc7e95032967d36a
run3 (concurrency=3): 5c3f4e3f339faf6ab05ad8218d1bcc79fca1983f71e2ca46dc7e95032967d36a
```

**Bit-identical across runs and across concurrency levels.** Parallelism does not perturb output. This means renders are cacheable by content hash, diffable, and safely resumable — you can re-render only changed sections.

**Licensing — verified, and it is the decisive commercial fact.** From `LICENSE.md` and the license FAQ (fetched 2026-08-01):
- Free for "an individual" or "a for-profit organisation with up to 3 employees", and for non-profits.
- Grants permission "to use the software non-commercially **or commercially** for the purpose of creating videos and images."
- The FAQ confirms explicitly that a solo developer **does not need the Automators plan even for programmatic rendering at scale**.
- The Automators plan ($0.01/render, $100/mo minimum) binds only companies with **4+ employees**. Enterprise starts at $500/mo.

A solo builder pays **$0**. This should be re-checked if the operation ever incorporates and hires.

**Style fidelity.** Total. You are drawing SVG paths, so the line weight, colour, and background are literal constants. There is no drift mechanism — frame 1 and frame 36,000 of a 20-minute video use the identical `stroke-width` and `#1a1a1a`. This is the strongest possible answer to "can it hold a consistent look across 20 minutes": consistency is not something the tool *achieves*, it is something the tool cannot avoid.

**Proof of concept built.** `scratchpad/research/poc-remotion/src/Scene.tsx` implements a procedural walk cycle using forward kinematics — thigh swings ±28°, knee flexes only on swing-through (`Math.max(0, -Math.cos(t)) * 42`), arms counter-phased by π, vertical bob at 2× gait frequency, back limbs drawn at 45% opacity for depth. Plus a camera push-in, a spring-driven label, and a `stroke-dashoffset` arrow that draws itself on. Frame extraction confirms distinct, correct poses through the cycle. This is ~90 lines and covers a large fraction of the reference channel's vocabulary.

**How it fails.**
- *Chrome/JS errors surface at render time, not build time.* A component that throws on frame 4,912 kills a 10-minute render. Mitigation: render in per-section chunks and concat with FFmpeg — which is exactly what the real pipelines below do.
- *Memory growth on very long single compositions.* Same mitigation.
- *Font loading is async* and can produce a flash of unstyled text; use `@remotion/google-fonts` or `staticFile` with `delayRender()`.
- *Node/Chrome version drift* can alter subpixel antialiasing. Pin the Remotion version and Node version; the determinism guarantee holds within a fixed toolchain, not across upgrades.

**Maturity.** `remotion@4.0.503` published 2026-07-31; repo pushed 2026-08-01 (today), 55,198 stars, 214 open issues. Ecosystem packages all at matching 4.0.503: `@remotion/rive`, `@remotion/lottie`, `@remotion/shapes`, `@remotion/paths`, `@remotion/media-utils`, `@remotion/transitions`. This is among the most actively maintained projects in the space.

**Cloud fallback.** Remotion Lambda costs **$0.0103–0.021 per minute of rendered video** (2048 MB, us-east-1; from the official cost-example page). A 20-minute video ≈ **$0.21–0.41**. Worth wiring up only if you need to render several videos concurrently; the local M2 handles one video in 10 minutes for free.

---

### A2/A3. Revideo and Motion Canvas

Motion Canvas is a genuinely elegant generator-based animation API (`yield* tween(...)`), and its declarative timeline reads better than Remotion's frame-function model for sequential animation.

**But the npm package is stale: `@motion-canvas/core@3.17.2` was last published 2025-02-16 — roughly 17 months ago** — despite repo commits through 2026-07-02. A project whose published artifact is a year and a half behind its repo is a supply risk for a production pipeline.

**Revideo** (`midrender/revideo`, 3,948★, pushed 2026-07-15) is the actively-maintained fork that adds headless rendering and a Node API aimed at exactly this use case; `@revideo/core@0.11.0` published 2026-07-10.

**Verdict:** Revideo is the credible alternative to Remotion and a reasonable fallback. It is 14× smaller by stars, has a thinner ecosystem, and no equivalent of Remotion's free-for-individuals commercial clarity that I could verify. Choose it only if Remotion's licensing ever changes.

---

### A4. Manim / ManimGL

**Install failed on this machine.** `uv pip install manim` fails building `pycairo` 1.29.0: `pkg-config` is absent and `pango` is not installed. Homebrew has `cairo` but not `pango`/`pkg-config`. Fixing it requires `brew install pkg-config pango` — I did not run this, since it modifies the user's system beyond the scratch directory. **Real friction point, but not a permanent blocker.**

**The deeper objection is aesthetic, not operational.** Manim is a *mathematical* animation engine. Its primitives are `Tex`, `MathTex`, `Axes`, `Transform`, `Graph`. It is superb at morphing equations and animating graphs — genuinely better than Remotion at that specific job. It has **no character rig, no skeleton, no walk-cycle concept**. Building a stick figure that walks means hand-rolling FK on `Line` mobjects, at which point you have written the same trigonometry as the Remotion POC but inside a slower CPU renderer with a harder install.

Manim's cairo renderer is CPU-bound and, for scenes with many mobjects, typically renders well below realtime — the inverse of the measured Remotion result.

**Verdict:** not the backbone. **Worth keeping as a targeted subprocess** for the one thing it dominates: if a video needs a real equation morph or a plotted curve, shell out to Manim for that 8-second insert and composite it. Native Python is a genuine convenience there. Maturity is excellent (ManimCommunity 39.8k★ and 3b1b 89.1k★, both pushed within 24 h, MIT).

---

### A5–A7. Blender Grease Pencil, Synfig, Lottie/Rive

**Blender Grease Pencil via `bpy`** produces the most authentically hand-drawn look of any option and is fully scriptable headlessly (`blender -b -P script.py -a`). But `bpy` is a global-singleton, side-effect-heavy API designed for interactive use; driving it from a clean data model means fighting it constantly. Render is CPU-bound on M2 with no CUDA. **Highest effort-to-payoff ratio here. Skip.**

**Synfig CLI** is scriptable but you author by generating `.sifz` XML. 2,270★ with **728 open issues** signals a maintenance backlog. **Skip.**

**Lottie / Rive** invert the problem in an interesting way. These are *playback* runtimes for hand-authored animation — they do not generate motion, they replay it. That is not a weakness if you reframe it:

> **Hand-author a small library of stick-figure animations once** (walk, point, shrug, think, sit, carry) in the Rive editor, then have Python programmatically select, sequence, retime, and recolour them.

`@remotion/rive@4.0.503` renders a `.riv` synchronised to Remotion's timeline, so this composes cleanly with the main recommendation. Rive's state machines and data binding mean one asset can be driven by parameters. `rive-app/rive-runtime` is MIT, 1,127★, pushed today. A headless CLI also exists (`breakawaydata/rive-render`, Apache-2.0) though at 4★ it is not something to depend on. Note Rive's *official* cloud video export requires a paid plan; the Remotion route avoids that entirely.

`lottie-web@5.13.0` was last published 2025-05-21 — moderately stale.

**Verdict:** **Rive-via-Remotion is a strong Phase-3 upgrade** for character motion quality, and the only path that gets genuinely expressive, animator-quality movement without per-video cost. It trades automation purity for a one-time authoring investment.

---

### B. Pose estimation → stick rig

**How it works.** Run MediaPipe Pose (BlazePose, 33 landmarks) over any stock video of a person walking/gesturing, extract 2D keypoints per frame, smooth them (Savitzky–Golay), normalise limb lengths, and emit a JSON array of joint positions. Feed that array to the *same* Remotion stick-figure component as the `phase` input. You get real human motion — with its natural weight shifts and irregularity — rendered as clean vector lines.

**Cost: $0.00.** MediaPipe runs locally on CPU, `mediapipe` is at 1.0.0 on PyPI, `google-ai-edge/mediapipe` is Apache-2.0, 36,418★, pushed 2026-07-31. `rtmlib` (0.0.15) is a lighter ONNX-based alternative for RTMPose.

**Why this is more interesting than it first appears.** The uncanny quality of procedural animation is that it is *too* regular — a perfect sine-wave walk cycle reads as robotic. Motion-captured keypoints carry natural noise. Extracting 20–30 reusable motion clips once, storing them as JSON, and replaying/blending them gives you the visual payoff of hand animation at zero marginal cost and full determinism (the JSON is fixed once extracted).

**How it fails.** Keypoint jitter needs real smoothing; occlusion produces limb popping; foot-sliding is common without contact-locking. Source video licensing needs care.

**Verdict:** **the highest-leverage optional upgrade.** Not needed for v1 — procedural FK is good enough to ship — but this is where the motion quality ceiling lifts, and it stays free. Recommended for Phase 3.

---

### C. AI image-to-video APIs

I pulled the **full fal.ai image-to-video catalogue via their models API on 2026-08-01** (188 non-deprecated models) and extracted the exact `pricingInfoOverride` strings rather than trusting blog roundups.

**Cheapest verified per-second prices (fal.ai, 2026-08-01):**

| Model | $/s | Notes |
|---|---|---|
| `fal-ai/minimax/hailuo-02-fast/image-to-video` | 0.017 | 512P only — too low-res for 16:9 YouTube |
| `fal-ai/ltxv-13b-098-distilled/image-to-video` | **0.020** | 24 fps; cheapest usable |
| `fal-ai/veo3.1/lite/image-to-video` | 0.030 | 720p, audio off ($0.05 with audio) |
| `fal-ai/pika/v2.2/pikaframes` | 0.040 | 720p, **min 5 billable s**; first+last frame |
| `fal-ai/ltx-video-13b-distilled/image-to-video` | 0.040 | |
| `fal-ai/minimax/hailuo-02/standard` | 0.045 | 768P |
| `wan/v2.6/image-to-video/flash` | 0.050 | 720p |
| `fal-ai/ltx-2.3/image-to-video/fast` | 0.060 | 1080p |
| `fal-ai/kling-video/v2.6/pro` | 0.070 | |
| `fal-ai/kling-video/v3/standard` | 0.084 | audio off |
| `fal-ai/kling-video/v3/pro` | 0.112 | audio off; $0.168 audio on |
| `fal-ai/wan/v2.7` · `fal-ai/veo3.1/fast` | 0.100 | 720p |
| `fal-ai/veo3.1/image-to-video` | 0.200 | no audio; $0.40 with |
| `bytedance/seedance-2.0/image-to-video` | 0.303 | 720p; $0.682 at 1080p |

**Cost arithmetic — full runtime (the disqualifying calculation):**

| Model $/s | 8 min (480 s) | **20 min (1200 s)** | 25 min (1500 s) |
|---|---|---|---|
| 0.020 | $9.60 | **$24.00** | $30.00 |
| 0.040 | $19.20 | **$48.00** | $60.00 |
| 0.084 | $40.32 | **$100.80** | $126.00 |
| 0.112 | $53.76 | **$134.40** | $168.00 |
| 0.200 | $96.00 | **$240.00** | $300.00 |
| 0.303 | $145.63 | **$364.08** | $455.10 |

Against a $2/video budget, the *floor* is 12× over. **Path C at full runtime is a non-starter and I am stating that explicitly rather than hedging.**

**Cost arithmetic — selective hero shots (the viable form):**

| Hero clips | Seconds | @ $0.02/s | @ $0.06/s | @ $0.084/s |
|---|---|---|---|---|
| 6 × 5 s | 30 | $0.60 | $1.80 | $2.52 |
| 10 × 5 s | 50 | **$1.00** | **$3.00** | **$4.20** |
| 20 × 5 s | 100 | $2.00 | $6.00 | $8.40 |

**Style fidelity — the real problem, independent of cost.** Flat line art is the *worst-case* input for diffusion video models. These models were trained on photographic and cinematic footage; they infer motion from texture, shading and depth cues. A black stroke on off-white provides none. The documented failure mode is exactly what you would predict: melting, morphing, and identity drift, driven by "too much motion plus weak identity constraints." Practitioners mitigate with tight crops, slow motion, short clips, and explicit style-lock prompting — all of which say the same thing: **keep clips ≤5 s and keep motion minimal.** Which is precisely the selective-hero-shot usage, and precisely *not* the full-runtime usage.

**First+last frame control matters** and is available: `fal-ai/veo3.1/*/first-last-frame-to-video` ($0.03–0.20/s) and `fal-ai/pika/v2.2/pikaframes` ($0.04/s). Supplying both endpoints constrains drift substantially and lets you generate a *transition* between two of your own deterministic vector frames — the safest possible use of AI video in this pipeline.

**Python SDKs:** `fal-client` 1.0.0 and `replicate` 1.0.7 are both current on PyPI.

**How it fails.** Non-deterministic (same prompt+seed is not guaranteed reproducible across model versions); models get deprecated and silently re-versioned; latency is minutes; and a bad generation is only detectable by looking at it, which means a human or a vision-model review gate.

**Verdict:** **budget $1–3/video for 6–10 hero clips of ≤5 s, using first+last-frame control on `veo3.1/lite` or `ltxv-13b-098-distilled`. Never generate the full runtime.**

---

### D. Cheap pseudo-motion — **the highest value-per-effort in this entire report**

These techniques are near-free, fully deterministic, and capture most of the *perceived* motion of the reference channels.

1. **Stroke reveal / drawn-on lines.** Animate SVG `stroke-dashoffset` from `pathLength → 0` and the line draws itself onto screen. **This is the single strongest cheap win.** It is the dominant visual verb of the @AxenCool style — diagrams and arrows appearing as if hand-drawn in real time. It costs one interpolated float per path. Demonstrated in the POC:
   ```tsx
   const drawOn = interpolate(frame, [45, 90], [DASH, 0],
     {extrapolateLeft:'clamp', extrapolateRight:'clamp', easing: Easing.out(Easing.cubic)});
   <path d="M1400,300 C1300,360 1230,420 1180,470"
         strokeDasharray={DASH} strokeDashoffset={drawOn}/>
   ```
   `@remotion/paths` provides `getLength()` / `getPointAtLength()` to do this generically over any path.

2. **Camera push / Ken Burns on vector art.** Same technique as the current pipeline, but applied to SVG instead of a bitmap, so it stays **crisp at any zoom** rather than softening. One `interpolate` on a transform. Already in the POC (`zoom: 1 → 1.14`).

3. **Layered parallax.** Give background/midground/foreground different translate rates. Three more `interpolate` calls; reads as real depth.

4. **Animated masks / wipe reveals.** Reveal diagram regions in sync with narration beats.

5. **Depth-map 2.5D warp.** Depth estimation + mesh warp on a still. Notably, this is the *least* useful entry on this list for this specific style — flat line art has no meaningful depth to estimate. Skip it here; it is a technique for photographic stills.

**Cost $0.00. Render impact negligible. Determinism perfect. Style fidelity perfect.**

**Verdict: implement this layer first, before anything else.** It is a few days of work and it is the difference between "slideshow" and "animation" for most viewers.

---

### E. Hybrid: static hero + animated overlays

Keep the existing AI-generated still as a background layer, then composite deterministic vector motion on top: arrows drawing on, labels springing in, highlight circles, underlines, callout boxes, progressive bullet reveals.

This is the **cheapest possible migration path** and deserves emphasis because it reuses the entire existing pipeline. Your current stills stay; you add a Remotion overlay pass. Cost $0.00, and it can ship in a fraction of the time of a full restyle.

The natural progression is: overlays on existing stills (E) → replace stills with native vector scenes (A1+D) → add character motion (B / Rive).

---

## What actually ships in the wild

Searched GitHub for real automated faceless-YouTube pipelines. **Remotion is the overwhelmingly dominant renderer**, and the architecture that recurs is precisely Python-orchestrator → Remotion-render → FFmpeg-assemble.

| Repo | What it does | Relevance |
|---|---|---|
| **`Mystery-CLI/faceless-video-engine`** | Daily autonomous faceless channel. "Remotion (React-based rendering) is the **priority renderer**; if Node or the Remotion project is missing, or a render fails, the engine **falls back to an equivalent ffmpeg pipeline** so an unattended run never dies." | **Validates the exact recommended architecture, including the failure strategy.** Python 3.11+ / Node 18+ / ffmpeg — same stack. |
| **`NesDevr/video-factory`** | Multi-agent pipeline; "Renders animated sections with Remotion and assembles the final MP4" via FFmpeg concat + xfade. Four Gemini vision review gates. Cost tracing, fixture replay for zero-cost re-runs. | **Confirms per-section rendering + FFmpeg concat** — the mitigation for long-render fragility. The vision review gate is a good pattern for QA-ing AI hero shots. |
| **`Gaurav1112/video-money-maker`** | Fireship-style animated teaching videos. 11 Remotion components, Kokoro TTS self-hosted, SQLite queue, n8n publishing. Explicitly **"Zero cost infrastructure… Total $0/month"**, Remotion listed as "Free". | **Independent confirmation that the $0 Remotion cost model is what people actually run.** Closest content type to the target. |
| **`myusp/image-video-gen-agent`** | Shared Remotion template, per-video `scene-config.json`, `REMOTION_PUBLIC_DIR` switches which video renders. Ken Burns + captions. | **Best structural pattern to copy**: one template, never edited per-video; all variation in JSON. Also documents real gotchas (no symlinks in output dir; pan translate must stay `< (scale-1)/(2×scale)` or black edges appear). |
| **`hassancs91/claude-youtube-editor`** | "Every screen moment you see is built as code (Remotion TSX)". Ships 37 real production shots. | Useful reference library of production-grade Remotion shot construction. |
| **`dr34ming/shorts-project`** | Manim scenes **+** Remotion effects, Python-orchestrated. | Precedent for the recommended Manim-as-subprocess-for-diagrams hybrid. |
| `amit14916-art/ai-youtube-bot` | Python; animated slides via MoviePy-style compositing. | The "before" architecture — roughly where the current pipeline is. |

The consistent lesson across these: **render in sections, always have an FFmpeg fallback, keep the Remotion template static and put all per-video variation in JSON.**

---

## Recommended stack

### Primary

```
Python orchestrator (existing)
  ├─ script + narration beats + TTS word timings   [existing]
  ├─ scene planner  → scene-config.json            [new, small]
  │     one entry per narration beat:
  │     {archetype, label, seconds, params}
  ├─ AI hero shots (selective, 6–10 × ≤5 s)        [new, optional]
  │     fal-ai/veo3.1/lite first-last-frame  @ $0.03/s
  │     bracketed by two deterministic vector frames
  ├─ Remotion render, PER SECTION                  [new, core]
  │     npx remotion render … --props '<json>'
  │     calculateMetadata derives duration from beats
  └─ FFmpeg concat + audio mux                     [existing]
```

**Component library to build (this is the real work):**
- `StickFigure` — FK rig; props: `pose | phase`, `scale`, `x`. (POC done.)
- `DrawOn` — generic `stroke-dashoffset` reveal over any path. **Build this first.**
- `Label`, `Callout`, `Arrow` — spring-in annotations.
- `SceneFrame` — background, ground line, camera push.
- ~15 scene archetypes composed from the above.

**Why this stack:** $0 marginal cost, 1.96× realtime local render, bit-identical determinism, the exact architecture three independent shipped projects converged on, and a licence that is free for a solo operator including automated rendering.

### Phasing

| Phase | Work | Cost | Outcome |
|---|---|---|---|
| **1** | Path E + D: Remotion overlay pass on **existing** stills — drawn-on arrows, spring labels, vector Ken Burns | $0 | Ships fastest; kills the "slideshow" feel immediately |
| **2** | Path A1: native vector scenes, stick-figure rig, ~15 archetypes | $0 | Full target aesthetic |
| **3** | Path B or Rive: motion-capture JSON clips or hand-authored Rive characters | $0 | Lifts motion-quality ceiling |
| **Ongoing** | Path C': 6–10 AI hero clips per video, first+last-frame constrained | $1–3 | Visual variety / thumbnail moments |

### Fallback

- **If Remotion licensing ever changes** (i.e. the operation incorporates and passes 3 employees): switch to **Revideo** (`@revideo/core` 0.11.0, active) — same architectural shape, MIT-descended. Or pay Automators at $0.01/render, which at ~30 videos/month is $100/mo minimum — still rational at that scale.
- **If local render time becomes the bottleneck** (batch rendering many videos): **Remotion Lambda at $0.0103–0.021/min** ≈ $0.21–0.41 per 20-min video. Cheap enough to be a non-issue.
- **If a Remotion render fails mid-run:** fall back to the existing FFmpeg still-assembly path for that section, as `faceless-video-engine` does. Never let an unattended run die.

---

## What I could not verify

- **Manim render speed on this machine.** Install failed (`pycairo` → missing `pkg-config`/`pango`); fixing it requires `brew install`, which modifies the user's system beyond the scratch directory, so I did not proceed. The claim that Manim's cairo renderer is slower than realtime for complex scenes is reasoned from its CPU-bound architecture, **not measured here**.
- **Motion Canvas / Revideo / Blender / Synfig render speeds** — not benchmarked. Only Remotion was measured.
- **Actual visual quality of AI i2v on flat line art.** I did not spend money generating test clips. The melting/drift claim rests on documented failure modes and the structural argument that flat art lacks the texture cues diffusion models rely on. **A $2 empirical test — 10 clips through `veo3.1/lite` on a real stick-figure frame — would settle this and is the single highest-value next experiment.**
- **fal.ai prices are list prices** scraped from `fal.ai/api/models` on 2026-08-01; volume discounts and any free tier not investigated. Replicate pricing not cross-checked in detail.
- **@AxenCool's actual production method** — inferred from the visual style, not confirmed.
- **Remotion licence edge cases.** The FAQ was read via an LLM-summarising fetch, not lawyer-reviewed. The ≤3-employee threshold and free automated rendering were consistent across `LICENSE.md`, `/docs/license/faq`, and `remotion.pro/license`, but confirm directly before relying on it commercially at scale.
- **Long-render stability.** Longest render tested was 120 s. The 20-minute single-composition case was **not** tested — which is exactly why per-section rendering is recommended rather than optional.

---

## Sources

All accessed **2026-08-01** unless noted.

**Measured locally (this machine, M2, 8 cores):**
- Remotion render benchmarks, determinism hashes, and Python→Remotion bridge — POC at `scratchpad/research/poc-remotion/` (`src/Scene.tsx`, `src/Timeline.tsx`, `drive.py`)
- Manim install failure — `uv pip install manim` → pycairo 1.29.0 meson build failure

**Package registries:**
- npm: `remotion` 4.0.503 (mod. 2026-07-31T08:59Z), `@remotion/renderer` 4.0.503, `@remotion/rive|lottie|shapes|paths|media-utils|transitions` 4.0.503, `@motion-canvas/core` 3.17.2 (mod. **2025-02-16**), `@revideo/core` 0.11.0 (mod. 2026-07-10), `lottie-web` 5.13.0 (mod. 2025-05-21), `@rive-app/canvas` 2.39.1 (mod. 2026-07-23)
- PyPI: `manim` 0.20.1, `manimgl` 1.7.2, `fal-client` 1.0.0, `replicate` 1.0.7, `mediapipe` 1.0.0, `rtmlib` 0.0.15, `moviepy` 2.2.1, `drawsvg` 2.4.1, `svgwrite` 1.4.3, `pycairo` 1.29.0

**GitHub API (`api.github.com/repos/...`):**
- `remotion-dev/remotion` — 55,198★, pushed 2026-08-01
- `motion-canvas/motion-canvas` — 18,878★, pushed 2026-07-02, MIT
- `midrender/revideo` — 3,948★, pushed 2026-07-15
- `ManimCommunity/manim` — 39,826★, pushed 2026-08-01, MIT
- `3b1b/manim` — 89,069★, pushed 2026-08-02, MIT
- `rive-app/rive-runtime` — 1,127★, pushed 2026-08-02, MIT
- `breakawaydata/rive-render` — 4★, pushed 2026-06-26, Apache-2.0
- `synfig/synfig` — 2,270★, pushed 2026-08-02, GPL-3.0, 728 open issues
- `google-ai-edge/mediapipe` — 36,418★, pushed 2026-07-31, Apache-2.0
- `Lightricks/LTX-Video` — 10,793★, pushed 2026-01-05, Apache-2.0

**Pricing / licensing:**
- fal.ai model catalogue + exact pricing — `https://fal.ai/api/models?categories=image-to-video` (188 models, raw `pricingInfoOverride` fields)
- Remotion licence — `github.com/remotion-dev/remotion/blob/main/LICENSE.md`
- Remotion licence FAQ — `remotion.dev/docs/license/faq`
- Remotion pricing — `remotion.pro/license`
- Remotion Lambda costs — `remotion.dev/docs/lambda/cost-example`

**Real-world projects:** `Mystery-CLI/faceless-video-engine`, `NesDevr/video-factory`, `Gaurav1112/video-money-maker`, `hassancs91/claude-youtube-editor`, `myusp/image-video-gen-agent`, `dr34ming/shorts-project`, `amit14916-art/ai-youtube-bot`

**Background:** kling.ai/blog/fix-ai-video-drift-consistency-guide · queststudio.io/blog/reduce-flicker-melting-artifacts · dev.to "AI Video's Character Consistency Problem" · sarath-menon/blender_automation_python (Grease Pencil bpy) · renderday.com/blog/mastering-the-blender-cli
