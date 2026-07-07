#!/usr/bin/env python3
"""Re-assemble a saved storyboard into a better-paced video WITHOUT regenerating images.

The pacing rework (issues the user raised on run 20260701-095928):
  1. No more cutting *back* to the same frame — images play on a forward schedule
     (`studio.narration.image_timeline`): main shot, then brief cutaway flashes, next beat's main.
  2. One continuous narration (Cartesia SSE, `add_timestamps`) → natural prosody instead of the old
     per-beat synth + crude atempo slow-down.
  3. Image + caption cuts are driven by REAL spoken word times (pause-snapped beat alignment), so
     subtitles and picture switches land on the actual narration.

Reuses the images already on disk (`img_{i}.png`, `img_{i}_cut{k}.png`); only the audio is new.

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
    align_beats_to_words,
    build_transcript,
    caption_timeline,
    emphasis_timeline,
    image_timeline,
    storyboard_from_dict,
)
from tools.studio_poc import (  # noqa: E402
    CartesiaTimestampVoice,
    H,
    W,
    ffprobe_duration,
    render_video,
)


# ── Assembly ───────────────────────────────────────────────────────────────────
def count_frames(images_dir: Path, index: int) -> int:
    """How many frames exist on disk for beat `index` — img_i plus img_i_1, img_i_2, … (≥1)."""
    k = 1
    while (images_dir / f"img_{index}_{k}.png").is_file():
        k += 1
    return k


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
    segments = image_timeline(beat_spans, frames_per_beat)
    cues = caption_timeline(beat_spans, narrations)
    overlays = [
        (text, start, end, images_dir / f"img_{bi}.png")
        for text, bi, start, end in emphasis_timeline(
            beat_spans, [s.emphasis for s in sb.scenes], narrations
        )
    ]

    print(f"  {len(sb.scenes)} beats → {len(segments)} image cuts, {len(cues)} caption cues, "
          f"{len(overlays)} callouts")
    for i, ((start, end), c) in enumerate(zip(beat_spans, frames_per_beat, strict=False)):
        print(f"   beat {i:2}: {start:6.2f}–{end:6.2f}s ({end - start:4.1f}s, {c} frame(s))")

    resolved = [(images_dir / name, start, end) for name, start, end in segments]
    render_video(resolved, wav, cues, out, overlays=overlays)
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
