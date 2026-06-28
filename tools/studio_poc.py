#!/usr/bin/env python3
"""Tier-0 faceless AI-history PoC — produces one assembled sample clip end-to-end.

Pipeline: canned storyboard → style-locked images → static hard-cut clips → narration → concat.
Proves the *automatable core*; paid pieces (Gemini images, Cartesia voice) are swappable providers.

Run:  python tools/studio_poc.py                              # placeholder images + macOS `say` (free)
      python tools/studio_poc.py --images gemini --voice cartesia   # real Gemini + Carson (needs .env)
Output: result/axen/poc/sample.mp4  (+ assets/ intermediates)

Providers:
  Images: PlaceholderImageProvider (free PIL card) → GeminiImageProvider ("Nano Banana", ~$0.039/img,
          needs GEMINI_API_KEY + billing; refs from assets/refs/ keep the character on-model).
  Voice:  SayVoiceProvider (macOS `say`) → CartesiaVoiceProvider (Carson). Motion: static hard cuts.
"""
from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from collections.abc import Sequence
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


from studio.style import LOCKED_STYLE, PALETTE  # noqa: E402

W, H, FPS = 1920, 1080, 30
SAMPLE_RATE = 44100  # Cartesia raw pcm_s16le mono (continuous-narration SSE output)
OUT_DIR = _ROOT / "result/axen/poc"
RUNS_DIR = OUT_DIR / "runs"  # each run gets its own subdir (manifest + log + assets) → browsable history
REFS_DIR = _ROOT / "assets/refs"  # committed channel identity: character.png, expressions.png

_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
    "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _fontfile() -> str | None:
    return next((f for f in _FONT_CANDIDATES if os.path.exists(f)), None)


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd[:3])}…\n{r.stderr[-1500:]}")


def ffprobe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip() or 0.0)


# ── Image providers ──────────────────────────────────────────────────────────
class PlaceholderImageProvider:
    """Renders a consistent cinematic title-card (PIL) standing in for a Gemini image.

    It deliberately uses the LOCKED palette/fonts on every card so 'style consistency' is visible.
    Real provider: `GeminiImageProvider` (below) renders the same `styled` prompt for real.
    """

    name = "placeholder"

    def generate(self, styled: str, out_path: Path, refs: Sequence[Path] = ()) -> Path:
        from PIL import Image, ImageDraw, ImageFont

        subject = styled.replace(LOCKED_STYLE, "").strip().rstrip(". ")
        # Flat off-white card with a thick black border — echoes the cartoon look it stands in for.
        img = Image.new("RGB", (W, H), PALETTE["bg_top"])
        draw = ImageDraw.Draw(img)
        draw.rectangle([18, 18, W - 18, H - 18], outline=(20, 20, 20), width=10)
        ff = _fontfile()
        big = ImageFont.truetype(ff, 56) if ff else ImageFont.load_default()
        small = ImageFont.truetype(ff, 30) if ff else ImageFont.load_default()
        tiny = ImageFont.truetype(ff, 24) if ff else ImageFont.load_default()

        draw.rectangle([140, H // 2 - 170, 140 + 90, H // 2 - 164], fill=PALETTE["accent"])
        lines = textwrap.wrap(subject, width=38)
        y = H // 2 - 140
        for ln in lines[:7]:
            draw.text((150, y), ln, font=big, fill=PALETTE["text"])
            y += 70
        draw.text((150, H - 150), "[ AI-image placeholder · prompt → Gemini 2.5 Flash Image ]",
                  font=small, fill=PALETTE["accent"])
        draw.text((150, H - 100), "locked style: minimalist stick-figure cartoon (Axen-like)",
                  font=tiny, fill=PALETTE["muted"])
        img.save(out_path)
        return out_path


# ── Voice providers ──────────────────────────────────────────────────────────
class SayVoiceProvider:
    """macOS `say` → wav. The free PoC stand-in for Cartesia 'Carson'."""

    name = "say"

    def synthesize(self, text: str, out_path: Path) -> float:
        aiff = out_path.with_suffix(".aiff")
        _run(["say", "-o", str(aiff), text])
        _run(["ffmpeg", "-y", "-i", str(aiff), "-ar", "44100", "-ac", "2", str(out_path)])
        aiff.unlink(missing_ok=True)
        return ffprobe_duration(out_path)


def concat_audio(wavs: list[Path], out: Path) -> None:
    """Join per-beat wavs into one continuous narration track (the `say` offline path)."""
    inputs: list[str] = []
    for w in wavs:
        inputs += ["-i", str(w)]
    n = len(wavs)
    fc = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[a]", str(out)])
