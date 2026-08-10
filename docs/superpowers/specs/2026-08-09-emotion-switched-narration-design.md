# Emotion-switched narration — design

**Date:** 2026-08-09
**Status:** approved, ready to plan

## Goal

Narrate the charged moments of a script in a different emotional take of the same voice, so a
video is not read in one flat register end to end.

## What makes this possible

Four Cartesia voice ids were supplied. Queried against `/voices/{id}` on 2026-08-09, all four are
the **same speaker, "Carson"**, recorded in four emotional deliveries:

| Name | Cartesia id | Role |
|---|---|---|
| Carson - Curious Conversationalist | `86e30c1d-…` | the narrator (already wired, `studio/voices.py`) |
| Carson - Disgusted Friendly Support | `ee8b13e7-…` | switchable |
| Carson - Angry Friendly Support | `0b32066b-…` | switchable |
| Carson - Surprised Friendly Support | `66f5935b-…` | switchable |

One speaker is the whole premise. Switching between takes changes *delivery*; four unrelated
voices would sound like four people reading one script.

## How often this fires — measured

A keyword lexicon scored every beat of all 13 storyboards in `result/axen/scripts/`:

| script | beats | emotion-tagged |
|---|---|---|
| why-do-empires-always-overreach-and-collapse | 47 | 6 (12.8%) |
| the-man-who-was-struck-by-lightning-seven-times | 45 | 3 (6.7%) |
| titanic | 45 | 2 (4.4%) |
| the-navy-that-sailed-18-000-miles | 39 | 2 (5.1%) |
| chinese-boys-in-the-1800s | 21 | 1 (4.8%) |
| the-great-molasses-flood | 36 | 1 (2.8%) |
| the-story-a-navy-on-one-massive-l | 45 | 1 (2.2%) |
| what-did-ancient-humans-do-at-night | 18 | 1 (5.6%) |
| *5 others* | 20–52 | 0 |

**17 of 500 beats (3.4%). Five of thirteen scripts score zero.**

This number sets the shape of the design. A switch fires roughly **1–3 times per video**, so the
feature is rare punctuation, not continuous colouring — and stitching 2–6 segment boundaries is
tractable where 30 would not be. A video with no charged beats narrates entirely in the narrator
take, which is the correct outcome, not a failure.

The lexicon was a sizing instrument only. The shipped scorer is the LLM (below).

## The two real risks

**Seams.** The pipeline makes ONE Cartesia SSE call for the whole script precisely to get natural
prosody and a continuous word-timestamp stream (`studio/narration.py` module docstring). Every
switch splits that into another call, and Cartesia's intonation contour restarts at each call
boundary.

**Silent desync.** Each call returns timestamps from zero. Shot cuts, captions and callouts all
ride on those arrays. An offsetting error does not crash — it quietly slides the whole video out
of sync.

Both are addressed below. The seam risk is measured *first*, before anything else is built.

## Architecture

Three units, split on this repo's existing purity line.

### `studio/emotion.py` — pure, owns the decision

```python
class VoiceSegment(BaseModel):       # frozen
    voice: str                       # a key of studio.voices.VOICES
    first_beat: int                  # inclusive
    last_beat: int                   # inclusive

def plan_voice_segments(
    emotions: Sequence[str],
    scores: Sequence[float],
    *,
    narrator: str = NARRATOR,
    min_score: float = EMOTION_MIN_SCORE,
    min_gap_beats: int = EMOTION_MIN_GAP_BEATS,
    max_switches: int = EMOTION_MAX_PER_VIDEO,
) -> tuple[VoiceSegment, ...]:
```

Segments are **contiguous and cover every beat**. The narrator is an ordinary segment, not a
special case — which means the single-voice path and the multi-voice path are the same code, and a
script with no charged beats yields exactly one segment.

Algorithm:

1. A beat is a **candidate** when its emotion is a key of `VOICES`, is not the narrator take, and
   its score ≥ `min_score`.
2. Adjacent candidates sharing an emotion merge into one **run**. Two charged beats in a row are
   one moment and must be one call.
3. Runs are ranked by `(score descending, first_beat ascending)` and accepted greedily, skipping
   any run whose first beat is closer than `min_gap_beats` to an already-accepted run, until
   `max_switches` are accepted. Ranking by score rather than position means a weak early moment
   cannot crowd out the strongest one.
4. Accepted runs are re-sorted into beat order and the gaps between them filled with narrator
   segments.

Deterministic: same inputs, same plan. A re-run reproduces the storyboard.

### `tools/make_script.py` — the scorer

The existing focused analysis pass (which already picks callouts and flags `intense`) also returns
`emotion` and `emotion_score` per beat. **No extra API call.** It reads meaning rather than
keywords, so it can catch a dread-heavy beat that uses no dread words — the failure the lexicon
demonstrated on two scripts.

