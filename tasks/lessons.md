# Lessons

## 2026-07-07 — The real visual target is the local `assets/refs` stills, not abstract style words
**Correction:** The user explicitly pointed to `assets/refs` as the image standard and asked for the
Agnes prompts to be rebuilt from those frames. The old prompt still sounded like a generic
"minimalist educational-explainer" style, which is too vague and too polished.
**Rule:** When prompting Agnes, describe the concrete visual grammar from the reference stills:
low-budget hand-drawn marker-cartoon frame, thick uneven black outlines, wobbly linework, flat fill
colors, plain pale backgrounds, lots of empty space, white round-headed stick people with dot eyes and
tiny line mouths, noodle limbs, crude flat clothing/hair add-ons, and simple props/diagrams. Avoid
cinematic/realistic/ornate/detail words in BOTH the style wrapper and GPT-OSS image_prompt
instructions; those words overpower the stick-figure style and make Agnes drift.

## 2026-07-02 — Provider retry must cover NETWORK exceptions, not just HTTP status codes
**Correction:** A 43-frame Agnes render failed at scene 5 with `httpx` "Server disconnected without
sending a response." The provider only retried on 429/5xx *status codes*, so a transport-level
exception (RemoteProtocolError/ConnectError/timeout) propagated and killed the whole run.
**Rule:** Any provider hitting a flaky third-party API over a long, many-call run must wrap the request
in `try/except httpx.RequestError` and retry those too (backoff), alongside 429 (honour `Retry-After`)
and 5xx. Long runs (dozens/hundreds of calls) make a transient disconnect near-certain — one un-retried
blip must not abort the batch. Bump the retry budget for long runs; consider an optional min-interval
throttle to stay under RPM.

## 2026-06-27 — Separate shared infra from domain logic when scoping a pivot
**Correction:** When proposing the Shorts pivot (D2), I framed it as "reuse ~70% of the engine,"
which lumped *discovery* in with infrastructure. The user clarified: shared **infra** (env keys, the
rate-limited LLM client, Redis, MinIO/S3, Postgres, control plane) stays the same, but **context +
discovery can be a completely new engine**.
**Rule:** For any pivot/refactor, explicitly split two tiers — (1) **shared infrastructure** (config,
LLM access, queue, storage, DB, control plane, generic media) which is reused verbatim, and (2)
**domain/business logic** (here: discovery/selection) which is free to be rebuilt clean-room. Don't
let "reuse the engine" force domain assumptions from the old product into the new one. Preserve the
old logic in `legacy/`, port ideas not flow.

## 2026-06-27 — Verify the premise with real data before designing
**Pattern:** The brief assumed RankZilla was a "ranking/#1-reveal" channel; real recon showed it's a
single-hook machine (96% identical title). Pulling genuine data first (yt-dlp flat-playlist) prevented
designing the wrong system. Always ground reverse-engineering in observed data; mark modeled vs observed.

## 2026-06-27 — The goal is YouTube Shorts; stop defaulting to Twitch
**Correction:** I repeatedly proposed running Twitch discovery / labeling Twitch candidates as the
next step (e.g., to make `/eval` produce a verdict). The user pushed back: the project goal is the
autonomous **YouTube Shorts** business; **Twitch is legacy/decommission-only**, not a workflow to run.
**Rule:** Frame every "next step" around the **active spec** (now `context/project/`), never around an
abandoned/legacy engine. Don't route progress back through legacy code (Twitch, reranking). When blocked,
solve it within the active direction or name the real blocker. See [[titan-project-goal]].
(Update 2026-06-27: niche later settled on faceless AI-history; old Twitch/RankZilla code deleted, tagged.)

