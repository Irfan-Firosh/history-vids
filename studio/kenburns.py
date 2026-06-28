"""Per-scene FFmpeg video filter.

Chosen style (from reference channels): **static images, HARD CUTS** — each AI image is held for
its narration beat (~5–10s) and cut straight to the next (the `concat` step gives the hard cut). No
transitions, no motion. That's the default (`motion="static"`).

Optional subtle Ken-Burns camera motion (pan/zoom) is kept available via `MOTIONS` but is OFF by
default — set a scene's `motion` to enable it. zoompan window = (iw/zoom × ih/zoom) at (x,y) scaled
to `s`; we pre-upscale 2x so motion stays sharp; `on` = output frame index (drives pans).
"""

from __future__ import annotations

#: Optional Ken-Burns camera moves (OFF by default; the channel style is static hard cuts).
MOTIONS: tuple[str, ...] = ("zoom_in", "pan_right", "zoom_out", "pan_left", "pan_up", "pan_down")

_ZOOM_RATE = 0.0016
_MAX_ZOOM = 1.5
_PAN_ZOOM = 1.3


def motion_for_index(i: int) -> str:
    """Rotate through the optional Ken-Burns moves (only if you opt into motion)."""
    return MOTIONS[i % len(MOTIONS)]


def scene_filter(
    motion: str = "static",
    width: int = 1920,
    height: int = 1080,
    duration_sec: float = 6.0,
    fps: int = 30,
) -> str:
    """Return the FFmpeg `-vf` chain for one scene.

    `motion="static"` (default) → a still image scaled/cropped to WxH, held for the clip (hard cut
    to the next scene at `concat`). Anything in `MOTIONS` → subtle Ken-Burns motion instead.
    """
    cover = (
        f"scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},setsar=1"
    )
    if motion == "static" or motion not in MOTIONS:
        return f"{cover},format=yuv420p"

    frames = max(1, round(duration_sec * fps))
    iw, ih = width * 2, height * 2  # pre-upscale so zoom/pan stay sharp
    cx = "x='iw/2-(iw/zoom/2)'"
    cy = "y='ih/2-(ih/zoom/2)'"
    if motion == "zoom_out":
        z, x, y = f"z='if(eq(on,0),{_MAX_ZOOM},max(zoom-{_ZOOM_RATE},1.0))'", cx, cy
    elif motion == "pan_right":
        z, x, y = f"z='{_PAN_ZOOM}'", f"x='(iw-iw/zoom)*on/{frames}'", cy
    elif motion == "pan_left":
        z, x, y = f"z='{_PAN_ZOOM}'", f"x='(iw-iw/zoom)*(1-on/{frames})'", cy
    elif motion == "pan_up":
        z, x, y = f"z='{_PAN_ZOOM}'", cx, f"y='(ih-ih/zoom)*(1-on/{frames})'"
    elif motion == "pan_down":
        z, x, y = f"z='{_PAN_ZOOM}'", cx, f"y='(ih-ih/zoom)*on/{frames}'"
    else:  # zoom_in
        z, x, y = f"z='min(zoom+{_ZOOM_RATE},{_MAX_ZOOM})'", cx, cy

    prescale = f"scale={iw}:{ih}:force_original_aspect_ratio=increase,crop={iw}:{ih},setsar=1"
    zoompan = f"zoompan={z}:{x}:{y}:d={frames}:s={width}x{height}:fps={fps}"
    return f"{prescale},{zoompan},format=yuv420p"
