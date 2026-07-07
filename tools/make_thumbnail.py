#!/usr/bin/env python3
"""Generate a YouTube thumbnail: a text-free focal image (channel style) + a hand-drawn title card.

Research-backed layout (1280x720): one bold focal subject on the LEFT third, big negative space on
the right for 2-4 BIG words, high contrast, curiosity gap. The image model never renders the words
(it garbles text) — the title is overlaid with PIL as a crude wobbly paper card so it matches the
same marker-cartoon style as the video frames instead of a polished Impact-font thumbnail.

Run:
  python tools/make_thumbnail.py --subject "a lone figure at a grave at dusk" \
      --text "THE FIRST GOODBYE" --model agnes --out result/axen/thumbs/death.png
"""
from __future__ import annotations

import argparse
import io
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

from studio import thumbnail_prompt  # noqa: E402
from tools.studio_poc import make_image_provider  # noqa: E402

THUMB_W, THUMB_H = 1280, 720
#: Hand-drawn display fonts, in preference order. Schoolbell is committed (OFL) and also used for
#: in-video callouts, so thumbnail text shares the same rough marker-cartoon language.
_TITLE_FONTS = [
    str(_ROOT / "assets/fonts/Schoolbell.ttf"),
    "/System/Library/Fonts/Supplemental/Chalkduster.ttf",
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _title_font(size: int):
    from PIL import ImageFont

    for f in _TITLE_FONTS:
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _cover_resize(im, w: int, h: int):
    """Scale to cover w×h, then centre-crop (fill the thumbnail frame, no letterboxing)."""
    from PIL import Image

    sw, sh = im.size
    scale = max(w / sw, h / sh)
    im = im.resize((max(w, int(sw * scale)), max(h, int(sh * scale))), Image.LANCZOS)
    left, top = (im.size[0] - w) // 2, (im.size[1] - h) // 2
    return im.crop((left, top, left + w, top + h))


def _wrap_to_width(draw, words: list[str], font, max_w: int) -> list[str]:
    """Greedily wrap words into lines no wider than max_w."""
    lines: list[str] = []
    cur = ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _wobbly_rect_points(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int]]:
    """Deterministic hand-drawn rectangle points; no randomness, so tests/screenshots are stable."""
    wobble = [0, -6, 4, -3, 5, -4, 3, 0]
    step = 64
    pts: list[tuple[int, int]] = []
    for i, x in enumerate(range(x0, x1 + 1, step)):
        pts.append((x, y0 + wobble[i % len(wobble)]))
    for i, y in enumerate(range(y0 + step, y1 + 1, step)):
        pts.append((x1 + wobble[(i + 2) % len(wobble)], y))
    for i, x in enumerate(range(x1 - step, x0 - 1, -step)):
        pts.append((x, y1 + wobble[(i + 4) % len(wobble)]))
    for i, y in enumerate(range(y1 - step, y0, -step)):
        pts.append((x0 + wobble[(i + 6) % len(wobble)], y))
    return pts


def _draw_title_card(draw, box: tuple[int, int, int, int]) -> None:
    """Draw a pale, wobbly, double-outlined card like a marker doodle on top of the frame."""
    x0, y0, x1, y1 = box
    pts = _wobbly_rect_points(x0, y0, x1, y1)
    draw.polygon(pts, fill=(246, 242, 226, 238))
    draw.line(pts + [pts[0]], fill=(18, 18, 18, 255), width=7, joint="curve")
    inset = 10
    pts2 = _wobbly_rect_points(x0 + inset, y0 + inset, x1 - inset, y1 - inset)
    draw.line(pts2 + [pts2[0]], fill=(18, 18, 18, 210), width=2, joint="curve")


def overlay_title(image_bytes: bytes, text: str, out: Path) -> None:
    """Compose the final 1280x720 thumbnail: focal image + hand-lettered title card on the right."""
    from PIL import Image, ImageDraw

    im = _cover_resize(
        Image.open(io.BytesIO(image_bytes)).convert("RGB"), THUMB_W, THUMB_H
    ).convert("RGBA")
    draw = ImageDraw.Draw(im)
    words = text.upper().split() or ["UNTITLED"]

    # Text lives on a wobbly card in the right ~52%. This keeps the generated focal image untouched
    # and makes the typography look like a deliberate part of the same crude hand-drawn system.
    card = (int(THUMB_W * 0.47), 74, THUMB_W - 48, THUMB_H - 78)
    _draw_title_card(draw, card)
    area_x, area_y = card[0] + 46, card[1] + 52
    area_w = card[2] - card[0] - 92
    area_h = card[3] - card[1] - 104

    size, lines = 132, [text.upper()]
    for size in range(148, 42, -6):
        font = _title_font(size)
        lines = _wrap_to_width(draw, words, font, area_w)
        line_h = int(size * 1.08)
        if len(lines) <= 4 and line_h * len(lines) <= area_h:
            break
    font = _title_font(size)
    line_h = int(size * 1.08)
    total_h = line_h * len(lines)
    y = area_y + (area_h - total_h) // 2
    stroke = max(2, size // 22)
    for line in lines:
        w = draw.textlength(line, font=font)
        x = area_x + (area_w - w) / 2
        # Small off-register shadow + rough black lettering, like the refs' hand-written labels.
        draw.text((x + 4, y + 5), line, font=font, fill=(150, 105, 45, 110))
        draw.text((x, y), line, font=font, fill=(18, 18, 18),
                  stroke_width=stroke, stroke_fill=(246, 242, 226))
        y += line_h
    out.parent.mkdir(parents=True, exist_ok=True)
    im.convert("RGB").save(out)


def make_thumbnail(subject: str, text: str, model: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    provider = make_image_provider(model)
    prompt = thumbnail_prompt(subject)
    raw = out.with_name(out.stem + ".raw.png")
    print(f"generating thumbnail image ({model}) …")
    provider.generate(prompt, raw, ())
    overlay_title(raw.read_bytes(), text, out)
    raw.unlink(missing_ok=True)
    print(f"✅ {out}  ({THUMB_W}x{THUMB_H})")
    return out


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subject", required=True, help="the focal scene (text-free; style auto-added)")
    ap.add_argument("--text", required=True, help="2-4 BIG words overlaid on the right")
    ap.add_argument("--model", choices=["agnes", "gemini", "hf", "placeholder"], default="agnes")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    make_thumbnail(args.subject, args.text, args.model, Path(args.out))


if __name__ == "__main__":
    main()