## 2026-07-03 — Parse ONE JSON value from LLM output; ignore trailing junk
**Correction:** A run failed at script-gen with `json.decoder.JSONDecodeError: Extra data (char 15415)`.
`parse_json_block` sliced `first "{"` … `last "}"` then `json.loads`-ed the whole slice — but the local
model appended a second object / commentary after the storyboard, so the slice spanned valid JSON + junk.
**Rule:** When extracting a JSON object from LLM text, use `json.JSONDecoder().raw_decode()` from the
first `{` (parses exactly one complete value, ignores anything trailing) instead of a greedy
`{`…`}` slice. Add a `not isinstance(obj, dict)` guard. Local models routinely emit extra prose/objects.

## 2026-07-03 — On-screen fact text: keep images text-free; don't PIL-overlay it either
**Correction:** I first built key-fact emphasis (numbers/dates/names) as a **crisp PIL overlay** composited
by FFmpeg (the diffusion model garbles digits, so overlay = legible). The user then rejected the PIL look
outright: "i dont like the PIL renders … if the accuracy for text of the diffusion model are that bad its
better not to do it." So BOTH channels are out — no PIL stat-cards, no diffusion-drawn text.
**Rule:** Keep every generated image **text-free** (`NO_TEXT` guardrail); let the **narration + subtitles**
carry the facts. Only purely *symbolic, wordless* emphasis (question mark, hourglass) may be drawn in-scene.
Don't add a text-overlay layer without the user's taste sign-off — a technically-correct legibility fix can
still be the wrong aesthetic. Show a sample and confirm the *look* before building the pipeline around it.

## 2026-07-03 — Resume must reuse saved narration + spans, not just skip frames
**Pattern:** Frame-level resume (`if resume and target.is_file(): continue`) already reused images, but
`render_storyboard` still re-ran `build_narration` every resume — a fresh Cartesia call (cost) whose new
timings could desync the reused frames.
**Rule:** Persist per-beat spans to `beat_spans.json` on first synth; on `--resume`, if `narration.wav` +
spans exist (and span count == scene count), load them and SKIP `build_narration` entirely. Also record a
truthful `resume_note` in the manifest ("N/M frames on disk — continuing at scene X") so the dashboard
shows real progress instead of looking like a fresh start.

## 2026-07-03 — Callout overlay: transparent black text on the image's whitespace (not a black box)
**Correction:** The first key-fact overlay used white text on a black semi-transparent panel; the user
rejected the "black background put over images." They want the callout on an EMPTY patch of the actual
image, black text, transparent bg, in the Schoolbell (Google Fonts, OFL) handwritten font — falling
back to a soft white card only when there's no clean whitespace.
**Rule:** For on-image text overlays, detect whitespace (`_pick_callout_zone`: score candidate zones by
brightness − roughness, skip the subtitle band + dead-center) and composite black text with a thin
white halo there; card fallback only when no zone is clean. Show the user a rendered sample and get a
taste sign-off before building — this callout has now flipped 3× (build → remove → rebuild restyled).

