"""Concatenate per-shot segments, mux narration, and burn subtitles in ONE pass.

Replaces `studio_poc.render_video`, which built a single filtergraph with N image inputs and M
serially chained full-frame PNG overlay nodes. Measured on this machine, that chain costs
~0.303 s/frame at depth 32, 1.391 at 128, and did not finish a 2-second output at 256. An 8-minute
video needs ~290 caption cues over 14,400 frames.

Here the segments are already rendered (`tools.render.segments.render_segment`) and stream-copy
together, and every caption is one .ass Dialogue line handled by a single libass filter. There is
ZERO PNG-overlay burn-in anywhere in this module — that is the entire point of the rebuild — so
when the active ffmpeg has no libass, `assemble` refuses outright rather than silently emitting a
video with missing captions.

`render_shots` is the adapter this task owns: `render_segment` only knows a raw image `Path` and a
float duration, while `studio.shots.plan_shots` produces `Shot` objects carrying `image_key` and
`start`/`end`. Nothing upstream bridges the two — this is that bridge.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from studio.shots import Shot
from studio.subtitles import build_ass
from tools.render.ffmpeg import ffmpeg_bin, subtitle_backend
from tools.render.segments import render_segment

#: Hard ceiling referenced in the refusal message below. A chained PNG-overlay burn (not
#: implemented in this module — see the module docstring) costs ~0.011 s/frame per cue and would
#: not scale past this many cues even if it existed here.
MAX_PNG_OVERLAY_CUES = 50


def concat_file(segments: Sequence[Path], out: Path) -> Path:
    """Write an ffmpeg concat-demuxer list.

    Paths are single-quoted with embedded apostrophes escaped: an unescaped `'` terminates the
    quoted string and silently drops or corrupts entries.
    """
    if not segments:
        raise ValueError("no segments to concatenate")
    lines = []
    for seg in segments:
        escaped = str(seg.resolve()).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    out.write_text("\n".join(lines) + "\n")
    return out


def render_shots(
    shots: Sequence[Shot],
    image_dir: Path,
    out_dir: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> list[Path]:
    """Adapter: resolve each `Shot.image_key`/`duration` and render it via `render_segment`.

    Returns one rendered segment path per shot, in the same order as `shots`. `shots` is expected
    to already be contiguous/monotonic (the `plan_shots` contract) — this function does not
    reorder or merge them, it only resolves each one to a cached mp4.
    """
    segments: list[Path] = []
    for shot in shots:
        image = image_dir / shot.image_key
        out, _was_cached = render_segment(
            image, shot.duration, out_dir, width=width, height=height, fps=fps
        )
        segments.append(out)
    return segments


def assemble(
    segments: Sequence[Path],
    wav: Path,
    cues: Sequence[tuple[str, float, float]],
    out: Path,
    *,
    work_dir: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> Path:
    """Concat `segments`, mux `wav`, burn `cues`. Returns `out`.

    With no cues, video is stream-copied byte-for-byte (`-c:v copy`) — nothing to draw, nothing to
    re-encode. With cues, the whole thing re-encodes once through a single libass `subtitles`
    filter. There is no third path: if cues are requested and this ffmpeg has no libass, this
    raises rather than starting a PNG-overlay render or silently dropping the captions.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    listing = concat_file(segments, work_dir / "concat.txt")
    backend = subtitle_backend()

    if cues and backend != "libass":
        raise RuntimeError(
            f"{len(cues)} caption cue(s) requested but this ffmpeg has no libass. This assembler "
            f"burns captions in a single libass pass with zero PNG-overlay nodes, so there is no "
            f"slow-path fallback to run here (a chained PNG-overlay burn would itself be capped "
            f"at {MAX_PNG_OVERLAY_CUES} cues — it costs ~0.011 s/frame per cue and does not "
            f"scale). Fix:\n"
            f"  brew install ffmpeg-full\n"
            f"  export FFMPEG_BIN=/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg\n"
            f"Or re-run with captions disabled."
        )

    cmd = [
        ffmpeg_bin(), "-nostdin", "-v", "error", "-y",
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-i", str(wav),
    ]
    if cues:
        ass = work_dir / "captions.ass"
        ass.write_text(build_ass(cues, width=width, height=height))
        # Escape for the filter-argument parser: ':' separates options, '\' escapes.
        filter_path = str(ass.resolve()).replace("\\", "\\\\").replace(":", r"\:")
        cmd += [
            "-vf", f"subtitles='{filter_path}'",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        ]
    else:
        cmd += ["-c:v", "copy"]  # nothing to draw → keep the segments byte-for-byte
    cmd += ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(out)]
    subprocess.run(cmd, check=True, capture_output=True)
    return out
