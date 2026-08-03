"""Render one still to a short mp4, cached by content hash.

Each segment is independent: identical codec parameters mean the concat demuxer can stream-copy
them together with no re-encode, and an unchanged shot is never re-rendered. This is what makes a
208-shot video usable as a development loop instead of a once-a-day event.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from tools.render.ffmpeg import ffmpeg_bin

#: Bump whenever the ffmpeg arguments below change. A cache key that outlives a renderer change
#: silently serves stale video — worse than no cache, because the output looks correct.
CACHE_VERSION = 1


def segment_key(image_bytes: bytes, duration: float, width: int, height: int, fps: int) -> str:
    """Cache key covering every input that can change the rendered bytes."""
    digest = hashlib.sha256(image_bytes).hexdigest()[:32]
    return f"v{CACHE_VERSION}-{digest}-{duration:.3f}-{width}x{height}-{fps}"


def render_segment(
    image: Path,
    duration: float,
    out_dir: Path,
    *,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> tuple[Path, bool]:
    """Render `image` held for `duration` seconds. Returns (path, was_cached)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    key = segment_key(image.read_bytes(), duration, width, height, fps)
    out = out_dir / f"seg_{key}.mp4"
    if out.exists() and out.stat().st_size > 0:
        return out, True
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1,fps={fps}"
    )
    subprocess.run(
        [
            ffmpeg_bin(), "-nostdin", "-v", "error", "-y",
            "-loop", "1", "-t", f"{duration:.3f}", "-i", str(image),
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-g", str(fps * 2), str(out),
        ],
        check=True, capture_output=True,
    )
    return out, False
