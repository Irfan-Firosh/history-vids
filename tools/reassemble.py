#!/usr/bin/env python3
"""Re-assemble a saved storyboard into a better-paced video WITHOUT regenerating images.

The pacing rework (issues the user raised on run 20260701-095928):
  1. No more cutting *back* to the same frame — images play on a forward schedule
     (`studio.narration.image_timeline`): main shot, then brief cutaway flashes, next beat's main.
  2. One continuous narration (Cartesia SSE, `add_timestamps`) → natural prosody instead of the old
     per-beat synth + crude atempo slow-down.
  3. Image + caption cuts are driven by REAL spoken word times (pause-snapped beat alignment), so
     subtitles and picture switches land on the actual narration.

Reuses the images already on disk (`img_{i}.png`, `img_{i}_{k}.png`); only the audio is new.

Rendering goes through the same segment-cache + single-libass-pass path as the main pipeline
(`tools.studio_poc._assemble_video`): each on-screen still is rendered once to a cached mp4
(`tools.render.assemble.render_shots`) and the whole thing is concatenated + captioned in one
`tools.render.assemble.assemble` call. This replaced the old `render_video`, which built one
FFmpeg filtergraph with a serially chained `overlay` node per caption cue — measured ~12.8h for an
8-minute video (see `tools/render/assemble.py`'s module docstring) — `render_video` has been
deleted; nothing else called it.

Run:
  python tools/reassemble.py \
    --storyboard assets/generated/ancient-humans-at-night/storyboard.json \
    --images-dir assets/generated/ancient-humans-at-night \
    --out assets/generated/ancient-humans-at-night/video_v2.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

from studio import (  # noqa: E402
    Shot,
    align_beats_to_words,
    build_transcript,
    caption_timeline,
    image_timeline,
    storyboard_from_dict,
)
from tools.render.assemble import assemble, render_shots  # noqa: E402
from tools.studio_poc import (  # noqa: E402
    FPS,
    CartesiaTimestampVoice,
    H,
    W,
    ffprobe_duration,
)


# ── Assembly ───────────────────────────────────────────────────────────────────
def count_frames(images_dir: Path, index: int) -> int:
    """How many frames exist on disk for beat `index` — img_i plus img_i_1, img_i_2, … (≥1)."""
    k = 1
    while (images_dir / f"img_{index}_{k}.png").is_file():
        k += 1
    return k


def _shots_from_disk(
    beat_spans: list[tuple[float, float]], frames_per_beat: list[int], shot_types: list[str],
) -> list[Shot]:
    """The on-screen Shot schedule, driven by frames actually rendered on disk (`frames_per_beat`,
    from `count_frames`) rather than a fresh-render count — reassemble reuses existing images only,
    it never generates new ones. Reuses `image_timeline`'s exact (name, start, end) segmentation
    (same forward-only, no-cut-back schedule the main pipeline uses) and rebuilds it as `Shot`
    objects so it can be handed to `render_shots`."""
    segments = image_timeline(beat_spans, frames_per_beat)
    shots: list[Shot] = []
    idx = 0
    for i, n in enumerate(frames_per_beat):
        for k in range(n):
            name, start, end = segments[idx]
            idx += 1
            shots.append(Shot(
                beat_index=i, sub_index=k, start=start, end=end,
                image_key=name, shot_type=shot_types[i],
            ))
    return shots


def reassemble(storyboard_path: Path, images_dir: Path, out: Path) -> Path:
    sb = storyboard_from_dict(json.loads(storyboard_path.read_text()))
    narrations = [s.narration for s in sb.scenes]

    transcript = build_transcript(narrations)
    wav = out.with_name("narration.wav")
    print(f"Synthesising one continuous narration ({len(transcript)} chars) via Cartesia SSE…")
    words, starts, ends = CartesiaTimestampVoice().synthesize(transcript, wav)
    total = float(ends[-1]) if ends else ffprobe_duration(wav)
    print(f"  audio {total:.1f}s · {len(starts)} word timestamps")

    beat_spans = align_beats_to_words(narrations, words, starts, ends)
    frames_per_beat = [count_frames(images_dir, i) for i in range(len(sb.scenes))]
    shots = _shots_from_disk(beat_spans, frames_per_beat, [s.shot_type for s in sb.scenes])
    cues = caption_timeline(beat_spans, narrations, words=words, word_starts=starts, word_ends=ends)

    print(f"  {len(sb.scenes)} beats → {len(shots)} image cuts, {len(cues)} caption cues")
    for i, ((start, end), c) in enumerate(zip(beat_spans, frames_per_beat, strict=False)):
        print(f"   beat {i:2}: {start:6.2f}–{end:6.2f}s ({end - start:4.1f}s, {c} frame(s))")

    segments = render_shots(
        shots, images_dir, out.parent / "segments", width=W, height=H, fps=FPS,
    )
    assemble(
        segments, wav, cues, out, work_dir=out.parent / "assemble_work", width=W, height=H, fps=FPS,
    )
    dur = ffprobe_duration(out)
    print(f"\n✅ {out}  ({dur:.1f}s, {W}x{H}) — reused {images_dir.name} images, new audio")
    return out


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    gallery = _ROOT / "assets/generated/ancient-humans-at-night"
    ap.add_argument("--storyboard", default=str(gallery / "storyboard.json"))
    ap.add_argument("--images-dir", default=str(gallery))
    ap.add_argument("--out", default=str(gallery / "video_v2.mp4"))
    args = ap.parse_args()
    reassemble(Path(args.storyboard), Path(args.images_dir), Path(args.out))


if __name__ == "__main__":
    main()
