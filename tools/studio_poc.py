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

import base64
import json
import os
import subprocess
import sys
import textwrap
import time
import wave
from collections.abc import Sequence
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


from studio import (  # noqa: E402
    gemini,
    huggingface,
)
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


class GeminiImageProvider:
    """Real images via Gemini 2.5 Flash Image ("Nano Banana"). Needs GEMINI_API_KEY + billing.

    Passes optional reference images (REF-1 character sheet, REF-2 expressions) so the recurring
    stick-figure stays on-model across scenes. Flat ~$0.039/image. Pure request/parse logic lives in
    `studio.gemini`; this is the thin httpx side-effect wrapper with billing-aware retry/backoff.
    """

    name = "gemini"

    def __init__(
        self,
        model: str | None = None,
        aspect_ratio: str | None = gemini.DEFAULT_ASPECT_RATIO,
        max_retries: int = 4,
    ) -> None:
        self.model = model or os.environ.get("GEMINI_IMAGE_MODEL", gemini.DEFAULT_IMAGE_MODEL)
        self.aspect_ratio = aspect_ratio
        self.max_retries = max_retries

    def generate(self, prompt: str, out_path: Path, refs: Sequence[Path] = ()) -> Path:
        import httpx

        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("Set GEMINI_API_KEY in .env (and enable billing) to use Gemini images.")
        ref_b64 = [gemini.encode_image(Path(r).read_bytes()) for r in refs]
        body = gemini.build_request(prompt, ref_b64, self.aspect_ratio)
        url = gemini.endpoint(self.model, key)

        for attempt in range(self.max_retries):
            try:
                resp = httpx.post(url, headers={"Content-Type": "application/json"}, json=body, timeout=120)
            except httpx.RequestError as err:  # disconnect / timeout — transient, retry
                if attempt == self.max_retries - 1:
                    raise RuntimeError(f"Gemini network {type(err).__name__} after retries") from err
                time.sleep(min(2**attempt, 30))
                continue
            try:
                out_path.write_bytes(gemini.parse_image(resp.json()))
                return out_path
            except gemini.GeminiError as err:
                if err.is_billing:
                    raise RuntimeError(
                        "Gemini billing problem — top up / enable pay-as-you-go at "
                        f"https://ai.studio/projects. ({err.api_message[:160]})"
                    ) from err
                if not err.is_retryable or attempt == self.max_retries - 1:
                    raise
                time.sleep(2**attempt)  # backoff on transient 429/5xx
        raise RuntimeError("unreachable")  # pragma: no cover


class HuggingFaceImageProvider:
    """Free-tier images via HuggingFace Inference (FLUX.1-schnell). Needs HUGGINGFACE_TOKEN.

    Text-to-image only (no reference conditioning) → used for shots that DON'T need the recurring
    character: concept/map shots and the trivial cutaway symbols. `refs` are ignored.
    """

    name = "hf"

    def __init__(self, model: str | None = None, max_retries: int = 4) -> None:
        self.model = model or os.environ.get("HF_IMAGE_MODEL", huggingface.DEFAULT_MODEL)
        self.max_retries = max_retries

    def generate(self, prompt: str, out_path: Path, refs: Sequence[Path] = ()) -> Path:
        import httpx

        token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        if not token:
            raise RuntimeError("Set HUGGINGFACE_TOKEN in .env to use HuggingFace images.")
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        body = huggingface.request_body(prompt)
        last = "no endpoint tried"
        for url in huggingface.endpoints(self.model):
            for attempt in range(self.max_retries):
                resp = httpx.post(url, headers=headers, json=body, timeout=120)
                if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image"):
                    out_path.write_bytes(resp.content)
                    return out_path
                if resp.status_code == 503:  # model loading — back off and retry
                    time.sleep(2**attempt)
                    continue
                last = f"{resp.status_code} {resp.text[:150]}"
                break  # try the next endpoint
        raise RuntimeError(f"HuggingFace image failed ({self.model}): {last}")


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


class CartesiaVoiceProvider:
    """Real Cartesia TTS (Sonic). Needs CARTESIA_API_KEY (set) + CARTESIA_VOICE_ID (Carson)."""

    name = "cartesia"

    def synthesize(self, text: str, out_path: Path) -> float:
        import httpx

        key = os.environ.get("CARTESIA_API_KEY")
        voice = os.environ.get("CARTESIA_VOICE_ID")
        if not key or not voice:
            raise RuntimeError(
                "Set CARTESIA_API_KEY (present) and CARTESIA_VOICE_ID=<Carson's id> in .env to use Cartesia."
            )
        model = os.environ.get("CARTESIA_TTS_MODEL", "sonic-2")
        resp = httpx.post(
            "https://api.cartesia.ai/tts/bytes",
            headers={"X-API-Key": key, "Cartesia-Version": "2024-11-13",
                     "Content-Type": "application/json"},
            json={
                "model_id": model, "transcript": text,
                "voice": {"mode": "id", "id": voice},
                "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": 44100},
            },
            timeout=60,
        )
        resp.raise_for_status()
        out_path.write_bytes(resp.content)
        return ffprobe_duration(out_path)


class CartesiaTimestampVoice:
    """One-shot Cartesia SSE synth of the WHOLE script → (wav on disk, per-word start/end arrays).

    Uses `/tts/sse` with ``add_timestamps`` so the entire narration is spoken in a single request
    (natural prosody) and we get the real word timings that drive image cuts + captions. Native
    ``generation_config.speed`` slows delivery (no atempo artifacts); timestamps track the slowed audio.
    """

    name = "cartesia-sse"

    def synthesize(
        self, text: str, out_path: Path
    ) -> tuple[list[str], list[float], list[float]]:
        import httpx

        key = os.environ.get("CARTESIA_API_KEY")
        voice = os.environ.get("CARTESIA_VOICE_ID")
        if not key or not voice:
            raise RuntimeError("Set CARTESIA_API_KEY and CARTESIA_VOICE_ID (Carson) in .env.")
        model = os.environ.get("CARTESIA_SSE_MODEL", "sonic-2")
        speed = max(0.6, min(1.5, float(os.environ.get("CARTESIA_SPEED", "0.88"))))
        body = {
            "model_id": model, "transcript": text,
            "voice": {"mode": "id", "id": voice},
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
        with wave.open(str(out_path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)  # pcm_s16le
            w.setframerate(SAMPLE_RATE)
            w.writeframes(bytes(pcm))
        if not ends:  # no timestamps came back → one full-length span
            dur = len(pcm) / 2 / SAMPLE_RATE
            words, starts, ends = [text], [0.0], [dur]
        return words, starts, ends


def concat_audio(wavs: list[Path], out: Path) -> None:
    """Join per-beat wavs into one continuous narration track (the `say` offline path)."""
    inputs: list[str] = []
    for w in wavs:
        inputs += ["-i", str(w)]
    n = len(wavs)
    fc = "".join(f"[{i}:a]" for i in range(n)) + f"concat=n={n}:v=0:a=1[a]"
    _run(["ffmpeg", "-y", *inputs, "-filter_complex", fc, "-map", "[a]", str(out)])


def load_channel_refs() -> list[Path]:
    """The committed character references passed on character/wide shots (if present)."""
    return [p for p in (REFS_DIR / "character.png", REFS_DIR / "expressions.png") if p.exists()]
