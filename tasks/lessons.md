# Lessons

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

