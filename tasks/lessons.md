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

