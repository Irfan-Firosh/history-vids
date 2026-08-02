"""Which ffmpeg do we call, and what can it do?

The default Homebrew ffmpeg 8.1.2 is built WITHOUT libass/libfreetype/drawtext, which is why
captions were originally rendered as full-frame PNG overlays. That path costs ~0.011 s/frame per
overlay and does not scale past ~50 cues. `ffmpeg-full` is keg-only, so pointing `FFMPEG_BIN` at
it gets libass without disturbing the default install.
"""

from __future__ import annotations

import functools
import os
import subprocess

#: A build without this filter cannot burn .ass subtitles and must fall back to PNG overlays.
_SUBTITLE_FILTER = "subtitles"


def ffmpeg_bin() -> str:
    """The ffmpeg executable to invoke. Override with ``FFMPEG_BIN``."""
    return os.environ.get("FFMPEG_BIN") or "ffmpeg"


@functools.lru_cache(maxsize=8)
def _filters(bin_path: str) -> frozenset[str]:
    """Filter names this build exposes. Cached — shelling out per query is wasteful."""
    try:
        out = subprocess.run(
            [bin_path, "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=30, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return frozenset()
    names: set[str] = set()
    for line in out.splitlines():
        parts = line.split()
        # Rows look like: " ... name  in->out  description"; the flags column precedes the name.
        if len(parts) >= 3 and not line.startswith("Filters:"):
            names.add(parts[1] if len(parts[0]) <= 3 else parts[0])
    return frozenset(names)


def has_filter(name: str, *, bin_path: str | None = None) -> bool:
    """Does this ffmpeg build expose `name`?"""
    return name in _filters(bin_path or ffmpeg_bin())


def subtitle_backend(*, bin_path: str | None = None) -> str:
    """``"libass"`` when .ass burn-in is available, else ``"png_overlay"`` (slow, tiny runs)."""
    return "libass" if has_filter(_SUBTITLE_FILTER, bin_path=bin_path) else "png_overlay"