## 2026-07-03 — "Main character energy" on Agnes must come from a TEXT-described protagonist
**(SUPERSEDED 2026-07-04: the user disliked the forced recurring protagonist — `CHARACTER_IDENTITY`
and the scarf were REMOVED; characters are now generic + consistent only. Keep the underlying insight
that ref images don't reach Agnes t2i, but do NOT reintroduce a named/scarf lead.)**
**Pattern:** The character prompt said "use the SAME character shown in the reference image," but Agnes
text-to-image never receives the reference PNG (refs only reach Gemini) — so every character beat
re-invented a generic stick figure, giving the video no consistent lead.
**Rule:** Pin one distinctive recurring protagonist in the prompt TEXT (`CHARACTER_IDENTITY` in
`studio/style.py`: a signature trait like a muted-teal scarf), used on every character/wide shot, so a
ref-less t2i model still draws the same character. Reserve character/wide for the protagonist's real
moments; concept/map stay people-free to kill filler stickmen.

## 2026-07-04 — All on-screen text is PIL-only; the model is never asked for text
**Correction:** Agnes sometimes drew garbled text into frames. The user wants a STRICT guardrail: the
only text on screen comes from the PIL layers (subtitles via make_caption_png + callouts via
make_emphasis_png), never the diffusion model.
**Rule:** Keep `NO_TEXT` maximal ("absolutely no text, no words, letters, numbers, signs, labels…") and
append it on EVERY image-prompt path in `styled_prompt` (character/wide/concept/map + refs + thumbnail)
— a test asserts this for every shot_type. Never inject callout/fact text into an image_prompt. A prompt
can't force the model 100%; the only hard gate is OCR detect-and-regenerate (opt-in, not built yet).

## 2026-07-04 — Callout word choice: a separate gpt-oss pass, favour names + hard numbers
**Pattern:** Picking the on-screen callout inline while writing the script gave filler and missed proper
names (e.g. a person's name). A dedicated 2nd pass over the finished beats fixed it — on a real script it
chose 'Frank "Lucky" Tower', 'Titanic 1912', 'Empress of Ireland', '18 minutes' and rejected filler.
**Rule:** For "pick the important words" tasks, run a focused post-hoc LLM pass (`CALLOUT_ANALYSIS_
SYSTEM_PROMPT`) with explicit criteria — prefer PROPER NAMES + hard numbers/dates, reject vague words,
must appear in the source text (no invention), sparse (~1 in 5). Same pass can flag "intense" beats for
extra frames. Degrade gracefully (no callouts) if the pass fails.
**(Art-style note SUPERSEDED 2026-07-04 — see below: the channel moved from ligne claire back to a
refined stick-figure look for consistency + fewer errors.)**

## 2026-07-04 — Place on-image text by scanning for whitespace, not a handful of fixed zones
**Correction:** The callout still landed on the subject sometimes. The old `_pick_callout_zone` scored
only 5 fixed candidate boxes (top thirds + side margins) and demanded near-white (mean>218); when the
subject filled those boxes or the "whitespace" was a flat *muted* sky (not near-white), nothing
qualified and it fell back to a centered default → text over the figure.
**Rule:** For "put text on the empty part of an image," do a real **flatness scan**: slide the text box
across the whole usable area (above the subtitle band) and score every position by local variance using
an **integral image / summed-area table** (O(1) mean+std per window). Flatness (low std) is the primary
signal — NOT whiteness — so text lands on any uncluttered region (muted sky, plain wall), wherever it
is in *this* frame. Verify empirically: composite the callout over several real generated frames and
eyeball it (did it on cave/torch/cave-wall/night-sky samples — all landed on genuine whitespace).
Keep a std ceiling so a fully-busy frame returns None (caller uses a default spot).

## 2026-07-04 — A "locked" aesthetic can be re-opened; optimise for consistency + low error rate
**Correction:** Style had been "locked to ligne claire" after a bake-off. The user reversed it back to a
**refined stick-figure** look (round white head, thin black stick body, minimal face, serious explainer
tone — Axen-style), because that design is *easiest to keep on-model across ~60 images and least likely
to garble anatomy/hands/text*.
**Rule:** Don't treat a locked visual decision as permanent. For a faceless pipeline generating dozens of
frames per video, cross-frame **consistency + low failure rate** often beats a "nicer" but more complex
look — a simpler design is a feature, not a downgrade. When the user shows a reference frame + a written
spec, follow the spec literally in `LOCKED_STYLE`/`CONCEPT_STYLE` and update the stale lesson.

## 2026-07-04 — Tolerate PARTIAL beats from the LLM: drop the bad one, keep the run
**Correction:** A run died at `storyboard_from_dict` with `KeyError: 'image_prompt'` — the local
gpt-oss model emitted one scene missing a required key, and the parser indexed keys directly
(`s["image_prompt"]`, `s["narration"]`, `data["title"]`), so a single malformed beat aborted the whole
run *after* research + script-gen had already been spent. Same failure class as the JSON `raw_decode`
fix: local models routinely emit *structurally-fine-but-content-incomplete* output.
**Rule:** At the parse boundary, validate each item and **skip** the unrenderable ones (a beat needs BOTH
`narration` and `image_prompt`; also guard non-dict entries) rather than hard-indexing — keep the rest,
warn to stderr (never silently swallow — surface "skipped N malformed beats"), and only fail loudly if
NOTHING usable survives. Default optional top-level fields (`title`) instead of `KeyError`-ing. One bad
beat in a 45-beat script must not throw away the whole (paid) run. See [[content-hash-cache-pattern]].

## 2026-07-04 — Picking up work another agent started: read the CURRENT file state first
**Correction:** The user ran a parallel Antigravity session that edited `studio_poc.py`, `style.py`,
`script_prompt.py`, `run_log.py`, `tests/` on top of my uncommitted work — including doing several of
my pending asks (removed the stick-figure nose, added irregular hand-drawn line-work, per-scene
clothing variation) and a `pending_approval()` stub. I nearly re-implemented things already done.
**Rule:** When told another agent/session touched the repo, re-read the current files BEFORE editing —
`git status`/`git log`, then read the actual functions. The Read tool may serve a STALE cached copy
("wasted call — unchanged"); force fresh content with an `offset`/`limit` read or `grep`. Build ON their
changes, don't clobber. Confirm which asks are already satisfied instead of duplicating them.

## 2026-07-04 — HITL gate: split a long detached pipeline into phases behind the run lock
**Pattern:** The user wanted human review — generate all images, then assemble ONLY after approval,
with per-image regenerate. The pipeline was one detached subprocess (research→script→images→assemble).
**Rule:** To pause a detached pipeline for approval, don't block the process — SPLIT it into phases that
each run as their own short subprocess behind the existing single-run lock: (1) generate → call
`rec.pending_approval()` and EXIT (frees the lock, dashboard shows the images); (2) a `/approve`
endpoint spawns an **assemble-only** pass that reuses the on-disk narration + frames; (3) a `/regenerate`
endpoint re-draws one scene's frame(s) and stays in `pending_approval`. Critical enabler: a
`RunRecorder.load()` that RE-OPENS the existing manifest — `create()` resets `run.json`, which would
wipe the scenes/callouts a follow-up phase must preserve. Verified the gate offline (placeholder + `say`):
`--review` stops at `pending_approval` with no video; `--assemble-only` then produces it + `completed`.

## 2026-07-06 — Two-sided style scoping (people-free concepts / stickman humans) + a real model limit
**Correction:** Stickmen were leaking into concept shots, and some humans still rendered detailed.
Fixes that WORKED (verified on real Agnes frames): (1) concept/map — lead with "empty scene, objects &
scenery only, NO people/stick figures" + a hardened `NO_PEOPLE` negative; (2) character/wide — add an
explicit `NO_REALISTIC_HUMANS` negative incl. anti-photorealism ("flat 2D cartoon, NOT a photo/3D").
Crowds now render ALL stickmen; normal characters (toga, fur, braids) stay stickmen.
**Rule + honest limit:** Prompt guards can't fully beat a strong subject. (a) Leading a character prompt
with a long "draw as a stick figure" PREAMBLE backfired — an ornate subject ("golden-armored emperor")
went PHOTOREALISTIC with a circle head. Keep character prompts subject-first + trailing negatives; add
an explicit no-photo clause. (b) Ornate/ARMORED focal subjects (breastplate, throne) resist stick-figure
rendering in Agnes t2i no matter the prompt — a genuine model limitation. The real lever is the SCRIPT:
instruct it to describe appearance with ONE-TWO SIMPLE markers, "never ornate/detailed," because an
over-described outfit makes the model draw a realistic person. Residual bad frames → the HITL regenerate
gate. Don't burn many API renders chasing one pathological subject once the common cases are solid.

## 2026-07-05 — Rich subject detail overrides a minimal style; force the constraint for the FOCAL subject
**Correction:** With a goofy-stickman `LOCKED_STYLE`, undescribed background people rendered as stick
figures and animals as normal cartoons (both correct) — but the FOCAL human, once described with rich
cultural detail ("a Viking with long braided hair + fur cloak"), rendered as a DETAILED realistic
person. The appearance detail out-weighed the minimal style for the subject the model focused on.
**Rule:** A style string that works for simple subjects can be overpowered when the per-scene subject is
detailed. Make the constraint explicit and DOMINANT for every subject, and say HOW detail attaches:
"EVERY person is a stick figure — blank round head + stick body; show culture/era ONLY as simple hair
and clothing added ON the stick figure (long braided hair on the round head, a fur cloak on the stick
body); never a detailed/realistic human." That kept Viking/Egyptian/caveman as stick figures WEARING
accurate cultural hair+dress while animals stayed normal cartoons. Scope selectively: "ONLY humans are
stick figures; animals, objects and background are normal cartoons (not stick figures)." Verified on
real Agnes renders (the only way to catch this — the constraint gap is invisible in the prompt text).

## 2026-07-05 — When a user keeps rejecting a style, they usually want it SIMPLER/cruder, not more refined
**Correction:** After "wobbly sketchy" (rejected) and a polished clean-Axen cartoon (rejected), the user
snapped: "it should be a GOOFY stickman style, is that so hard?" My prompts kept adding *richness* (cream
heads, hair/beard, furnished rooms, "clean/refined/explainer," "serious not comedic") — pulling AWAY from
what they wanted. The fix was to STRIP it down and push the opposite adjectives: goofy, crude, minimal,
silly, comedic, exaggerated; plain blank round head, dot eyes, one big squiggle mouth, noodly stick
limbs, plain flat background. That rendered as an obvious goofy stickman and landed.
**Rule:** Repeated style rejection ≠ "add more detail / polish." It usually means "too much" — go
CRUDER and SIMPLER, and lead with the vibe word the user used (goofy/silly/crude) over craft words
(clean/refined/detailed). Flip "serious" ↔ "comedic" to match their tone. Always confirm with a real
render (never claim a look from the prompt alone). Grounding in reference frames is good, but the user's
taste can be goofier/simpler than the reference — their word wins.

## 2026-07-04 — Ground a style prompt in REAL reference frames; "hand-drawn" ≠ "sketchy scribble"
**Correction:** The art style read as messy/scribbly. Root cause: the prompt said "wobbly pencil/ink
textures, irregular sketchy hand-drawn ink outlines" — which pushes a pencil-scribble look. Downloading
the actual Axen reference video (`yt-dlp` → `ffmpeg` frame extract into gitignored
`result/axen/style_refs/…`) and READING the frames showed the true look: **clean, confident, SOLID
black outlines** (only a *subtle* hand-drawn quality), round off-white heads, simple faces (no nose),
thin solid limbs, flat warm muted colors, lightly-furnished backgrounds. The organic/rough quality
lives ONLY in hair/beard texture — not the main linework.
**Rule:** Don't write a visual-style prompt from imagination — pull real reference frames first and
match them literally. "Hand-drawn / minimalist" is ambiguous: be explicit that outlines are CLEAN and
SOLID (not sketchy/pencil) unless the frames actually show scribble. VERIFY by rendering a few frames
(one per shot_type: character, map, concept) with the real provider and eyeballing them side-by-side
against the reference — the offline placeholder can't show style. Keep the prompt-doc mirror
(`prompts/02`, `prompts/04`) and the ref-sheet generator (`tools/make_refs.py`) in sync with
`studio/style.py`. Verified: 3 Agnes frames matched Axen's frame_004 / frame_095 / frame_03.

## 2026-07-04 — Time an on-screen callout to its SPOKEN moment (estimate, land on/before the word)
**Correction:** The key-fact PIL callout showed for the WHOLE beat; the user wants it to appear when
its phrase is actually spoken. We have per-beat Cartesia spans but not per-word times.
**Rule:** Estimate the phrase's spoken moment the way the rest of the pipeline estimates in-beat timing
— **proportionally to text length** (like `align_beats` / `captions.cue_timings`): find the phrase's
character offset in the beat narration, scale by beat duration, then subtract a small **lead** (~0.3s)
so it lands **on or before** the word (the user's tolerance). Clamp `start` to `[beat_start,
beat_end − min_hold]` so it stays readable and never precedes its beat; hold to beat end. Phrase not
found → beat_start (safe). Keep the change in the pure `emphasis_timeline` (thread `narrations` in);
downstream (`set_callouts`, dashboard "Planned callouts") picks up the new time for free. Verified:
"Tsushima" at char 62/70 of a 20s beat → callout at 17.4s (was 0.0s for the whole beat).

## 2026-07-04 — Content-policy 400s need a PROMPT retry (soften), not a backoff retry
**Correction:** Agnes killed a run with `400 content_policy_violation` ("modify your prompt"). The
provider only retried 429/5xx/network (backoff) — useless here: re-POSTing the SAME prompt is blocked
again deterministically. A history channel trips this constantly (death, weapons, blood).
**Rule:** Detect the content-policy block distinctly (`is_content_policy_error`: 400 + code/message)
and retry with a **softened prompt**, not a delay: neutralise graphic words → mild symbolic synonyms
(`soften_prompt`, escalating levels; append "mild, non-graphic, family-friendly, no blood/gore/weapons"),
then drop them, then a blunt safe framing. Try the original + ~3 softened variants before failing; keep
the RPM/5xx backoff loop separate (two different retry axes). Deliberately DON'T neuter ordinary words
(war/battle/attack) — that flattens every video. Raise a typed `ContentPolicyError` (RuntimeError
subclass) so the render loop's fallback-provider path still catches it. Pure logic in `studio/agnes.py`
(tested); the side-effecting variant loop in `AgnesImageProvider`.

## 2026-07-04 — Enforce callout sparsity as a render-time guardrail, not just in the prompt
**Correction:** "Only ~2-3 callouts per 1.5 min" — but relying on the analysis prompt ("~1 in 5") let
clusters through. **Rule:** Cap density where the real timeline lives (`emphasis_timeline`, which has the
beat spans): greedily enforce a **minimum gap** (~35s) between kept callouts — a hard guardrail
independent of how many the LLM proposes — AND tell the model to be sparse. Compute the surviving set
ONCE, then drive both the rendered overlays and the dashboard badges/plan from it so they always match.

## 2026-07-06 — Beat cuts must anchor to REAL word timings, not character-proportion
**Bug (user):** "the timing of the video and the display of images is off by a lot." Measured against
real Cartesia timestamps: the old `align_beats` (distribute audio by each beat's CHARACTER count, then
snap to a nearby pause) drifted the image cuts up to **3.5s AHEAD** of the narration through the whole
middle of a 4-min video (21/45 beats off ≥1.5s), then snapped back. Character proportion is a poor
proxy — speech rate isn't uniform beat to beat.
**Rule:** When the TTS returns per-word timestamps (Cartesia `add_timestamps`), capture the `words`
array too (not just `start`/`end`) and ANCHOR each beat's end to the actual spoken word where its
narration text runs out (`align_beats_to_words`): walk the spoken-word stream, hand words to each beat
until its normalised-char budget is spent, cut at that word's real end time. Drift → **0.00s** (verified
on real audio). Robust to number expansion ("35,000"→"thirty five thousand") via a per-beat re-anchor +
a "leave ≥1 word per remaining beat" starvation guard. Keep the proportional `align_beats` only as the
fallback for voices with no word text (offline `say`). Don't throw away signal you already fetched.
**Verify tip:** to quantify alignment drift without a full render, replay ONE Cartesia call, cache the
word arrays to disk, and diff algorithm-boundaries vs word-anchored "truth" offline (free iteration).

## 2026-07-07 — "UI change not showing" = the dashboard server cached HTML at import
**Bug (user):** "I still can't see all the images for the fire/hotspots." The code + data were correct
(run.json had frame_count=2 on the intense beats, img_i_1.png existed on disk, the API returned it, the
sceneCard JS rendered both frames). The real cause: `dashboard/app.py` read `INDEX_HTML =
Path(...).read_text()` ONCE at import, so the long-running uvicorn process (started ~2h before the
fire-spot frontend was written) kept serving the STALE index.html — the served HTML had 0 occurrences
of `frame_count`. A restart would "fix" it, masking the footgun.
**Rule:** For a local dev dashboard, DON'T cache templates at import — read the HTML fresh per request
(`INDEX_HTML_PATH.read_text()` inside the route). The file is tiny; the per-request read is free and
edits show up with no restart. When a user says "my UI change isn't showing," first check whether a
server process predates the file edit (`ps -o lstart` vs file mtime) and diff the SERVED bytes
(`curl / | grep token`) against disk before hunting for a logic bug. Verify the data path end-to-end
(disk → API JSON → rendered DOM) rather than re-reading the component.

## 2026-07-29 — Grounding that is *instructed* but never *verified* is not grounding
**Bug (review of the Exa→LLM script path):** `SCRIPT_SYSTEM_PROMPT` says "use ONLY facts from the
RESEARCH BRIEF… NEVER invent" and "never read citations aloud". Both rules were prompt-only, so both
failed silently in production. Measured on the 13 shipped runs: `the-sailor-who-survived-three-
different-shipwrecks` is a 44-beat script citing **3 of 54** sources with 34 uncited beats — it
rendered end to end with no warning. And `chinese-boys-in-the-1800s` had `[2][5]` inline in 16 of 45
narration beats, which Cartesia read aloud to the viewer.
**Rule:** any prompt rule whose violation is expensive (paid render) or audible (TTS) needs a
deterministic check in code, placed at the last boundary before the cost is incurred. Concretely:
(1) a **grounding gate** (`studio.research.grounding_report`) runs in `build_and_save` next to the
existing word-count check — *before* any image/TTS spend — and raises below a source floor or a
citation-coverage floor; (2) `strip_citation_markers` runs in `storyboard_from_dict`, the one
boundary every render path funnels through, so storyboards already on disk are fixed too, with
stripped indices folded back into `cite` so provenance is never lost.
**Also:** untrusted fetched text is *data, not instructions* — whitespace-normalise every field
(6 of 604 real Exa titles carry embedded newlines that broke the `[n] title/url/snippet` contract and
could forge a fake source), fence it (`<research_brief>`), and say so in the system prompt.
**Verify tip:** calibrate a new gate against the real corpus on disk before shipping it. Replaying all
13 runs showed it refuses exactly the one broken run, flags 3 as thin, and passes 9 — proof it catches
the failure without blocking good work. A threshold you haven't replayed is a guess.

## 2026-08-03 — Script-craft rubric was calibrated to the wrong pole; the corpus wasn't even on disk
**Bug (self-caught during Task 2.2 calibration):** `studio/script_rubric.py`'s `MAX_MEAN_SENTENCE_WORDS
= 17.0` came from the LONG-FORM Mack/Stickly envelope (§13 of `05-script-craft.md` splits this check
**≤17.0w long-form / ≤15.0w short-form**). This channel targets 6-9 min (`make_script.py`
`--min-minutes 6.0 --max-minutes 9.0`, matching `context/project/roadmap.md`'s "ONE full ~7-min video
matching Axen's structure") — i.e. the SHORT-FORM Axen/ThenFolk pole, not Mack's 22-min pole. Every
measured Axen/ThenFolk winner's mean sentence tops out at 13.9w (Axen 635K); 17.0 was loose enough to
let bloated short-form prose through undetected.
**Also found:** no transcript/script corpus was actually on disk in this worktree — `result/axen/
scripts/` and `result/axen/poc/runs/` are gitignored generated output, present only in the main
checkout (not shared across git worktrees). Ran `tools/calibrate_rubric.py` against the main checkout's
real 13 generated scripts via absolute path (read-only, no copy) instead of inventing fixtures.
**Rule:** when a corpus a plan references isn't on disk in an isolated worktree, check whether it's
gitignored local output that exists in the main checkout before concluding "no corpus" — read it via
absolute path rather than copying it in or fabricating substitute data.
**Calibration outcome (fix: `MAX_MEAN_SENTENCE_WORDS` 17.0 → 15.0; all other constants unchanged
after replay):**
- All 5 Axen/ThenFolk winners (3.05M, 1.0M, 635K, 144K, 138K) pass every dimension at the new
  threshold — the governing rule ("if a threshold rejects a 996K/3.05M-view winner, the threshold is
  wrong") holds.
- Both Mack same-cohort underperformers (31K, 24K) and Axen's 11K underperformer still fail, as before.
- Axen's 9.4K underperformer — the one case a narrow sentence-length-only replay would call a false
  negative — is independently caught by the (unchanged) `MIN_2P_AFTER_90S_PER_1K=8.0` check: its
  published post-90s second-person density is 6.4/1k (§13 validation line), below the 8.0 floor. Not a
  threshold I tuned to catch it — it already failed on a different, pre-existing dimension.
- Mack's two 22-min winners (1.6M, 316K) now fail the recalibrated mean-sentence check (16.3w, 15.9w >
  15.0w) — an accepted tradeoff since this pipeline only ever generates short-form scripts.
- Honest baseline: replaying the pipeline's own 13 real generated scripts (main checkout, gitignored)
  scores **0/13 pass** — same 0/13 at the old 17.0 threshold, so the recalibration didn't cause the
  failures. Real defects: 8 of 13 have no question mark anywhere or ask it past 145s (max allowed 45s);
  most also fall below the numbers/1k and 2p-after-90s floors. The gate is doing real work.
**Verify tip:** when a fixture in a plan snippet is too short to reach the metric's measurement window
(here: a toy ~150-word "winner" can never cross the 294-word/90-second mark the retention check needs),
the test fails for a structural reason unrelated to content quality — extend the fixture to a realistic
length rather than loosening the check it's supposed to exercise.

---

## 2026-08-09 — An enumeration in an image prompt is read as a checklist, not a menu

**What happened.** Rewriting `LOCKED_STYLE` against the reference frames, I listed the seven
environments the reference uses and the six diagram marks it uses. The very next probe came back
with **all of them in every frame**: a cave AND a snowfield AND a forest AND a river AND an earth
cross-section, each stamped with a red `?`, a red `✗`, orange squiggles and blue arrows. Six of six.

Then I did it twice more, one level up each time:

1. Removed the lists but left `"Draw ONLY the marks the subject asks for and no others."`
   Marks still appeared on frames whose subject requested none — *mentioning* marks summons marks.
2. Replaced the figure cap with `"…never more than three. When there are two or three, one stands
   near and large while the others are small…"` Frames came back with two or three people. The
   clause describing the multi-person case is what produced multiple people.

`LOCKED_STYLE` also said `"EVERY human is a…"` — a plural framing that implies a cast.

**Rule.** In a prompt sent to an image model, treat every noun you write as a request to draw it.
- Never enumerate options. A list of alternatives is rendered as a conjunction.
- Never write a rule *about* a thing you do not want. There is no negation strong enough; the noun
  is what lands. Delete the sentence instead.
- Prefer singular and definite ("the one place named in the subject") over universal-plural
  ("every human", "backgrounds").
- Options belong in the *script writer's* prompt, where one is chosen and named. By the time the
  image prompt is built, the choice should already be a concrete noun in the subject.

**What actually fixed the composition** was not prompt wording at all: it was giving each shot a
single named framing from `studio.framing.plan_framings`, and widening the per-scene subject from
8 words to 20-35 so it names the place and the action. Rounds 1-2 fed the new style the OLD 8-word
subjects and looked worse than the original — the subject, not the style block, is what carries
the picture.

**Residual, unfixed after four probe rounds:** Agnes still adds background crowds to a subject that
says "stands alone". Prompt text has hit diminishing returns here; the next lever is a
post-generation check or reference conditioning, not more words.