`Scene` (`studio/types.py`) gains:

```python
emotion: str = ""          # "", "disgust", "angry", or "surprise"
emotion_score: float = 0.0 # 0-1 LLM confidence
```

Both default to the inert value, so every existing storyboard on disk keeps loading.

### `tools/studio_poc.py` — the stitcher

`CartesiaTimestampVoice.synthesize` gains a segmented sibling. Per segment: one SSE call with that
segment's voice, accumulate raw PCM, and append the segment's words with each time shifted by the
cumulative duration of all preceding PCM.

**The offset must be derived from the PCM byte count, not from the previous segment's last word
end time.** Audio routinely carries trailing silence after the final word; using the word end
would compress every subsequent segment and accumulate drift across the video.

```
offset_seconds = bytes_written_so_far / 2 / SAMPLE_RATE   # pcm_s16le -> 2 bytes/sample
```

**The invariant that keeps the blast radius small:** the stitched result is shape-identical to
today's single-call result — one wav, one monotonic `(words, starts, ends)` triple. Nothing
downstream learns that segmentation happened.

## Guardrails

| Constant | Value | Rationale |
|---|---|---|
| `EMOTION_MIN_SCORE` | 0.7 | Below this the model is guessing |
| `EMOTION_MIN_GAP_BEATS` | 8 | ≈240 words ≈84s at the measured 172 wpm. Mirrors the existing `CALLOUT_MIN_GAP_SEC = 35.0`, which keeps callouts rare |
| `EMOTION_MAX_PER_VIDEO` | 3 | The measurement says 1–3 is natural; a cap makes it a guarantee rather than a hope |
| segment granularity | whole beats | Beats end on sentence boundaries, so a seam always lands in a real pause |

Every value is a keyword argument on the pure planner, so all four replay over the corpus without
synthesizing anything.

## Failure handling

| Failure | Behaviour |
|---|---|
| An emotion segment fails to synthesize | Retry once **in the narrator voice**, log it, continue. A lost flourish must never cost a 432-second TTS run |
| LLM returns an unknown emotion name | Treated as no emotion. Same quiet degradation as an illegal `framing` |
| LLM returns a non-numeric or out-of-range score | Clamped to `[0, 1]`; unparseable becomes `0.0` (inert) |
| Stitched timestamps inconsistent | **Raise.** Asserted: arrays are equal length, `starts`/`ends` are monotonic non-decreasing across every join, and the final end time is within one frame of the wav's true duration |

The last row is deliberate. Every other failure degrades quietly because the cost of stopping
exceeds the cost of the defect; a desync is the opposite — it is invisible at synthesis time and
ruins the finished video, so it must fail loudly and immediately.

## Testing

**Task 1 de-risks everything else and comes first.** Synthesize one paragraph twice in the *same*
voice — once as a single call, once split at a sentence boundary and stitched — then measure the
discontinuity at the join and listen to it. If same-voice stitching is already audible, no amount
of emotion logic rescues the feature and the fallback is one take per video. Cost: ~30 seconds of
TTS.

Beyond that:

- **L0, pure planner** — threshold, gap, cap, run merging, score-ranked acceptance, unknown names,
  empty input, all-narrator, determinism.
- **L0, stitching** — fake segment outputs; assert exact offsets, monotonicity across joins, and
  that the offset uses PCM length rather than last-word-end (a fixture with trailing silence
  distinguishes the two, and is the whole point of the test).
- **Calibration** — back-fill emotion tags onto the 13 storyboards on disk by running the analysis
  pass over them, then replay `plan_voice_segments` and print which beats would switch in each.
  Thresholds are only fixed once that replay is inspected. Calibrate before enforcing.
- **Integration** — the offline voice path exercises a two-segment plan end to end without paid
  TTS.

## Global constraints

- `studio/` is pure: no file I/O, network, `subprocess`, or `os.environ`. The planner and models
  live there; every Cartesia call lives in `tools/`.
- Frozen pydantic models.
- Line length 100. `uv run ruff check .` clean.
- Voice ids are public and belong in `studio/voices.py`. Only `CARTESIA_API_KEY` is a secret, and
  `.env` contents are never printed or committed.
- Package manager is `uv`.
- The full suite must pass; the count only goes up.

## Out of scope

- Phrase-level or word-level emotion switching. Beats are the unit.
- Any change to `intense`. It buys an extra *image*; emotion changes the *voice*. They will
  correlate, and coupling them would join two unrelated decisions.
- Cross-fading or any audio smoothing at joins. If joins need smoothing, Task 1 will say so and
  that becomes its own decision.
- Emotion affecting image generation.
