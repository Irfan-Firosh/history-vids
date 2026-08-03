"""Build an .ass subtitle file (pure string generation).

Captions were previously one full-frame PNG overlay per cue, serially chained in a single ffmpeg
filtergraph. Measured on this machine that costs ~0.011 s/frame per overlay: an 8-minute video with
~290 cues over 14,400 frames is ~12.8 hours. libass renders all of them in ONE filter.

This module is pure so the styling is diffable and testable; the burn-in lives in tools/render.
"""

from __future__ import annotations

from collections.abc import Sequence

_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, \
Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, \
MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},&H00141414,&H00FFFFFF,&H00FFFFFF,0,0,0,0,100,100,0,0,1,4,0,2,\
120,120,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"""


def ass_timestamp(seconds: float) -> str:
    """``H:MM:SS.CC`` — ASS uses centiseconds, not milliseconds."""
    total = max(0.0, float(seconds))
    hours, rem = divmod(int(total), 3600)
    minutes, secs = divmod(rem, 60)
    centis = int(round((total - int(total)) * 100))
    if centis == 100:  # rounding carried into the next second
        centis, secs = 0, secs + 1
        if secs == 60:
            secs, minutes = 0, minutes + 1
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


def _escape(text: str) -> str:
    """Neutralise ASS control characters.

    ``{`` opens an override block, so unescaped narration containing braces would be read as
    styling commands rather than displayed. Newlines become the literal ``\\N`` line break.
    """
    return (
        text.replace("\\", "\\\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\r\n", "\\N")
        .replace("\n", "\\N")
    )


def build_ass(
    cues: Sequence[tuple[str, float, float]],
    *,
    width: int = 1920,
    height: int = 1080,
    font: str = "Arial",
    font_size: int = 54,
) -> str:
    """Render cues as an .ass file: dark text with a heavy white outline, bottom-centred."""
    lines = [_HEADER.format(width=width, height=height, font=font, font_size=font_size)]
    for text, start, end in cues:
        if end <= start:
            continue
        span = f"{ass_timestamp(start)},{ass_timestamp(end)}"
        lines.append(f"Dialogue: 0,{span},Default,,0,0,0,,{_escape(text)}")
    return "\n".join(lines) + "\n"
