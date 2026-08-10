# Emotion-Switched Narration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Narrate the 1–3 most charged beats of a script in a different emotional take of the same
Cartesia speaker, without disturbing the word-timestamp stream everything downstream rides on.

**Architecture:** A pure planner (`studio/emotion.py`) turns per-beat emotion tags into contiguous
voice segments covering every beat. The existing script-analysis pass produces those tags at no
extra API cost. `tools/studio_poc.py` makes one Cartesia SSE call per segment and stitches the PCM
and word timings back into a single wav and a single monotonic timing triple — shape-identical to
today's one-call output, so nothing downstream changes.

**Tech Stack:** Python 3.12, `uv`, pydantic v2 (frozen models), pytest, httpx, Cartesia SSE TTS.

## Global Constraints

Copied verbatim from `docs/superpowers/specs/2026-08-09-emotion-switched-narration-design.md`.

- `studio/` is **pure**: no file I/O, no network, no `subprocess`, no `os.environ`. The planner and
  models live there; every Cartesia call lives in `tools/`.
- Frozen pydantic models (`model_config = ConfigDict(frozen=True)`).
- Line length 100. `uv run ruff check .` must pass.
- Voice ids are public and belong in `studio/voices.py`. Only `CARTESIA_API_KEY` is a secret.
  **Never print, echo, or commit `.env` contents** — reference variable NAMES only.
- Package manager is `uv`. Never `pip install`. Never activate the venv manually.
- The full suite must pass. Baseline is **336 passing**. That number only goes up.
- Commit format: `<type>: <description>`. No attribution trailer.
- `EMOTION_MIN_SCORE = 0.7`, `EMOTION_MIN_GAP_BEATS = 8`, `EMOTION_MAX_PER_VIDEO = 3`.
- Segment granularity is **whole beats**. Never split a beat.
- Timestamp offsets derive from **PCM byte count**, never from the previous segment's last word end.
- Do not modify `studio/script_rubric.py` thresholds.

---

## File Structure

| File | Responsibility |
|---|---|
| `studio/emotion.py` (create) | Pure: `VoiceSegment`, `plan_voice_segments`, `stitch_word_times`, the three constants |
| `tests/test_emotion.py` (create) | Planner + stitching unit tests |
| `studio/types.py` (modify) | `Scene.emotion`, `Scene.emotion_score` |
| `studio/storyboard.py` (modify) | Read both fields from storyboard JSON |
| `studio/script_prompt.py` (modify) | Ask the analysis pass for emotion tags |
| `tools/make_script.py` (modify) | Parse emotion tags into the scene dicts |
| `tools/calibrate_emotion.py` (create) | Replay the planner over the storyboards on disk |
| `tools/studio_poc.py` (modify) | Segmented SSE synthesis + stitching; wire into `build_narration` |

**Ordering:** Task 1 gates everything — if stitching is audible, stop and report. Tasks 2 and 3
touch disjoint files and could run in parallel; Task 4 needs both; Task 5 needs Task 2.

---

### Task 1: Measure whether a stitched seam is audible

This task writes no production code. It answers one question — *does splitting a Cartesia call at
a sentence boundary produce an audible discontinuity?* — because every later task is wasted if the
answer is yes. Roughly 30 seconds of paid TTS.

**Files:**
- Create: `/private/tmp/.../scratchpad/seam_ab.py` (scratch, not committed)
- Create: `context/research/2026-08-09/02-tts-seam-ab.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a GO / NO-GO finding for Tasks 2–5, recorded in the research note.

- [ ] **Step 1: Write the A/B probe**

Use the SAME voice for both arms. This isolates the seam from the emotion change.

```python
import sys, wave
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("/Users/ippu/Documents/projects/ytautomation-fr/.env")
sys.path.insert(0, "/Users/ippu/Documents/projects/ytautomation-fr")
from tools.studio_poc import SAMPLE_RATE, CartesiaTimestampVoice  # noqa: E402

OUT = Path("SCRATCHPAD_DIR"); OUT.mkdir(parents=True, exist_ok=True)
A = ("For ninety-nine percent of human history there was no such thing as a job. "
     "You woke when your body was ready, and the day was yours to fill.")
B = ("Then the grain came, and the grain had to be counted. "
     "Counting is how the day stopped belonging to you.")

v = CartesiaTimestampVoice()
v.synthesize(A + " " + B, OUT / "one_call.wav")
v.synthesize(A, OUT / "seg_a.wav")
v.synthesize(B, OUT / "seg_b.wav")

frames = b""
for name in ("seg_a.wav", "seg_b.wav"):
    with wave.open(str(OUT / name)) as w:
        frames += w.readframes(w.getnframes())
with wave.open(str(OUT / "stitched.wav"), "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SAMPLE_RATE)
    w.writeframes(frames)
print("wrote one_call.wav and stitched.wav")
```

- [ ] **Step 2: Run it**

Run: `uv run python SCRATCHPAD_DIR/seam_ab.py`
Expected: three wavs plus `stitched.wav`.

- [ ] **Step 3: Measure the discontinuity at the join**

```python
import sys, wave
import numpy as np

def rms_around(path, join_s, win=0.05):
    with wave.open(path) as w:
        sr, n = w.getframerate(), w.getnframes()
        a = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
    j, k = int(join_s * sr), int(win * sr)
    before, after = a[max(0, j - k):j], a[j:j + k]
    r = lambda x: float(np.sqrt((x ** 2).mean())) if len(x) else 0.0
    return r(before), r(after)

def dur(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()

OUT = sys.argv[1]
join = dur(f"{OUT}/seg_a.wav")
print(f"join at {join:.3f}s")
for tag, p in (("stitched", f"{OUT}/stitched.wav"), ("one_call", f"{OUT}/one_call.wav")):
    b, a = rms_around(p, join)
    print(f"{tag:9s} rms before {b:8.1f}  after {a:8.1f}  ratio {a / (b + 1e-9):5.2f}")
print(f"duration: one_call {dur(f'{OUT}/one_call.wav'):.2f}s  "
      f"stitched {dur(f'{OUT}/stitched.wav'):.2f}s")
```

- [ ] **Step 4: Listen to both**

Run: `afplay SCRATCHPAD_DIR/one_call.wav && afplay SCRATCHPAD_DIR/stitched.wav`

The measurement is a proxy; the ear is the decision. Note specifically whether the stitched
version has an unnatural pause, a clipped word, or a pitch reset at the join.

- [ ] **Step 5: Record the finding and decide**

Write `context/research/2026-08-09/02-tts-seam-ab.md` with the RMS numbers, both durations, and a
plain verdict sentence. Then:

- **GO** — the seam is inaudible or reads as a normal paragraph pause. Continue to Task 2.
- **NO-GO** — the seam is audible. **Stop the plan and report to the human partner.** Do not start
  Task 2. The fallback (one emotional take chosen per whole video, single call, zero seams) is a
  different design and needs its own approval.

- [ ] **Step 6: Commit the research note**

```bash
git add context/research/2026-08-09/02-tts-seam-ab.md
git commit -m "docs: measure whether a stitched TTS seam is audible"
```

---

### Task 2: The pure segment planner

**Files:**
- Create: `studio/emotion.py`
- Create: `tests/test_emotion.py`
- Modify: `studio/__init__.py` (re-export, following the existing pattern at line 36)

**Interfaces:**
- Consumes: `studio.voices.VOICES` (`dict[str, str]`), `studio.voices.NARRATOR` (`"curious"`).
- Produces, relied on by Tasks 4 and 5:
  - `VoiceSegment` — frozen pydantic model, fields `voice: str`, `first_beat: int`,
    `last_beat: int` (both inclusive), property `beat_count -> int`.
  - `plan_voice_segments(emotions: Sequence[str], scores: Sequence[float], *, narrator: str = NARRATOR, min_score: float = EMOTION_MIN_SCORE, min_gap_beats: int = EMOTION_MIN_GAP_BEATS, max_switches: int = EMOTION_MAX_PER_VIDEO) -> tuple[VoiceSegment, ...]`
  - `stitch_word_times(segments: Sequence[tuple[Sequence[str], Sequence[float], Sequence[float], float]]) -> tuple[list[str], list[float], list[float]]`
  - `EMOTION_MIN_SCORE = 0.7`, `EMOTION_MIN_GAP_BEATS = 8`, `EMOTION_MAX_PER_VIDEO = 3`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emotion.py`:

```python
"""Voice-segment planning and word-timing stitching — both pure."""

from __future__ import annotations

import pytest

from studio.emotion import (
    EMOTION_MAX_PER_VIDEO,
    EMOTION_MIN_GAP_BEATS,
    VoiceSegment,
    plan_voice_segments,
    stitch_word_times,
)
from studio.voices import NARRATOR


def _flat(n, **overrides):
    """n beats of no emotion, with {index: (emotion, score)} overrides."""
    emotions, scores = [""] * n, [0.0] * n
    for i, (emo, sc) in overrides.items():
        emotions[i], scores[i] = emo, sc
    return emotions, scores


def test_no_emotion_yields_one_narrator_segment_covering_everything():
    segs = plan_voice_segments(*_flat(20))
    assert segs == (VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=19),)


def test_segments_are_contiguous_and_cover_every_beat():
    segs = plan_voice_segments(*_flat(30, **{5: ("angry", 0.9), 20: ("surprise", 0.9)}))
    assert segs[0].first_beat == 0
    assert segs[-1].last_beat == 29
    for a, b in zip(segs, segs[1:], strict=False):
        assert b.first_beat == a.last_beat + 1


def test_a_charged_beat_becomes_its_own_segment():
    segs = plan_voice_segments(*_flat(20, **{7: ("disgust", 0.95)}))
    assert [(s.voice, s.first_beat, s.last_beat) for s in segs] == [
        (NARRATOR, 0, 6), ("disgust", 7, 7), (NARRATOR, 8, 19),
    ]


def test_a_score_below_the_threshold_is_ignored():
    assert plan_voice_segments(*_flat(20, **{7: ("angry", 0.69)})) == (
        VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=19),
    )


def test_adjacent_beats_with_the_same_emotion_merge_into_one_segment():
    """Two charged beats in a row are one moment, so they must be ONE call, not two."""
    segs = plan_voice_segments(*_flat(20, **{7: ("angry", 0.9), 8: ("angry", 0.8)}))
    charged = [s for s in segs if s.voice == "angry"]
    assert len(charged) == 1
    assert (charged[0].first_beat, charged[0].last_beat, charged[0].beat_count) == (7, 8, 2)


def test_adjacent_beats_with_DIFFERENT_emotions_do_not_merge_and_the_gap_rule_drops_one():
    segs = plan_voice_segments(*_flat(20, **{7: ("angry", 0.9), 8: ("disgust", 0.8)}))
    assert [s.voice for s in segs if s.voice != NARRATOR] == ["angry"]


def test_switches_closer_than_the_minimum_gap_are_dropped():
    overrides = {5: ("angry", 0.9), 5 + EMOTION_MIN_GAP_BEATS - 1: ("surprise", 0.85)}
    segs = plan_voice_segments(*_flat(40, **overrides))
    assert len([s for s in segs if s.voice != NARRATOR]) == 1


def test_switches_exactly_the_minimum_gap_apart_are_both_kept():
    overrides = {5: ("angry", 0.9), 5 + EMOTION_MIN_GAP_BEATS: ("surprise", 0.85)}
    segs = plan_voice_segments(*_flat(40, **overrides))
    assert len([s for s in segs if s.voice != NARRATOR]) == 2


def test_the_cap_is_never_exceeded():
    overrides = {i * EMOTION_MIN_GAP_BEATS: ("angry", 0.9) for i in range(10)}
    segs = plan_voice_segments(*_flat(100, **overrides))
    assert len([s for s in segs if s.voice != NARRATOR]) == EMOTION_MAX_PER_VIDEO


def test_the_highest_scoring_moments_win_the_cap_not_the_earliest():
    """A weak early beat must not crowd out the strongest moment in the script."""
    overrides = {
        0: ("angry", 0.71), 10: ("angry", 0.72), 20: ("angry", 0.73), 30: ("surprise", 0.99),
    }
    segs = plan_voice_segments(*_flat(60, **overrides))
    charged = [s for s in segs if s.voice != NARRATOR]
    assert len(charged) == EMOTION_MAX_PER_VIDEO
    assert 30 in [s.first_beat for s in charged]


def test_an_unknown_emotion_name_is_ignored_rather_than_raising():
    assert plan_voice_segments(*_flat(20, **{7: ("sarcastic", 0.99)})) == (
        VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=19),
    )


def test_the_narrator_take_is_never_treated_as_a_switch():
    assert plan_voice_segments(*_flat(20, **{7: (NARRATOR, 0.99)})) == (
        VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=19),
    )


def test_a_short_scores_list_degrades_to_no_emotion():
    assert plan_voice_segments(["", "angry", "surprise"], [0.0]) == (
        VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=2),
    )


def test_max_switches_zero_disables_switching_entirely():
    """The kill switch build_narration uses when the narrator is a custom clone rather than one
    of the four Carson takes — switching speakers mid-video is worse than a flat read."""
    segs = plan_voice_segments(*_flat(20, **{7: ("angry", 0.99)}), max_switches=0)
    assert segs == (VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=19),)


def test_empty_input():
    assert plan_voice_segments([], []) == ()


def test_is_deterministic():
    emotions, scores = _flat(40, **{5: ("angry", 0.9), 25: ("disgust", 0.9)})
    assert plan_voice_segments(emotions, scores) == plan_voice_segments(emotions, scores)


def test_segments_are_frozen():
    seg = VoiceSegment(voice=NARRATOR, first_beat=0, last_beat=1)
    with pytest.raises(Exception):
        seg.voice = "angry"


# ── stitching ────────────────────────────────────────────────────────────────
def test_stitching_offsets_by_AUDIO_length_not_by_the_last_word_end():
    """The whole point. Segment one is 10.0s of audio whose last word ends at 8.0s — 2s of
    trailing silence. Offsetting by 8.0 would slide every later word 2s early and the error
    would accumulate across the video."""
    seg1 = (["a", "b"], [0.0, 4.0], [2.0, 8.0], 10.0)
    seg2 = (["c"], [0.0], [3.0], 3.0)
    words, starts, ends = stitch_word_times([seg1, seg2])
    assert words == ["a", "b", "c"]
    assert starts == [0.0, 4.0, 10.0]
    assert ends == [2.0, 8.0, 13.0]


def test_stitching_a_single_segment_changes_nothing():
    words, starts, ends = stitch_word_times([(["a"], [0.5], [1.5], 2.0)])
    assert (words, starts, ends) == (["a"], [0.5], [1.5])


def test_stitched_times_are_monotonic_across_every_join():
    segs = [(["w"], [0.0], [1.0], 2.0)] * 5
    _w, starts, ends = stitch_word_times(segs)
    assert starts == sorted(starts) and ends == sorted(ends)
    assert all(e >= s for s, e in zip(starts, ends, strict=True))


def test_a_segment_with_no_words_still_advances_the_clock():
    """A segment can return audio but no timestamps. Its duration must still offset what follows,
    or everything after it plays early."""
    words, starts, ends = stitch_word_times([([], [], [], 4.0), (["x"], [0.0], [1.0], 2.0)])
    assert (words, starts, ends) == (["x"], [4.0], [5.0])


def test_stitching_nothing():
    assert stitch_word_times([]) == ([], [], [])


def test_mismatched_array_lengths_raise():
    with pytest.raises(ValueError, match="length"):
        stitch_word_times([(["a", "b"], [0.0], [1.0], 2.0)])
```

- [ ] **Step 2: Run the tests to watch them fail**

Run: `uv run pytest tests/test_emotion.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'studio.emotion'`.

- [ ] **Step 3: Write the implementation**

Create `studio/emotion.py`:

```python
"""Which beats get an emotional take, and how the resulting audio is stitched back together.

Pure. Every Cartesia call lives in ``tools/``.

Two jobs that belong together because they are two halves of one invariant: ``plan_voice_segments``
decides where the narration is cut, and ``stitch_word_times`` puts the timing stream back together
so nothing downstream can tell it was ever cut.

Measured 2026-08-09 over the 13 storyboards in ``result/axen/scripts/``: 17 of 500 beats read as
charged (3.4%), so a switch fires 1-3 times in a video. The guardrails below make that a guarantee
rather than an observation — see the design spec for why each value is what it is.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict

from studio.voices import NARRATOR, VOICES

#: Below this the model is guessing, and a guessed emotion is worse than none.
EMOTION_MIN_SCORE = 0.7

#: Minimum beats between two switches. At ~30 words/beat and the measured 172 wpm this is ~84
#: seconds — the same order as ``studio.narration.CALLOUT_MIN_GAP_SEC`` (35.0), which already keeps
#: on-screen callouts feeling rare rather than habitual.
EMOTION_MIN_GAP_BEATS = 8

#: Hard cap per video. The measurement says 1-3 is what the material naturally supports.
EMOTION_MAX_PER_VIDEO = 3


class VoiceSegment(BaseModel):
    """A contiguous run of beats narrated in one voice. Both bounds inclusive."""

    model_config = ConfigDict(frozen=True)

    voice: str  # a key of studio.voices.VOICES
    first_beat: int
    last_beat: int

    @property
    def beat_count(self) -> int:
        return self.last_beat - self.first_beat + 1


#: (emotion, first_beat, last_beat, best_score) while planning.
_Run = tuple[str, int, int, float]


def plan_voice_segments(
    emotions: Sequence[str],
    scores: Sequence[float],
    *,
    narrator: str = NARRATOR,
    min_score: float = EMOTION_MIN_SCORE,
    min_gap_beats: int = EMOTION_MIN_GAP_BEATS,
    max_switches: int = EMOTION_MAX_PER_VIDEO,
) -> tuple[VoiceSegment, ...]:
    """Contiguous voice segments covering beats ``0..len(emotions)-1``.

    The narrator is an ordinary segment rather than a special case, so a script with no charged
    beats yields exactly one segment and the single-voice and multi-voice paths are the same code.

    Deterministic. Unknown emotion names, short ``scores``, and out-of-range values all degrade to
    "no emotion" for that beat rather than raising — a storyboard is model output, and one bad
    token must not cost a run.
    """
    n = len(emotions)
    if n == 0:
        return ()
    runs = _candidate_runs(emotions, scores, narrator, min_score)
    kept = _accept(runs, min_gap_beats, max_switches)
    return _fill(kept, n, narrator)


def _candidate_runs(
    emotions: Sequence[str], scores: Sequence[float], narrator: str, min_score: float
) -> list[_Run]:
    """Adjacent beats sharing an emotion merged into one run, carrying the run's best score."""
    runs: list[_Run] = []
    for i, raw in enumerate(emotions):
        emotion = (raw or "").strip().lower()
        try:
            score = float(scores[i]) if i < len(scores) else 0.0
        except (TypeError, ValueError):
            score = 0.0
        if emotion not in VOICES or emotion == narrator or score < min_score:
            continue
        if runs and runs[-1][0] == emotion and runs[-1][2] == i - 1:
            prev_emotion, first, _last, best = runs[-1]
            runs[-1] = (prev_emotion, first, i, max(best, score))
        else:
            runs.append((emotion, i, i, score))
    return runs


def _too_close(a: _Run, b: _Run, min_gap_beats: int) -> bool:
    """True when fewer than `min_gap_beats` beats separate two runs (or they touch/overlap)."""
    if a[1] > b[2]:
        return a[1] - b[2] < min_gap_beats
    if b[1] > a[2]:
        return b[1] - a[2] < min_gap_beats
    return True


def _accept(runs: Sequence[_Run], min_gap_beats: int, max_switches: int) -> list[_Run]:
    """Strongest runs first, skipping any that crowds one already accepted, up to the cap.

    Ranking by score rather than position is deliberate: a weak early moment must not crowd out the
    strongest moment in the script just because it comes first.
    """
    kept: list[_Run] = []
    for run in sorted(runs, key=lambda r: (-r[3], r[1])):
        if len(kept) >= max_switches:
            break
        if any(_too_close(run, k, min_gap_beats) for k in kept):
            continue
        kept.append(run)
    return sorted(kept, key=lambda r: r[1])


def _fill(kept: Sequence[_Run], n: int, narrator: str) -> tuple[VoiceSegment, ...]:
    """Accepted runs plus narrator segments in the gaps, covering every beat exactly once."""
    segments: list[VoiceSegment] = []
    cursor = 0
    for emotion, first, last, _score in kept:
        if first > cursor:
            segments.append(VoiceSegment(voice=narrator, first_beat=cursor, last_beat=first - 1))
        segments.append(VoiceSegment(voice=emotion, first_beat=first, last_beat=last))
        cursor = last + 1
    if cursor < n:
        segments.append(VoiceSegment(voice=narrator, first_beat=cursor, last_beat=n - 1))
    return tuple(segments)


def stitch_word_times(
    segments: Sequence[tuple[Sequence[str], Sequence[float], Sequence[float], float]],
) -> tuple[list[str], list[float], list[float]]:
    """Concatenate per-segment word timings into one continuous stream.

    Each element is ``(words, starts, ends, audio_seconds)``. ``audio_seconds`` is the DURATION OF
    THAT SEGMENT'S AUDIO — never its last word's end time. Synthesised audio routinely carries
    trailing silence after the final word; offsetting by the word end would pull every later
    segment early and the error would compound across the video, silently desyncing captions and
    every image cut. That distinction is the reason this function exists as its own unit.
    """
    words: list[str] = []
    starts: list[float] = []
    ends: list[float] = []
    offset = 0.0
    for seg_words, seg_starts, seg_ends, audio_seconds in segments:
        if not (len(seg_words) == len(seg_starts) == len(seg_ends)):
            raise ValueError(
                f"segment word/start/end length mismatch: {len(seg_words)}/"
                f"{len(seg_starts)}/{len(seg_ends)}"
            )
        words.extend(str(w) for w in seg_words)
        starts.extend(round(float(s) + offset, 3) for s in seg_starts)
        ends.extend(round(float(e) + offset, 3) for e in seg_ends)
        offset += float(audio_seconds)
    return words, starts, ends
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest tests/test_emotion.py -q`
Expected: PASS, 22 tests.

- [ ] **Step 5: Re-export from the package**

In `studio/__init__.py`, beside the existing `from studio.shots import ...` line, add:

```python
from studio.emotion import VoiceSegment, plan_voice_segments, stitch_word_times
```

and add `"VoiceSegment"`, `"plan_voice_segments"`, `"stitch_word_times"` to `__all__`.

- [ ] **Step 6: Full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 358 passing (336 + 22), ruff clean.

- [ ] **Step 7: Commit**

```bash
git add studio/emotion.py studio/__init__.py tests/test_emotion.py
git commit -m "feat: pure planner for emotion-switched voice segments"
```

---

### Task 3: Tag each beat with an emotion during the existing analysis pass

**Files:**
- Modify: `studio/script_prompt.py:155-183` (`CALLOUT_ANALYSIS_SYSTEM_PROMPT`,
  `build_callout_analysis_user_prompt`)
- Modify: `tools/make_script.py:263-294` (`_apply_callout_analysis`)
- Modify: `studio/types.py` (`Scene`)
- Modify: `studio/storyboard.py:96-106` (the `Scene(...)` construction)
- Test: `tests/test_studio.py`

**Interfaces:**
- Consumes: nothing from Task 2 (the planner takes plain sequences).
- Produces, relied on by Tasks 4 and 5: `Scene.emotion: str` (`""`, `"disgust"`, `"angry"`, or
  `"surprise"`) and `Scene.emotion_score: float` (0.0–1.0), and the same two keys in the saved
  `storyboard.json`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_studio.py`:

```python
def test_scene_carries_an_emotion_tag_defaulting_to_inert():
    from studio.types import Scene

    s = Scene(narration="n", image_prompt="p")
    assert s.emotion == "" and s.emotion_score == 0.0


def test_storyboard_reads_emotion_tags_and_lowercases_them():
    from studio.storyboard import storyboard_from_dict

    sb = storyboard_from_dict({"title": "T", "scenes": [
        {"narration": "a", "image_prompt": "p", "emotion": " Angry ", "emotion_score": 0.9},
        {"narration": "b", "image_prompt": "p"},
    ]})
    assert (sb.scenes[0].emotion, sb.scenes[0].emotion_score) == ("angry", 0.9)
    assert (sb.scenes[1].emotion, sb.scenes[1].emotion_score) == ("", 0.0)


def test_storyboard_clamps_a_score_out_of_range_and_survives_a_junk_one():
    from studio.storyboard import storyboard_from_dict

    sb = storyboard_from_dict({"title": "T", "scenes": [
        {"narration": "a", "image_prompt": "p", "emotion": "angry", "emotion_score": 4.2},
        {"narration": "b", "image_prompt": "p", "emotion": "angry", "emotion_score": "loud"},
        {"narration": "c", "image_prompt": "p", "emotion": "angry", "emotion_score": -1},
    ]})
    assert [s.emotion_score for s in sb.scenes] == [1.0, 0.0, 0.0]


def test_the_analysis_prompt_asks_for_emotion_tags():
    from studio.script_prompt import CALLOUT_ANALYSIS_SYSTEM_PROMPT

    p = CALLOUT_ANALYSIS_SYSTEM_PROMPT.lower()
    assert "emotion" in p
    for take in ("disgust", "angry", "surprise"):
        assert take in p
    assert "emotions" in p  # the output key
```

- [ ] **Step 2: Run them to watch them fail**

Run: `uv run pytest tests/test_studio.py -q -k "emotion"`
Expected: FAIL — `Scene` has no `emotion` field.

- [ ] **Step 3: Add the model fields**

In `studio/types.py`, inside `Scene`, directly below the `framing` field:

```python
    #: Emotional colour for the narration of this beat: "", "disgust", "angry" or "surprise"
    #: (a key of studio.voices.VOICES). Filled by the script analysis pass; whether it actually
    #: changes the voice is decided by studio.emotion.plan_voice_segments.
    emotion: str = ""
    #: 0-1 confidence from that pass. Below studio.emotion.EMOTION_MIN_SCORE it is ignored.
    emotion_score: float = 0.0
```

- [ ] **Step 4: Read them in the storyboard loader**

In `studio/storyboard.py`, add this module-level helper above `storyboard_from_dict`:

```python
def _clamped_score(raw: object) -> float:
    """A 0-1 confidence from model output. Anything unparseable is 0.0 — inert, never a switch."""
    try:
        return max(0.0, min(1.0, float(raw)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
```

and inside the `Scene(...)` construction, directly below the `framing=` line:

```python
                emotion=(s.get("emotion") or "").strip().lower(),
                emotion_score=_clamped_score(s.get("emotion_score")),
```

- [ ] **Step 5: Ask the analysis pass for the tags**

In `studio/script_prompt.py`, replace the `"OUTPUT: ..."` tail of
`CALLOUT_ANALYSIS_SYSTEM_PROMPT` (currently lines 171-172) with:

```python
    "3) EMOTIONS — the narrator can read a beat in one of three extra deliveries: disgust, angry, "
    "or surprise. Tag ONLY the beats where the writing genuinely carries that feeling, and give a "
    "confidence from 0 to 1. Be extremely sparse: most scripts have one or two such beats and many "
    "have none, so returning an empty list is the normal and correct answer. Do not tag a beat "
    "merely because its subject is grim — tag it when reading it aloud in the flat narrator voice "
    "would lose something. Never tag adjacent beats with different emotions.\n\n"
    "OUTPUT: a single strict JSON object, no prose, no markdown fences: "
    '{"callouts": [{"beat": 0, "text": "..."}], "intense": [0, 1], '
    '"emotions": [{"beat": 0, "emotion": "angry", "score": 0.8}]}'
```

- [ ] **Step 6: Parse them in `make_script`**

In `tools/make_script.py::_apply_callout_analysis`, extend the reset loop (currently lines 271-273):

```python
        for s in scenes:  # start clean; the pass owns these fields now
            s["emphasis"] = ""
            s["intense"] = False
            s["emotion"] = ""
            s["emotion_score"] = 0.0
```

and add, directly after the `for i in result.get("intense") or []:` loop and BEFORE
`_boost_intense_beats(scenes)`:

```python
        for e in result.get("emotions") or []:
            i, emotion = e.get("beat"), (e.get("emotion") or "").strip().lower()
            if not (isinstance(i, int) and 0 <= i < len(scenes)) or emotion not in VOICES:
                continue
            try:
                score = max(0.0, min(1.0, float(e.get("score"))))
            except (TypeError, ValueError):
                continue
            scenes[i]["emotion"] = emotion
            scenes[i]["emotion_score"] = score
```

Add `from studio.voices import VOICES` to the imports at the top of `tools/make_script.py`.

- [ ] **Step 7: Run the tests**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 362 passing (358 + 4), ruff clean.

- [ ] **Step 8: Commit**

```bash
git add studio/types.py studio/storyboard.py studio/script_prompt.py tools/make_script.py tests/test_studio.py
git commit -m "feat: tag beats with an emotional take in the script analysis pass"
```

---

### Task 4: Calibrate the thresholds against the scripts on disk

Thresholds that have never been replayed are guesses. This task back-fills real emotion tags onto
the 13 storyboards already in `result/axen/scripts/` and shows exactly which beats would switch.

**Files:**
- Create: `tools/calibrate_emotion.py` (follow the shape of the existing `tools/calibrate_rubric.py`)
- Modify: `docs/superpowers/specs/2026-08-09-emotion-switched-narration-design.md` (record the outcome)

**Interfaces:**
- Consumes: `studio.emotion.plan_voice_segments`, `VoiceSegment`, the three constants (Task 2);
  `Scene.emotion` / `Scene.emotion_score` and the analysis pass (Task 3).
- Produces: a calibration table. No importable API.

- [ ] **Step 1: Write the calibration CLI**

Create `tools/calibrate_emotion.py`:

```python
"""Replay the emotion planner over every storyboard on disk.

A threshold you have not replayed is a guess. This runs the real analysis pass over the scripts in
result/axen/scripts/, caches the tags next to each storyboard, and prints which beats would switch
voice under the current constants -- all without synthesising a second of audio.

Usage:
    uv run python tools/calibrate_emotion.py            # use cached tags where present
    uv run python tools/calibrate_emotion.py --retag    # re-run the LLM pass on every script
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from studio.emotion import (  # noqa: E402
    EMOTION_MAX_PER_VIDEO,
    EMOTION_MIN_GAP_BEATS,
    EMOTION_MIN_SCORE,
    plan_voice_segments,
)
from studio.voices import NARRATOR  # noqa: E402
from tools.make_script import LLMScriptProvider  # noqa: E402

SCRIPTS = _ROOT / "result" / "axen" / "scripts"


def tags_for(sb_path: Path, retag: bool) -> list[dict]:
    """Beat dicts carrying emotion tags, cached beside the storyboard as emotion_tags.json."""
    cache = sb_path.parent / "emotion_tags.json"
    if cache.is_file() and not retag:
        return json.loads(cache.read_text())["scenes"]
    data = json.loads(sb_path.read_text())
    LLMScriptProvider()._apply_callout_analysis(data)
    cache.write_text(json.dumps({"scenes": data["scenes"]}, indent=2))
    return data["scenes"]


def main() -> None:
    load_dotenv(_ROOT / ".env")
    ap = argparse.ArgumentParser()
    ap.add_argument("--retag", action="store_true", help="re-run the LLM pass on every script")
    args = ap.parse_args()

    print(f"min_score={EMOTION_MIN_SCORE} min_gap_beats={EMOTION_MIN_GAP_BEATS} "
          f"max={EMOTION_MAX_PER_VIDEO}\n")
    totals = {"scripts": 0, "with_switch": 0, "switches": 0, "beats": 0}
    for sb_path in sorted(SCRIPTS.glob("*/storyboard.json")):
        scenes = tags_for(sb_path, args.retag)
        emotions = [s.get("emotion", "") for s in scenes]
        scores = [s.get("emotion_score", 0.0) for s in scenes]
        segments = plan_voice_segments(emotions, scores)
        switched = [s for s in segments if s.voice != NARRATOR]
        tagged = sum(1 for e in emotions if e)
        totals["scripts"] += 1
        totals["beats"] += len(scenes)
        totals["switches"] += len(switched)
        totals["with_switch"] += bool(switched)
        detail = ", ".join(f"{s.voice}@{s.first_beat}-{s.last_beat}" for s in switched) or "-"
        print(f"{sb_path.parent.name[:52]:52s} {len(scenes):3d} beats  "
              f"tagged {tagged:2d}  kept {len(switched)}  {detail}")
    print(f"\n{totals['scripts']} scripts, {totals['beats']} beats, "
          f"{totals['switches']} switches, "
          f"{totals['with_switch']}/{totals['scripts']} scripts get at least one")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Run: `uv run python tools/calibrate_emotion.py --retag`
Expected: one line per script, then a summary. Cost: 13 cheap analysis calls.

- [ ] **Step 3: Read the result against the design's prediction**

The spec predicts 1–3 switches per video and some scripts with zero. Check the output against that:

- **Switches per script above 3 anywhere** — impossible, the cap forbids it. If you see it, the
  cap is broken; go back to Task 2.
- **Nearly every script at zero** — `EMOTION_MIN_SCORE` is too high, or the prompt's "be extremely
  sparse" is too strong. Report the numbers; do not silently retune.
- **Nearly every script at the cap of 3** — the pass is over-tagging. Report the numbers.
- **Mostly 0–2, a few at 3** — matches the prediction. Keep the constants.

Do NOT change a threshold to make the output look better without saying so. If you do change one,
re-run and show both tables.

- [ ] **Step 4: Record the outcome in the spec**

Append a `## Calibration outcome (2026-08-09)` section to
`docs/superpowers/specs/2026-08-09-emotion-switched-narration-design.md` with the full table, the
constants used, and one sentence on whether they were kept or changed and why.

- [ ] **Step 5: Commit**

`emotion_tags.json` caches live under `result/`, which is gitignored — do not force-add them.

```bash
git add tools/calibrate_emotion.py docs/superpowers/specs/2026-08-09-emotion-switched-narration-design.md
git commit -m "test: calibrate the emotion thresholds against the scripts on disk"
```

---

### Task 5: Segmented synthesis and stitching

**Files:**
- Modify: `tools/studio_poc.py` — `CartesiaTimestampVoice` (currently around line 495) and
  `build_narration` (currently around line 780)
- Test: `tests/test_emotion_synthesis.py` (create)

**Interfaces:**
- Consumes: `studio.emotion.plan_voice_segments`, `studio.emotion.stitch_word_times`,
  `studio.emotion.VoiceSegment`, `studio.voices.resolve_voice`, `Scene.emotion`,
  `Scene.emotion_score`.
- Produces: `CartesiaTimestampVoice.synthesize_segments(segments: Sequence[tuple[str, str]], out_path: Path) -> tuple[list[str], list[float], list[float]]`
  where each element is `(text, voice_name)`. `build_narration` returns exactly what it returns
  today: `(wav, spans, words, starts, ends)`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_emotion_synthesis.py`:

```python
"""Segmented Cartesia synthesis — stitching, offsets, and the narrator fallback.

No network: `_sse_once` is monkeypatched, which is exactly the seam this task introduces so the
stitching logic is testable without paying for TTS.
"""

from __future__ import annotations

import wave

import pytest

from studio.voices import VOICES
from tools.studio_poc import SAMPLE_RATE, CartesiaTimestampVoice


def _silence(seconds: float) -> bytes:
    return b"\x00\x00" * int(seconds * SAMPLE_RATE)


@pytest.fixture
def fake_sse(monkeypatch):
    """Replace the one network call. Records the voice id used for each segment."""
    calls: list[tuple[str, str]] = []

    def _fake(self, text, voice_id, model, speed):
        calls.append((text, voice_id))
        # 2s of audio, one word ending at 1s -> 1s of trailing silence, so a stitcher that
        # offsets by last-word-end instead of audio length will produce visibly wrong numbers.
        return _silence(2.0), [text.split()[0]], [0.0], [1.0]

    monkeypatch.setattr(CartesiaTimestampVoice, "_sse_once", _fake)
    return calls


def test_two_segments_produce_one_wav_of_the_summed_length(tmp_path, fake_sse):
    out = tmp_path / "n.wav"
    CartesiaTimestampVoice().synthesize_segments(
        [("alpha one", "curious"), ("beta two", "angry")], out
    )
    with wave.open(str(out)) as w:
        assert w.getnframes() / w.getframerate() == pytest.approx(4.0, abs=0.01)
        assert w.getnchannels() == 1 and w.getsampwidth() == 2


def test_the_second_segment_is_offset_by_the_first_segments_AUDIO_length(tmp_path, fake_sse):
    words, starts, ends = CartesiaTimestampVoice().synthesize_segments(
        [("alpha one", "curious"), ("beta two", "angry")], tmp_path / "n.wav"
    )
    assert words == ["alpha", "beta"]
    assert starts == [0.0, 2.0]  # 2.0 = audio length, NOT the 1.0 last-word end
    assert ends == [1.0, 3.0]


def test_each_segment_is_synthesised_with_its_own_voice_id(tmp_path, fake_sse):
    CartesiaTimestampVoice().synthesize_segments(
        [("alpha one", "curious"), ("beta two", "surprise")], tmp_path / "n.wav"
    )
    assert [vid for _text, vid in fake_sse] == [VOICES["curious"], VOICES["surprise"]]


def test_a_failing_emotion_segment_retries_in_the_narrator_voice(tmp_path, monkeypatch):
    """Losing a flourish must never cost a 432-second run."""
    calls: list[str] = []

    def _flaky(self, text, voice_id, model, speed):
        calls.append(voice_id)
        if voice_id == VOICES["angry"]:
            raise RuntimeError("Cartesia SSE 500")
        return _silence(2.0), ["w"], [0.0], [1.0]

    monkeypatch.setattr(CartesiaTimestampVoice, "_sse_once", _flaky)
    words, starts, _ends = CartesiaTimestampVoice().synthesize_segments(
        [("a", "curious"), ("b", "angry")], tmp_path / "n.wav"
    )
    assert calls == [VOICES["curious"], VOICES["angry"], VOICES["curious"]]
    assert len(words) == 2 and starts == [0.0, 2.0]


def test_a_failing_NARRATOR_segment_still_raises(tmp_path, monkeypatch):
    """The fallback is the narrator voice. If that fails there is nothing left to fall back to."""
    def _dead(self, text, voice_id, model, speed):
        raise RuntimeError("Cartesia SSE 500")

    monkeypatch.setattr(CartesiaTimestampVoice, "_sse_once", _dead)
    with pytest.raises(RuntimeError):
        CartesiaTimestampVoice().synthesize_segments([("a", "curious")], tmp_path / "n.wav")


def test_one_segment_matches_the_old_single_call_shape(tmp_path, fake_sse):
    words, starts, ends = CartesiaTimestampVoice().synthesize_segments(
        [("only one", "curious")], tmp_path / "n.wav"
    )
    assert (words, starts, ends) == (["only"], [0.0], [1.0])
```

- [ ] **Step 2: Run them to watch them fail**

Run: `uv run pytest tests/test_emotion_synthesis.py -q`
Expected: FAIL — `CartesiaTimestampVoice` has no attribute `_sse_once`.

- [ ] **Step 3: Extract the single SSE call**

In `tools/studio_poc.py`, split the body of `CartesiaTimestampVoice.synthesize` so the network call
becomes its own method. Replace the existing `synthesize` with:

```python
    def _sse_once(
        self, text: str, voice_id: str, model: str, speed: float
    ) -> tuple[bytes, list[str], list[float], list[float]]:
        """ONE Cartesia SSE request. Returns (raw pcm_s16le bytes, words, starts, ends).

        Extracted so `synthesize_segments` can make several of these and so the stitching logic is
        testable without a network call.
        """
        import httpx

        key = os.environ.get("CARTESIA_API_KEY")
        if not key:
            raise RuntimeError("Set CARTESIA_API_KEY in .env to use Cartesia.")
        body = {
            "model_id": model, "transcript": text,
            "voice": {"mode": "id", "id": voice_id},
            "add_timestamps": True,
            "generation_config": {"speed": speed},
            "output_format": {
                "container": "raw", "encoding": "pcm_s16le", "sample_rate": SAMPLE_RATE,
            },
        }
        pcm = bytearray()
        words: list[str] = []
        starts: list[float] = []
        ends: list[float] = []
        with httpx.stream(
            "POST", "https://api.cartesia.ai/tts/sse",
            headers={"X-API-Key": key, "Cartesia-Version": "2024-11-13",
                     "Content-Type": "application/json"},
            json=body, timeout=None,
        ) as resp:
            if resp.status_code != 200:
                raise RuntimeError(f"Cartesia SSE {resp.status_code}: {resp.read()[:300]!r}")
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[len("data:"):].strip()
                if not payload or payload == "[DONE]":
                    continue
                msg = json.loads(payload)
                kind = msg.get("type")
                if kind == "chunk" and msg.get("data"):
                    pcm += base64.b64decode(msg["data"])
                elif kind == "timestamps":
                    wt = msg.get("word_timestamps") or {}
                    words += [str(x) for x in wt.get("words", [])]
                    starts += [float(x) for x in wt.get("start", [])]
                    ends += [float(x) for x in wt.get("end", [])]
                if msg.get("done"):
                    break
        if not pcm:
            raise RuntimeError("Cartesia SSE returned no audio.")
        return bytes(pcm), words, starts, ends

    def _model_and_speed(self) -> tuple[str, float]:
        model = os.environ.get("CARTESIA_SSE_MODEL", "sonic-2")
        speed = max(0.6, min(1.5, float(os.environ.get("CARTESIA_SPEED", "0.88"))))
        return model, speed

    def _write_wav(self, pcm: bytes, out_path: Path) -> None:
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # pcm_s16le
            w.setframerate(SAMPLE_RATE)
            w.writeframes(pcm)

    def synthesize(
        self, text: str, out_path: Path
    ) -> tuple[list[str], list[float], list[float]]:
        """One voice for the whole script — the original single-call path."""
        return self.synthesize_segments([(text, _cartesia_voice_name())], out_path)
```

- [ ] **Step 4: Add the segmented path**

Immediately after `synthesize`, add:

```python
    def synthesize_segments(
        self, segments: Sequence[tuple[str, str]], out_path: Path
    ) -> tuple[list[str], list[float], list[float]]:
        """One SSE call per (text, voice_name); returns ONE stitched timing stream.

        The result is shape-identical to a single call — one wav at `out_path`, one monotonic
        (words, starts, ends) triple — so nothing downstream can tell the narration was segmented.

        A non-narrator segment that fails is retried once in the narrator voice: losing an
        emotional flourish must never throw away a run that has already paid for research, a
        script, and the segments before it.
        """
        model, speed = self._model_and_speed()
        narrator_id = _cartesia_voice()
        pcm = bytearray()
        collected: list[tuple[list[str], list[float], list[float], float]] = []
        for text, voice_name in segments:
            voice_id = _segment_voice_id(voice_name)
            try:
                chunk, words, starts, ends = self._sse_once(text, voice_id, model, speed)
            except Exception as exc:  # noqa: BLE001 — see the docstring; degrade, don't abort
                if voice_id == narrator_id:
                    raise
                print(f"  ⚠ {voice_name} segment failed ({exc}); re-reading it in the "
                      f"narrator voice", file=sys.stderr)
                chunk, words, starts, ends = self._sse_once(text, narrator_id, model, speed)
            if not ends:  # audio but no timestamps → one span covering the whole chunk
                words, starts, ends = [text], [0.0], [len(chunk) / 2 / SAMPLE_RATE]
            pcm += chunk
            collected.append((words, starts, ends, len(chunk) / 2 / SAMPLE_RATE))
        self._write_wav(bytes(pcm), out_path)
        words, starts, ends = stitch_word_times(collected)
        _assert_timeline_sane(starts, ends, len(pcm) / 2 / SAMPLE_RATE)
        return words, starts, ends
```

and change `synthesize` (Step 3) to label its single segment with the narrator take:

```python
    def synthesize(
        self, text: str, out_path: Path
    ) -> tuple[list[str], list[float], list[float]]:
        """One voice for the whole script — the original single-call path."""
        return self.synthesize_segments([(text, NARRATOR)], out_path)
```

Add these module-level helpers above the class:

```python
def _segment_voice_id(voice_name: str) -> str:
    """Resolve one segment's voice to a Cartesia id.

    The narrator segment goes through `_cartesia_voice`, so `CARTESIA_VOICE_ID` and
    `CARTESIA_VOICE` still work and a custom clone is still usable. Emotional segments always
    resolve to their own public Carson id — an override there would defeat the point.
    """
    if voice_name == NARRATOR:
        return _cartesia_voice()
    return resolve_voice(None, voice_name)


def narrator_is_a_carson_take() -> bool:
    """True when the narrator is one of the four Carson takes.

    Emotion switching only works because all four takes are the SAME SPEAKER. If the narrator has
    been pointed at a custom clone via `CARTESIA_VOICE_ID`, switching mid-video would swap in a
    different person's voice — far worse than a flat read. `build_narration` collapses to a single
    segment when this is False.
    """
    return _cartesia_voice() in set(VOICES.values())


def _assert_timeline_sane(starts: Sequence[float], ends: Sequence[float], audio_sec: float) -> None:
    """A stitching bug does not crash — it silently desyncs every caption and cut in the video.

    So it is checked here and raised, unlike every other failure on this path which degrades.
    """
    if len(starts) != len(ends):
        raise RuntimeError(f"stitched timeline length mismatch: {len(starts)} vs {len(ends)}")
    for i in range(1, len(starts)):
        if starts[i] < starts[i - 1] or ends[i] < ends[i - 1]:
            raise RuntimeError(
                f"stitched timeline is not monotonic at word {i}: "
                f"start {starts[i - 1]}->{starts[i]}, end {ends[i - 1]}->{ends[i]}"
            )
    if ends and ends[-1] > audio_sec + 0.05:
        raise RuntimeError(
            f"stitched timeline ends at {ends[-1]:.3f}s but the audio is {audio_sec:.3f}s"
        )
```

Add to the imports at the top of `tools/studio_poc.py`:

```python
from studio.emotion import (  # noqa: E402
    EMOTION_MAX_PER_VIDEO,
    plan_voice_segments,
    stitch_word_times,
)
from studio.voices import NARRATOR, VOICES, resolve_voice  # noqa: E402
```

(`resolve_voice` is already imported from `studio.voices` — extend that line rather than adding a
second one, or ruff's `I001` will fail.)

- [ ] **Step 5: Run the synthesis tests**

Run: `uv run pytest tests/test_emotion_synthesis.py -q`
Expected: PASS, 6 tests.

- [ ] **Step 6: Wire the planner into `build_narration`**

In `tools/studio_poc.py::build_narration`, replace the `if voice.name == "cartesia":` block
(currently lines 780-786) with:

```python
    if voice.name == "cartesia":
        # Switching only works because the four takes are one speaker. Pointed at a custom clone,
        # a switch would swap in a different person mid-video — so don't switch at all.
        segments = plan_voice_segments(
            [s.emotion for s in scenes], [s.emotion_score for s in scenes],
            max_switches=EMOTION_MAX_PER_VIDEO if narrator_is_a_carson_take() else 0,
        )
        texts = [
            (build_transcript(narrations[seg.first_beat : seg.last_beat + 1]), seg.voice)
            for seg in segments
        ]
        if len(texts) > 1:
            print(f"  narration: {len(texts)} voice segments — "
                  + ", ".join(f"{s.voice}[{s.first_beat}-{s.last_beat}]" for s in segments))
        words, starts, ends = CartesiaTimestampVoice().synthesize_segments(texts, wav)
        # Anchor each beat to the REAL spoken word where its text ends (accurate; the old
        # character-proportional align_beats drifted up to ~3.5s mid-video).
        spans = align_beats_to_words(narrations, words, starts, ends)
        return wav, spans, words, starts, ends
```

- [ ] **Step 7: Verify the no-emotion path is byte-for-byte the old behaviour**

A storyboard with no emotion tags must produce exactly ONE segment and therefore exactly one SSE
call — identical to today. Add to `tests/test_emotion_synthesis.py`:

```python
def test_a_storyboard_with_no_emotion_tags_makes_exactly_one_call(tmp_path, fake_sse):
    """The single-voice path must not regress: no tags -> one segment -> one Cartesia call."""
    from studio.emotion import plan_voice_segments

    segments = plan_voice_segments([""] * 40, [0.0] * 40)
    assert len(segments) == 1
    CartesiaTimestampVoice().synthesize_segments(
        [("the whole script", segments[0].voice)], tmp_path / "n.wav"
    )
    assert len(fake_sse) == 1


def test_a_custom_clone_narrator_disables_emotion_switching(monkeypatch):
    """All four takes are one speaker, which is the whole premise. Pointed at a custom clone,
    a switch would swap in a different person mid-video."""
    from tools.studio_poc import narrator_is_a_carson_take

    monkeypatch.setenv("CARTESIA_VOICE_ID", "11111111-2222-3333-4444-555555555555")
    assert narrator_is_a_carson_take() is False
    monkeypatch.delenv("CARTESIA_VOICE_ID")
    monkeypatch.setenv("CARTESIA_VOICE", "curious")
    assert narrator_is_a_carson_take() is True
```

- [ ] **Step 8: Full suite and lint**

Run: `uv run pytest -q && uv run ruff check .`
Expected: 370 passing (362 + 8), ruff clean.

- [ ] **Step 9: Commit**

```bash
git add tools/studio_poc.py tests/test_emotion_synthesis.py
git commit -m "feat: synthesise narration in per-emotion segments and stitch the timeline"
```

- [ ] **Step 10: One real end-to-end check**

Run a real Cartesia narration on a storyboard whose calibration output (Task 4) shows at least one
switch, using `--resume` so nothing else is re-paid:

```bash
uv run python tools/studio_poc.py \
  --storyboard result/axen/scripts/<a-script-with-a-switch>/storyboard.json \
  --voice cartesia --images placeholder
```

Confirm from the log that the segment line printed, then check the wav:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 <run-dir>/narration.wav
```

Expected: the duration is roughly the sum of the segments, `word_timings.json` is monotonic, and
`_assert_timeline_sane` did not fire. Listen to the switch point.

---

## Self-Review

**Spec coverage.** Goal → Tasks 2+5. The four-take table → Task 5 (`resolve_voice` per segment).
Frequency measurement → Task 4 replays it. Seam risk → Task 1 (gating). Silent-desync risk →
`stitch_word_times` (Task 2) plus `_assert_timeline_sane` (Task 5). `studio/emotion.py` →
Task 2. Scorer + `Scene` fields → Task 3. Stitcher → Task 5. All four guardrail constants →
Task 2, replayed in Task 4. All four failure-handling rows → Task 3 (unknown name, bad score),
Task 5 (segment failure, timeline assertion). Testing section: Task 1 is the A/B; L0 planner and
stitching are Task 2; calibration is Task 4; the offline integration check is Task 5 Step 7.
Out-of-scope items appear in no task. **No gaps.**

**Placeholders.** None: every code step carries runnable code, and the two judgement steps
(Task 1 Step 5, Task 4 Step 3) enumerate the concrete outcomes and what each one means.

**Type consistency.** `VoiceSegment(voice, first_beat, last_beat)` is used identically in Tasks 2,
4 and 5. `plan_voice_segments(emotions, scores)` takes two positional sequences everywhere.
`stitch_word_times` takes 4-tuples ending in `audio_seconds` in both its definition and its
caller. `synthesize_segments(segments, out_path)` takes `(text, voice_name)` pairs in the tests,
the implementation, and `build_narration`. `Scene.emotion` / `Scene.emotion_score` are named
identically in Tasks 3, 4 and 5.

One deliberate note for the Task 5 implementer: `_cartesia_voice_name` returns an explicit
`CARTESIA_VOICE_ID` unchanged when set, because `resolve_voice(None, name)` would reject it as an
unknown take. That is why it returns a *name or id* rather than only a name.
