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

import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import textwrap
import time
import unicodedata
import wave
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv  # noqa: E402

from studio import (  # noqa: E402
    DEMO_STORYBOARD,
    RunRecorder,
    agnes,
    align_beats_to_words,
    build_transcript,
    caption_timeline,
    cloudflare,
    emphasis_timeline,
    frames_for_span,
    gemini,
    huggingface,
    image_timeline,
    shot_uses_character,
    storyboard_from_dict,
    styled_prompt,
)
from studio.run_log import RunSettings, RunStats  # noqa: E402
from studio.style import LOCKED_STYLE, PALETTE  # noqa: E402
from tools.render.assemble import assemble  # noqa: E402
from tools.render.ffmpeg import subtitle_backend  # noqa: E402
from tools.render.segments import render_segment  # noqa: E402

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


# Key-fact callouts use a casual handwritten face (Schoolbell, OFL — committed to assets/fonts/);
# fall back to an installed hand-drawn font, then anything, so a missing file never breaks a run.
_CALLOUT_FONT_CANDIDATES = [
    str(_ROOT / "assets/fonts/Schoolbell.ttf"),
    "/System/Library/Fonts/Supplemental/Chalkduster.ttf",
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
]


def _callout_fontfile() -> str | None:
    return next((f for f in _CALLOUT_FONT_CANDIDATES if os.path.exists(f)), None) or _fontfile()


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
    uses_refs = False

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
    uses_refs = True  # multi-reference conditioning on every character/wide shot

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
    uses_refs = False  # text-to-image only — `refs` are ignored

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


class CloudflareImageProvider:
    """Cloudflare Workers AI **FLUX.2 [dev]** — text-to-image + up to 4 reference images for
    character consistency (the Cloudflare-billed counterpart to Gemini). Needs CLOUDFLARE_ACCOUNT_ID
    + CLOUDFLARE_API_TOKEN.

    `refs` (REF-1 character sheet, REF-2 expressions) are downscaled to < 512px and sent as
    ``input_image_0..N`` in a multipart request, so the recurring stick-figure stays on-model. Pure
    endpoint/parse logic lives in ``studio.cloudflare``; this is the httpx side-effect wrapper.
    """

    name = "cloudflare"
    uses_refs = True  # up to 4 input images for character consistency

    # FLUX.2 [dev] is popular + capacity-constrained (frequent 429 "capacity exceeded" / 424 routing),
    # and each generation is slow (~1-2 min under load), so retry generously — rejections are instant.
    def __init__(self, model: str | None = None, steps: int | None = None, max_retries: int = 6):
        self.model = model or os.environ.get("CF_IMAGE_MODEL", cloudflare.DEFAULT_IMAGE_MODEL)
        self.steps = steps or int(os.environ.get("CF_FLUX_STEPS", cloudflare.DEFAULT_STEPS))
        self.width = int(os.environ.get("CF_IMAGE_WIDTH", cloudflare.DEFAULT_WIDTH))
        self.height = int(os.environ.get("CF_IMAGE_HEIGHT", cloudflare.DEFAULT_HEIGHT))
        self.max_retries = max_retries

    def _reference_jpeg(self, path: Path) -> bytes:
        """Downscale a reference image to < 512px (FLUX.2's input limit) as JPEG bytes."""
        import io

        from PIL import Image

        im = Image.open(path).convert("RGB")
        im.thumbnail((cloudflare.REFERENCE_MAX_DIM, cloudflare.REFERENCE_MAX_DIM))
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    def generate(self, prompt: str, out_path: Path, refs: Sequence[Path] = ()) -> Path:
        import httpx

        acct = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
        token = os.environ.get("CLOUDFLARE_API_TOKEN")
        if not acct or not token:
            raise RuntimeError(
                "Set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN in .env to use Cloudflare Workers AI."
            )
        url = cloudflare.run_endpoint(acct, self.model)
        # multipart: scalar fields as (None, value), each reference as a file part input_image_N.
        parts: list = [
            ("prompt", (None, prompt)),
            ("steps", (None, str(self.steps))),
            ("width", (None, str(self.width))),
            ("height", (None, str(self.height))),
        ]
        for i, r in enumerate(list(refs)[: cloudflare.MAX_REFERENCE_IMAGES]):
            parts.append((f"input_image_{i}", (f"ref_{i}.jpg", self._reference_jpeg(Path(r)), "image/jpeg")))
        headers = {"Authorization": f"Bearer {token}"}

        for attempt in range(self.max_retries):
            resp = httpx.post(url, headers=headers, files=parts, timeout=300)
            ctype = resp.headers.get("content-type", "")
            if resp.status_code == 200 and ctype.startswith("image/"):
                out_path.write_bytes(resp.content)
                return out_path
            if resp.status_code == 200 and ctype.startswith("application/json"):
                out_path.write_bytes(cloudflare.parse_image(resp.json()))  # base64 in result.image
                return out_path
            # 424 = "could not route request to AI model" (transient Workers AI routing/warmup).
            if resp.status_code in (424, 429, 500, 502, 503) and attempt < self.max_retries - 1:
                time.sleep(min(2**attempt, 8))  # transient overload / model warmup / routing
                continue
            raise RuntimeError(
                f"Cloudflare Workers AI image failed ({self.model}): {resp.status_code} {resp.text[:200]}"
            )
        raise RuntimeError("unreachable")  # pragma: no cover


class AgnesImageProvider:
    """Agnes Image 2.1 Flash (Sapiens AI) — text-to-image + image-to-image. Needs AGNES_API_KEY.

    Free/fast/on-style and OpenAI-compatible. When `refs` are supplied (character/wide shots) it does
    **image-to-image** off the reference(s) for consistency; otherwise plain text-to-image. Has an
    **RPM limit**, so requests retry with backoff (honouring ``Retry-After``) on 429 / 5xx AND on
    network errors (disconnect/timeout) — important for long, many-frame runs. Pure request/parse
    logic lives in ``studio.agnes``.
    """

    name = "agnes"

    #: Documented free-tier rate limit (wiki.agnes-ai.com error codes): 20 requests / minute.
    FREE_RPM = 20

    def __init__(self, model: str | None = None, size: str | None = None, max_retries: int = 8):
        self.model = model or os.environ.get("AGNES_IMAGE_MODEL", agnes.DEFAULT_MODEL)
        self.size = size or os.environ.get("AGNES_SIZE", agnes.DEFAULT_SIZE)
        self.max_retries = int(os.environ.get("AGNES_MAX_RETRIES", max_retries))
        # Floor delay between request STARTS so we never exceed the RPM limit (60/RPM = 3s at RPM 20),
        # even when retries would otherwise burst. Serial gen is already ~15-30s/call so this rarely bites.
        default_interval = 60.0 / max(1, self.FREE_RPM)
        self.min_interval = float(os.environ.get("AGNES_MIN_INTERVAL", str(default_interval)))
        self._last_call = 0.0
        # Agnes's image-to-image (reference-upload) path is unreliable/slow — it hangs where plain
        # text-to-image succeeds. Default to text-to-image (ignore refs); set AGNES_IMG2IMG=1 to
        # re-enable. This is per-INSTANCE, not per-provider-name: with it off Agnes consumes no
        # reference image at all, and callers must not claim (or warn about) ref conditioning.
        self.uses_refs = os.environ.get("AGNES_IMG2IMG", "0") == "1"

    def _data_uri(self, path: Path) -> str:
        """A reference image as a base64 PNG data URI (downscaled to keep the payload sane)."""
        import base64 as _b64
        import io

        from PIL import Image

        im = Image.open(path).convert("RGB")
        im.thumbnail((1024, 1024))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return "data:image/png;base64," + _b64.b64encode(buf.getvalue()).decode()

    def _build_body(self, prompt: str, refs: Sequence[Path]) -> dict:
        if refs and self.uses_refs:  # character/wide → image-to-image off the reference(s)
            return agnes.image_to_image_body(
                prompt, [self._data_uri(Path(r)) for r in refs], self.size, self.model
            )
        # text-to-image (reliable path); consistency comes from the prompt + locked style
        return agnes.text_to_image_body(prompt, self.size, self.model)

    def _request_bytes(self, headers: dict, body: dict) -> bytes:
        """POST ONE prompt and return the image bytes. Retries 429 / 5xx / network errors with
        backoff (honouring the RPM throttle); raises :class:`agnes.ContentPolicyError` when Agnes
        blocks the prompt itself (so the caller can soften + retry) and ``RuntimeError`` otherwise."""
        import httpx

        if self.min_interval > 0:  # throttle to stay under the per-minute rate limit
            gap = self.min_interval - (time.monotonic() - self._last_call)
            if gap > 0:
                time.sleep(gap)

        last = "no attempt made"
        for attempt in range(self.max_retries):
            self._last_call = time.monotonic()
            try:
                resp = httpx.post(agnes.ENDPOINT, headers=headers, json=body, timeout=360)
            except httpx.RequestError as err:  # disconnect / timeout / connect / read — all transient
                last = f"network {type(err).__name__}"
                if attempt == self.max_retries - 1:
                    break
                time.sleep(min(2**attempt, 30))
                continue
            if resp.status_code == 200:
                img, url = agnes.extract(resp.json())
                if img is None and url:  # URL output → fetch the bytes
                    img = httpx.get(url, timeout=120).content
                return img
            if resp.status_code == 429 or resp.status_code >= 500:  # RPM rate limit / transient 5xx
                last = f"{resp.status_code} {resp.text[:120]}"
                if attempt == self.max_retries - 1:
                    break
                # 429 = RPM limit: honour Retry-After, else back off up to ~60s (docs: "wait 1 minute").
                # 5xx = transient: shorter backoff.
                retry_after = resp.headers.get("retry-after") or resp.headers.get("x-ratelimit-reset")
                cap = 60 if resp.status_code == 429 else 30
                wait = float(retry_after) if retry_after else min(2 ** (attempt + 2), cap)
                time.sleep(wait)
                continue
            # Non-retryable HTTP. A prompt content-policy block is special — signal the caller to
            # soften the prompt and try again (a plain retry of the same prompt just fails again).
            try:
                detail: dict | str = resp.json()
            except ValueError:
                detail = resp.text
            if agnes.is_content_policy_error(resp.status_code, detail):
                raise agnes.ContentPolicyError(resp.text[:200])
            raise RuntimeError(f"Agnes image failed: {resp.status_code} {resp.text[:200]}")
        raise RuntimeError(f"Agnes image failed after {self.max_retries} attempts: {last}")

    def generate(self, prompt: str, out_path: Path, refs: Sequence[Path] = ()) -> Path:
        key = os.environ.get("AGNES_API_KEY")
        if not key:
            raise RuntimeError("Set AGNES_API_KEY in .env to use Agnes images.")
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        # Try the original prompt first; if Agnes blocks it on CONTENT POLICY, retry with a
        # progressively softened prompt (graphic words neutralised + a safety note) instead of
        # failing the run — a plain retry of the same prompt would only be blocked again.
        variants = [prompt] + [agnes.soften_prompt(prompt, lvl) for lvl in (1, 2, 3)]
        for vi, variant in enumerate(variants):
            try:
                img = self._request_bytes(headers, self._build_body(variant, refs))
            except agnes.ContentPolicyError:
                if vi == len(variants) - 1:
                    raise agnes.ContentPolicyError(
                        "Agnes blocked this prompt on content policy even after softening it "
                        f"{len(variants) - 1}x; the subject is likely too graphic to depict."
                    ) from None
                print(
                    "  ⚠ Agnes content-policy block — softening the prompt & retrying "
                    f"(attempt {vi + 2}/{len(variants)})",
                    file=sys.stderr,
                )
                continue
            out_path.write_bytes(img)
            return out_path
        raise RuntimeError("unreachable")  # pragma: no cover


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


# ── FFmpeg motion + assembly ─────────────────────────────────────────────────
# Punctuation the LLM/TTS emit that the caption font lacks a glyph for -> ASCII (else tofu box).
_CAPTION_SUBST = {
    0x2011: "-", 0x2013: "-", 0x2014: "-",  # non-breaking / en / em dashes
    0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"',  # curly quotes
    0x2026: "...",  # ellipsis
}


def _clean_caption(text: str) -> str:
    """Map exotic unicode punctuation to ASCII so the overlay font renders it (no tofu boxes)."""
    # Any unicode space-separator (Zs: no-break U+00A0, narrow U+202F, thin U+2009) or zero-width
    # format char (Cf: BOM, ZWSP) -> a plain space; then map dashes/quotes/ellipsis by code point.
    folded = "".join(
        " " if unicodedata.category(ch) in ("Zs", "Cf") else ch for ch in text
    )
    return folded.translate(_CAPTION_SUBST)


#: The callout box, as fractions of the frame: a wide, short band the text word-wraps inside.
_CALLOUT_BOX_WF, _CALLOUT_BOX_HF = 0.42, 0.16
#: Search bounds (frame fractions): stay out of the bottom subtitle band and off the very edges.
_CALLOUT_TOP_MARGIN, _CALLOUT_SIDE_MARGIN, _CALLOUT_SUBTITLE_TOP = 0.05, 0.03, 0.74
#: Above this local roughness (grayscale std, 0-255) even the flattest region is too busy for
#: text — the caller then falls back to a sensible default spot (still text-only, no card).
_CALLOUT_MAX_STD = 34.0
#: Cap the scan resolution: big enough to preserve real detail/noise (so busy frames score busy),
#: small enough to stay fast. Frames are only downscaled if larger than this on the long side.
_CALLOUT_SCAN_MAX_DIM = 1280


def _pick_callout_zone(base_image: Path) -> tuple[int, int, int, int] | None:
    """Find the emptiest (flattest) region of the frame to drop the callout onto — returns an
    (x, y, w, h) box in OUTPUT-frame pixels, or None when even the best region is too busy (the
    caller then uses a default spot).

    Rather than a handful of fixed candidate zones, this slides the callout box across the whole
    usable area (above the subtitle band) and scores every position by local *flatness* using an
    integral image (summed-area table) so each window's mean/variance is O(1). Flat, uncluttered
    areas — an empty sky, a plain wall — win; busy/inky areas lose. A mild bonus prefers lighter
    regions and the sides/top (the subject usually sits low-center), but flatness dominates so the
    text lands on genuine whitespace, wherever it actually is in this particular image."""
    import numpy as np
    from PIL import Image

    try:
        im = Image.open(base_image).convert("L")
    except (OSError, ValueError):
        return None
    if max(im.size) > _CALLOUT_SCAN_MAX_DIM:  # bound cost; only downscale oversized frames
        im.thumbnail((_CALLOUT_SCAN_MAX_DIM, _CALLOUT_SCAN_MAX_DIM))
    arr = np.asarray(im, dtype=np.float64)
    sh, sw = arr.shape
    wpx, hpx = max(1, int(_CALLOUT_BOX_WF * sw)), max(1, int(_CALLOUT_BOX_HF * sh))

    # Summed-area tables of values and squared values → O(1) window sum for mean + variance.
    ii = np.zeros((sh + 1, sw + 1))
    ii2 = np.zeros((sh + 1, sw + 1))
    ii[1:, 1:] = arr.cumsum(0).cumsum(1)
    ii2[1:, 1:] = (arr * arr).cumsum(0).cumsum(1)

    def _win(table, y0, x0):  # sum over [y0:y0+hpx, x0:x0+wpx]
        return (table[y0 + hpx, x0 + wpx] - table[y0, x0 + wpx]
                - table[y0 + hpx, x0] + table[y0, x0])

    y_lo, x_lo = int(_CALLOUT_TOP_MARGIN * sh), int(_CALLOUT_SIDE_MARGIN * sw)
    y_hi = int(_CALLOUT_SUBTITLE_TOP * sh) - hpx
    x_hi = sw - wpx - int(_CALLOUT_SIDE_MARGIN * sw)
    n = wpx * hpx
    ystep, xstep = max(1, hpx // 3), max(1, wpx // 4)

    best, best_score, best_std = None, float("-inf"), 0.0
    for y0 in range(y_lo, max(y_lo, y_hi) + 1, ystep):
        for x0 in range(x_lo, max(x_lo, x_hi) + 1, xstep):
            mean = _win(ii, y0, x0) / n
            std = (max(0.0, _win(ii2, y0, x0) / n - mean * mean)) ** 0.5
            cx, cy = (x0 + wpx / 2) / sw, (y0 + hpx / 2) / sh
            # Flatness (−std) dominates; small nudges toward lighter, off-center, upper regions.
            score = -std + (mean / 255) * 8 + abs(cx - 0.5) * 12 + (1 - cy) * 6
            # Avoid the horizontal center (middle 35%) where character head/body stands
            if 0.325 <= cx <= 0.675:
                score -= 100.0
            if score > best_score:
                best_score, best, best_std = score, (x0 / sw, y0 / sh), std
    if best is None:
        return None
    fx, fy = best
    is_busy = bool(best_std > _CALLOUT_MAX_STD)
    return (int(fx * W), int(fy * H), int(_CALLOUT_BOX_WF * W), int(_CALLOUT_BOX_HF * H), is_busy)


def _fit_callout_text(draw, text: str, font_path: str | None, max_w: int, max_h: int):
    """Largest font size (Schoolbell) at which `text` word-wraps inside (max_w, max_h). Returns
    (lines, font, line_height)."""
    from PIL import ImageFont

    for size in range(112, 42, -6):
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        words, lines, cur = text.split(), [], ""
        for wd in words:
            trial = f"{cur} {wd}".strip()
            if draw.textlength(trial, font=font) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = wd
        if cur:
            lines.append(cur)
        line_h = int(size * 1.25)
        widest = max((draw.textlength(ln, font=font) for ln in lines), default=0)
        if (widest <= max_w and line_h * len(lines) <= max_h) or font_path is None:
            return lines, font, line_h
    font = ImageFont.truetype(font_path, 44) if font_path else ImageFont.load_default()
    return [text], font, 54


def make_emphasis_png(text: str, out: Path, base_image: Path | None = None) -> None:
    """Render a full-frame transparent key-fact callout.

    If the selected zone is too busy, a hand-drawn paper card is drawn behind the text to guarantee
    legibility. Safe off-center fallback is used if no image is available.
    """
    from PIL import Image, ImageDraw

    text = _clean_caption(text).strip()
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ff = _callout_fontfile()

    zone_res = _pick_callout_zone(base_image) if base_image else None
    if zone_res is None:
        # Default off-center fallback (top-left) if no image or scan failed
        zw, zh = int(W * 0.42), int(H * 0.16)
        zx, zy = int(W * 0.05), int(H * 0.07)
        is_busy = False
    else:
        zx, zy, zw, zh, is_busy = zone_res

    # Draw a wobbly hand-drawn paper card background if the zone is busy
    if is_busy:
        import random
        pad = 12
        rx0, ry0 = zx + pad, zy + pad
        rx1, ry1 = zx + zw - pad, zy + zh - pad
        
        # Subdivide rectangle edges to make them wobbly
        points = []
        for x in range(rx0, rx1 + 1, 40):
            points.append((x, ry0 + random.randint(-4, 4)))
        for y in range(ry0 + 40, ry1 + 1, 40):
            points.append((rx1 + random.randint(-4, 4), y))
        for x in range(rx1 - 40, rx0 - 1, -40):
            points.append((x, ry1 + random.randint(-4, 4)))
        for y in range(ry1 - 40, ry0 - 1, -40):
            points.append((rx0 + random.randint(-4, 4), y))
            
        # Draw the filled paper card (translucent off-white)
        d.polygon(points, fill=(244, 240, 232, 230))
        
        # Draw a sketchy double outline
        for _ in range(2):
            outline_points = []
            for pt in points:
                outline_points.append((pt[0] + random.randint(-1, 1), pt[1] + random.randint(-1, 1)))
            d.polygon(outline_points, outline=(40, 40, 40, 225), width=2)

    lines, font, line_h = _fit_callout_text(d, text, ff, zw - 48, zh - 24)
    block_h = line_h * len(lines)
    top = zy + (zh - block_h) // 2
    cx = zx + zw // 2

    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text((cx - w / 2, top), ln, font=font, fill=(20, 20, 20, 255),
               stroke_width=4, stroke_fill=(255, 255, 255, 235))
        top += line_h
    im.save(out)


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


def build_narration(
    scenes, voice, out_dir: Path
) -> tuple[Path, list[tuple[float, float]], list[str], list[float], list[float]]:
    """Synthesize the whole script and return ``(continuous_wav, per-beat (start,end) spans, words,
    word_starts, word_ends)``.

    Cartesia → one SSE request with word timestamps → spans snapped to real speech pauses, plus the
    per-word text/timings themselves (used downstream to word-anchor captions in
    ``caption_timeline``). Any other voice (e.g. macOS ``say``, offline) → synth each beat, concat
    into one wav, spans = cumulative per-beat durations, and no word data (empty lists — captions
    fall back to proportional spreading). Either way the assembler gets a single continuous audio +
    one span per beat.
    """
    narrations = [s.narration for s in scenes]
    wav = out_dir / "narration.wav"
    if voice.name == "cartesia":
        transcript = build_transcript(narrations)
        words, starts, ends = CartesiaTimestampVoice().synthesize(transcript, wav)
        # Anchor each beat to the REAL spoken word where its text ends (accurate; the old
        # character-proportional align_beats drifted up to ~3.5s mid-video).
        spans = align_beats_to_words(narrations, words, starts, ends)
        return wav, spans, words, starts, ends

    per_beat: list[Path] = []
    spans: list[tuple[float, float]] = []
    t = 0.0
    for i, text in enumerate(narrations):
        w = out_dir / f"narr_{i}.wav"
        voice.synthesize(text, w)
        dur = ffprobe_duration(w)
        spans.append((round(t, 3), round(t + dur, 3)))
        t += dur
        per_beat.append(w)
    concat_audio(per_beat, wav)
    return wav, spans, [], [], []


BEAT_SPANS_NAME = "beat_spans.json"
WORD_TIMINGS_NAME = "word_timings.json"


def _save_beat_spans(out_dir: Path, spans: list[tuple[float, float]]) -> None:
    """Persist the per-beat (start,end) spans so a resume reuses the exact timings (no re-synth)."""
    (out_dir / BEAT_SPANS_NAME).write_text(
        json.dumps([[round(s, 3), round(e, 3)] for s, e in spans])
    )


def _load_beat_spans(out_dir: Path) -> list[tuple[float, float]] | None:
    """The saved beat spans for a run, or None if absent/unreadable (fall back to re-synthesis)."""
    path = out_dir / BEAT_SPANS_NAME
    if not path.is_file():
        return None
    try:
        return [(float(s), float(e)) for s, e in json.loads(path.read_text())]
    except (ValueError, TypeError):
        return None


def _save_word_timings(
    out_dir: Path, words: Sequence[str], word_starts: Sequence[float], word_ends: Sequence[float]
) -> None:
    """Persist Cartesia's per-word text + timings alongside the beat spans, so the approve-time
    assemble path can word-anchor captions too (see ``studio.narration.caption_timeline``). The
    ``say`` voice has no word data, so this writes empty lists — treated as "unavailable" on load.
    """
    (out_dir / WORD_TIMINGS_NAME).write_text(
        json.dumps({
            "words": list(words),
            "word_starts": [round(float(s), 3) for s in word_starts],
            "word_ends": [round(float(e), 3) for e in word_ends],
        })
    )


def _load_word_timings(out_dir: Path) -> tuple[list[str], list[float], list[float]]:
    """The saved per-word timings for a run, or empty lists if absent/unreadable/never captured
    (offline ``say`` voice) — ``caption_timeline`` treats empty word data as "fall back to
    proportional spreading"."""
    path = out_dir / WORD_TIMINGS_NAME
    if not path.is_file():
        return [], [], []
    try:
        data = json.loads(path.read_text())
        return (
            [str(w) for w in data["words"]],
            [float(s) for s in data["word_starts"]],
            [float(e) for e in data["word_ends"]],
        )
    except (ValueError, TypeError, KeyError):
        return [], [], []


def wants_refs(provider) -> bool:
    """Does THIS provider instance actually consume reference images?

    Read off the instance (``uses_refs``), never off the provider NAME: Agnes only conditions on a
    reference when ``AGNES_IMG2IMG=1``, so a name-based check claimed ref-conditioned consistency
    for the default Agnes setup that never sends a reference at all — and told the user to generate
    ref sheets that would then be ignored. Unknown/duck-typed providers default to False.
    """
    return bool(getattr(provider, "uses_refs", False))

#: Every selectable image provider by name → constructor. `cloudflare` (slow/capacity-unreliable)
#: and `hf` (weaker quality) are kept working but are NOT offered on the dashboard picker — Gemini
#: and Agnes are the recommended providers (see context/project/roadmap.md).
IMAGE_PROVIDERS = {
    "placeholder": PlaceholderImageProvider,
    "gemini": GeminiImageProvider,
    "agnes": AgnesImageProvider,
    "hf": HuggingFaceImageProvider,
    "cloudflare": CloudflareImageProvider,
}
IMAGE_PROVIDER_NAMES = tuple(IMAGE_PROVIDERS)


class ImageProviders(NamedTuple):
    """One provider per image role. `character` gets reference images (character/wide shots);
    `concept` renders concept/map shots. Images stay text-free — there is no cutaway role."""

    character: object
    concept: object


def make_image_provider(name: str):
    """Instantiate an image provider by name (raises ValueError on an unknown name)."""
    try:
        return IMAGE_PROVIDERS[name]()
    except KeyError:
        raise ValueError(f"unknown image provider {name!r}; choose from {IMAGE_PROVIDER_NAMES}") from None


def providers_from_roles(character: str, concept: str) -> ImageProviders:
    """Build an :class:`ImageProviders` from a per-role provider-name choice (the new run page)."""
    return ImageProviders(make_image_provider(character), make_image_provider(concept))


def build_providers(mode: str) -> ImageProviders:
    """Legacy single-mode shorthand → an :class:`ImageProviders` (character / concept).

    * ``gemini``     — Gemini character + HuggingFace FLUX (free) concept.
    * ``agnes``      — Agnes for both roles (recommended: free, fast, on-style, image-to-image refs).
    * ``cloudflare`` — Cloudflare FLUX.2 [dev] character + Gemini concept. (not offered in UI)
    * ``hf``         — HuggingFace FLUX for both (free, no character consistency). (not in UI)
    * else           — Placeholder (free/offline default).
    """
    if mode == "gemini":
        return ImageProviders(GeminiImageProvider(), HuggingFaceImageProvider())
    if mode == "agnes":
        return providers_from_roles("agnes", "agnes")
    if mode == "cloudflare":
        return ImageProviders(CloudflareImageProvider(), GeminiImageProvider())
    if mode == "hf":
        return providers_from_roles("hf", "hf")
    return providers_from_roles("placeholder", "placeholder")


def attach_script_artifacts(rec: RunRecorder, storyboard_path: Path) -> None:
    """Copy a generated script's sibling artifacts into the run dir + record them on the manifest."""
    src_dir = Path(storyboard_path).parent
    copied: dict[str, Path] = {}
    for name, key in (
        ("storyboard.json", "script"),
        ("sources.json", "sources"),
        ("qc.md", "qc"),
        ("script_prompt.txt", "prompt"),
        ("rubric.json", "rubric"),
    ):
        p = src_dir / name
        if p.is_file():
            dest = rec.dir / name
            if p.resolve() != dest.resolve():  # skip when resuming from the run's own artifacts
                shutil.copy(p, dest)
            copied[key] = dest
    rec.attach_artifacts(**copied)
    rec.log(f"attached script artifacts: {', '.join(copied) or 'none'}")


def _generate_frame(provider, styled, target, refs, fallback, rec, i, k):
    """Generate one frame; if the primary provider fails (e.g. a Gemini safety refusal on a prompt),
    fall back to a secondary provider so one bad frame never kills a long run."""
    try:
        provider.generate(styled, target, refs)
    except Exception as err:
        if fallback is None:
            raise
        rec.log(f"scene {i} frame {k}: {provider.name} failed ({err}); falling back to {fallback.name}")
        fallback.generate(styled, target, refs)


def _frame_name(i: int, k: int) -> str:
    """The on-disk name for beat ``i``'s ``k``-th frame (``img_i.png`` / ``img_i_k.png``)."""
    return f"img_{i}.png" if k == 0 else f"img_{i}_{k}.png"


def _frame_prompt(styled: str, k: int) -> str:
    """The prompt for beat frame ``k``. ``k == 0`` is the base image; each extra frame (a "fire
    spot" / intense beat shows two) must be a CLEARLY different shot of the SAME scene so the
    on-screen switch reads as a real cut, not a near-duplicate — a different camera distance/angle
    and a different moment, pose and action, same characters and style."""
    if k == 0:
        return styled
    return (
        f"{styled} This is a DIFFERENT shot of the SAME scene, characters and art style — change "
        f"the camera distance and angle and show a distinctly different moment, pose and action "
        f"from the other frame (variation {k}): a clearly different composition, NOT a near-duplicate."
    )


#: Numbers-only reference envelope (see context/project/style-envelope.json's `_provenance` for
#: the calibration story). Loading it here — not importing tools.style_check.load_envelope — keeps
#: this module free of a dependency on that CLI (which itself lazily imports FROM this module, to
#: pick a provider; a two-way top-level import would be circular).
_STYLE_ENVELOPE_PATH = _ROOT / "context" / "project" / "style-envelope.json"


def _load_style_envelope():
    """The measured reference envelope `studio.style_metrics.conforms` scores a frame against."""
    from studio.style_metrics import Envelope

    raw = json.loads(_STYLE_ENVELOPE_PATH.read_text())
    return Envelope(
        saturation=tuple(raw["saturation"]),
        colour_bins=tuple(raw["colour_bins"]),
        near_white_pct=tuple(raw["near_white_pct"]),
    )


def _style_preflight(rec, sb, images: ImageProviders, channel_refs, skip_style_check: bool) -> None:
    """Pre-flight style gate: measure scene 0's frame against the reference envelope and abort
    BEFORE the main image loop if it has drifted outside — refusing a run that would otherwise pay
    for ~200 off-style Agnes images before anyone notices the art has drifted. Reuses scene 0's
    frame off disk when a prior invocation (e.g. ``--resume``) already generated it, rather than
    paying for a second probe of the same shot. ``skip_style_check`` is the informed-operator
    escape hatch (mirrors ``--skip-rubric`` in tools/make_script.py): it skips the probe
    entirely, since generating one is itself a paid call.
    """
    if skip_style_check or not sb.scenes:
        return
    import numpy as np
    from PIL import Image

    from studio.style_metrics import conforms, measure_frame

    sc0 = sb.scenes[0]
    is_char = shot_uses_character(sc0.shot_type)
    provider = images.character if is_char else images.concept
    refs = channel_refs if is_char else []

    existing = rec.dir / _frame_name(0, 0)
    generated = not existing.is_file()
    if generated:
        styled = styled_prompt(
            sc0.image_prompt, sb.style, use_character_ref=bool(refs), shot_type=sc0.shot_type
        )
        probe_path = rec.dir / "style_probe.png"
        rec.log(f"style pre-flight: generating probe frame ({provider.name}) before the image loop…")
        provider.generate(styled, probe_path, refs)
    else:
        probe_path = existing
        rec.log("style pre-flight: reusing scene 0's frame already on disk (no new spend)")

    try:
        metrics = measure_frame(np.asarray(Image.open(probe_path).convert("RGB")))
    finally:
        if generated:
            probe_path.unlink(missing_ok=True)

    ok, failures = conforms(metrics, _load_style_envelope())
    if ok:
        rec.log("style pre-flight: PASS — probe frame is inside the reference envelope")
        return
    msg = (
        "style pre-flight FAILED — the first frame drifted outside the reference envelope:\n  - "
        + "\n  - ".join(failures)
        + "\nRefusing to render the rest of the run (would pay for the remaining images). "
        "Fix LOCKED_STYLE and re-run, or pass --skip-style-check to render anyway."
    )
    rec.log(f"ERROR: {msg}")
    raise RuntimeError(msg)


def _record_resume_progress(rec: RunRecorder, frames_per_beat: list[int]) -> None:
    """On resume, count frames already on disk and record where generation will pick up — so the
    manifest/dashboard show truthful progress instead of looking like a fresh start."""
    total = sum(frames_per_beat)
    done = 0
    first_missing: tuple[int, int] | None = None
    for i, nfb in enumerate(frames_per_beat):
        for k in range(nfb):
            if (rec.dir / _frame_name(i, k)).is_file():
                done += 1
            elif first_missing is None:
                first_missing = (i, k)
    if first_missing is None:
        note = f"resume: all {total} frames already on disk — only re-assembling the video"
    else:
        si, sk = first_missing
        note = (f"resume: {done}/{total} frames already on disk — "
                f"continuing at scene {si + 1} (frame {sk + 1})")
    rec.resumed(note)
    print(f"  ↻ {note}")


def _assemble_video(
    rec, sb, wav, beat_spans, frames_per_beat, callout_overlays, captions,
    words: Sequence[str] = (), word_starts: Sequence[float] = (), word_ends: Sequence[float] = (),
):
    """Step 3, shared by a full render and the approve-time assemble: render every planned frame to
    its own content-hash-cached segment (`tools.render.segments.render_segment`), concat them under
    the continuous narration, and burn timed captions in one libass pass
    (`tools.render.assemble.assemble`), then mark the run complete.

    Replaces the old single-filtergraph path (`render_video`, deleted — `tools/reassemble.py` was
    the last caller and has since been migrated onto this same path) that chained one `overlay`
    node per caption cue and could not scale past a couple hundred cues.

    ``words``/``word_starts``/``word_ends`` are the real Cartesia per-word timings (empty for the
    ``say`` voice) — passed through so captions word-anchor instead of drifting proportionally.

    ``callout_overlays`` (key-fact badges) are still recorded on the manifest for the dashboard via
    ``rec.set_callouts`` upstream, but are no longer burned into the video pixels — the new
    assembler does zero PNG-overlay compositing of any kind, by design (see
    ``tools/render/assemble.py``'s module docstring)."""
    narrations = [s.narration for s in sb.scenes]
    cues = caption_timeline(
        beat_spans, narrations, words=words, word_starts=word_starts, word_ends=word_ends,
    ) if captions else []

    segments: list[Path] = []
    images_cached = 0
    for name, start, end in image_timeline(beat_spans, frames_per_beat):
        seg, was_cached = render_segment(
            rec.dir / name, end - start, rec.dir / "segments", width=W, height=H, fps=FPS,
        )
        images_cached += int(was_cached)
        segments.append(seg)

    out = rec.dir / "video.mp4"
    rec.log(f"assembling final video from {len(segments)} segment(s)…")
    assemble(
        segments, wav, cues, out, work_dir=rec.dir / "assemble_work", width=W, height=H, fps=FPS,
    )

    # RunRecorder has no public stats setter (adding one touches studio/run_log.py, owned by a
    # sibling agent right now) — write through the same `_replace` path its own public methods use.
    # `updated_at` is left to the `rec.completed(...)` call immediately below, which always follows.
    rec._replace(stats=RunStats(
        shots=len(segments),
        images_generated=len(segments) - images_cached,
        images_cached=images_cached,
        subtitle_backend=subtitle_backend(),
    ))
    total = ffprobe_duration(out)
    rec.completed(out, total)
    print(f"\n✅ {out}  ({total:.1f}s, {W}x{H})")
    rec.log(f"done → {out.name} ({total:.1f}s, {W}x{H})")
    return out


def assemble_storyboard(rec: RunRecorder, sb, captions: bool = True) -> Path:
    """Assemble the final video from the narration + frames ALREADY on disk — the "approve" step of
    the human-in-the-loop review gate. Reconstructs the exact timeline ``render_storyboard`` would
    have used (same spans, frame counts, callouts) so the result is identical to an un-paused run."""
    wav = rec.dir / "narration.wav"
    beat_spans = _load_beat_spans(rec.dir)
    if not wav.is_file() or beat_spans is None or len(beat_spans) != len(sb.scenes):
        raise RuntimeError("cannot assemble: missing narration.wav / beat_spans.json for this run")
    words, word_starts, word_ends = _load_word_timings(rec.dir)
    try:
        frames_per_beat = [
            frames_for_span(e - s, intense=sb.scenes[i].intense)
            for i, (s, e) in enumerate(beat_spans)
        ]
        callout_overlays = emphasis_timeline(
            beat_spans, [s.emphasis for s in sb.scenes], [s.narration for s in sb.scenes]
        )
        rec.set_callouts([(t, bi, st) for t, bi, st, _e in callout_overlays])
        rec.log("approved — assembling from reviewed images…")
        return _assemble_video(
            rec, sb, wav, beat_spans, frames_per_beat, callout_overlays, captions,
            words=words, word_starts=word_starts, word_ends=word_ends,
        )
    except Exception as exc:
        rec.failed(exc)
        print(f"\n❌ assemble failed: {exc}", file=sys.stderr)
        raise


def regenerate_scene(
    rec: RunRecorder, sb, images: ImageProviders, scene_index: int,
    fallback=None, prompt_override: str | None = None,
) -> None:
    """Re-draw ONE scene's image(s) during the review gate (human-in-the-loop). Overwrites
    ``img_{i}[_k].png`` in place, keeps the run in ``pending_approval`` (nothing is assembled), and
    optionally swaps in an edited prompt in place of the script's ``image_prompt``."""
    if not 0 <= scene_index < len(sb.scenes):
        raise RuntimeError(f"scene index {scene_index} out of range (0..{len(sb.scenes) - 1})")
    sc = sb.scenes[scene_index]
    beat_spans = _load_beat_spans(rec.dir)
    if beat_spans is not None and scene_index < len(beat_spans):
        s, e = beat_spans[scene_index]
        n = frames_for_span(e - s, intense=sc.intense)
    else:
        n = 1
    is_char = shot_uses_character(sc.shot_type)
    provider = images.character if is_char else images.concept
    refs = load_channel_refs() if (is_char and wants_refs(provider)) else []
    subject = (prompt_override or sc.image_prompt).strip()
    styled = styled_prompt(subject, sb.style, use_character_ref=bool(refs), shot_type=sc.shot_type)
    edited = " · edited prompt" if prompt_override else ""
    rec.log(f"regenerating scene {scene_index} ({provider.name}) · {n} frame(s){edited}")
    try:
        for k in range(n):
            target = rec.dir / _frame_name(scene_index, k)
            _generate_frame(
                provider, _frame_prompt(styled, k), target, refs, fallback, rec, scene_index, k
            )
        rec.scene_image(scene_index, rec.dir / f"img_{scene_index}.png")
        rec.pending_approval()  # stay in the review gate — the user still has to approve
        rec.log(f"scene {scene_index} regenerated — still awaiting your approval")
        print(f"  ↻ regenerated scene {scene_index}")
    except Exception as exc:
        rec.failed(exc)
        print(f"\n❌ regenerate failed: {exc}", file=sys.stderr)
        raise


def _thumbnail_subject(sb, override: str | None = None) -> str:
    """Pick a striking focal subject for the thumbnail: an explicit override, else the first intense
    character/wide scene, else the first character/wide scene, else the title."""
    if override and override.strip():
        return override.strip()
    char_scenes = [s for s in sb.scenes if shot_uses_character(s.shot_type)]
    for s in char_scenes:
        if s.intense:
            return s.image_prompt
    if char_scenes:
        return char_scenes[0].image_prompt
    return sb.title


def generate_thumbnail(
    rec: RunRecorder, sb, provider, text: str | None = None, subject: str | None = None
) -> Path:
    """Generate a YouTube thumbnail for the run: a text-free focal image (channel style, via the
    given image provider) + a big PIL title overlaid on the right. Records it on the manifest so the
    dashboard can show it. Title defaults to the run title; subject to a striking scene."""
    from studio.style import thumbnail_prompt
    from tools.make_thumbnail import overlay_title  # lazy: make_thumbnail imports this module

    title = (text or sb.title or "").strip() or "UNTITLED"
    subj = _thumbnail_subject(sb, subject)
    out = rec.dir / "thumbnail.png"
    raw = rec.dir / "thumbnail.raw.png"
    rec.log(f"generating thumbnail ({provider.name}) · text={title[:40]!r}")
    try:
        provider.generate(thumbnail_prompt(subj), raw, ())
        overlay_title(raw.read_bytes(), title, out)
        raw.unlink(missing_ok=True)
        rec.set_thumbnail(out)
        rec.log(f"thumbnail → {out.name}")
        print(f"🖼  {out}")
        return out
    except Exception as exc:
        rec.log(f"thumbnail failed: {exc}")
        print(f"\n❌ thumbnail failed: {exc}", file=sys.stderr)
        raise


def render_storyboard(
    rec: RunRecorder, sb, images: ImageProviders, voice, captions: bool = True,
    resume: bool = False, fallback=None, pause_for_review: bool = False,
    skip_style_check: bool = False,
) -> Path | None:
    """Render `sb` into `rec.dir` and return the final video path.

    One continuous narration (`build_narration`) → real per-beat spans → each beat gets one or more
    **freshly generated** frames, each held ≥ ``MIN_FRAME_HOLD`` seconds (long beats split into that
    many distinct frames) → each frame rendered to its own cached segment and concatenated under the
    narration (`_assemble_video`). Images are text-free; a beat's optional `emphasis` fact is
    recorded on the manifest (`rec.set_callouts`) for the dashboard but is no longer burned into the
    video itself; there are no cutaway frames.
    Per-role providers: `character` renders character/wide (reference-conditioned), `concept` renders
    concept/map. `resume` skips frames whose image already exists on disk (reuse a partial run);
    `fallback` is a secondary provider used when the primary refuses/fails a frame. Before the main
    image loop, a style pre-flight (`_style_preflight`) refuses the run if scene 0's frame drifts
    outside the reference envelope — unless `skip_style_check` (the informed-operator escape hatch).
    Shared by the CLI (`main`) and the dashboard's `run_pipeline`; records failure + re-raises.
    """
    # State the consistency mode plainly, once, in the run log — it silently decides how well the
    # recurring character holds across ~50 frames, and it is NOT what the provider name implies.
    char_wants_refs = wants_refs(images.character)
    channel_refs = load_channel_refs() if char_wants_refs else []
    if char_wants_refs and not channel_refs:
        msg = (f"{images.character.name} conditions on reference images but "
               f"{REFS_DIR.relative_to(_ROOT)}/character.png + expressions.png are missing — run "
               f"`python tools/make_refs.py` (needs GEMINI_API_KEY + billing) and commit them. "
               f"Falling back to prompt-only consistency for this run.")
        print(f"  ⚠ {msg}")
        rec.log(f"WARN: {msg}")
    elif char_wants_refs:
        rec.log(f"character consistency: reference-conditioned ({images.character.name}, "
                f"{len(channel_refs)} ref image(s))")
    else:
        rec.log(f"character consistency: prompt-only ({images.character.name} sends no reference "
                f"image; set AGNES_IMG2IMG=1 or use --char-model gemini to condition on refs)")
    try:
        # 1) Whole-script narration → one continuous wav + a real (start,end) span per beat. On a
        # resume, reuse the saved narration.wav + spans so timings stay identical to the frames
        # already on disk (no audio drift, no wasted TTS) instead of re-synthesising.
        wav = rec.dir / "narration.wav"
        saved_spans = _load_beat_spans(rec.dir) if resume else None
        if resume and wav.is_file() and saved_spans is not None and len(saved_spans) == len(sb.scenes):
            beat_spans = saved_spans
            words, word_starts, word_ends = _load_word_timings(rec.dir)
            rec.log(f"resume: reusing existing narration.wav + spans "
                    f"({len(beat_spans)} beats, no TTS)")
        else:
            rec.log(f"synthesising continuous narration ({voice.name})…")
            wav, beat_spans, words, word_starts, word_ends = build_narration(
                sb.scenes, voice, rec.dir
            )
            _save_beat_spans(rec.dir, beat_spans)
            _save_word_timings(rec.dir, words, word_starts, word_ends)
        total_audio = beat_spans[-1][1] if beat_spans else 0.0
        rec.log(f"narration {total_audio:.1f}s · {len(beat_spans)} beats")

        # 2) Per beat: split its span into ≥8s holds and generate that many DISTINCT fresh frames
        # (an `intense` beat gets one extra frame for more punch, capped in frames_for_span).
        frames_per_beat = [
            frames_for_span(e - s, intense=sb.scenes[i].intense)
            for i, (s, e) in enumerate(beat_spans)
        ]
        if resume:
            _record_resume_progress(rec, frames_per_beat)

        # Sparse key-fact callouts: the analysis pass proposes candidates on scenes; the spacing cap
        # is enforced HERE (once) so the recorded plan, the per-scene badges, and what actually
        # renders all match. Each surviving callout is drawn on its beat's first frame's whitespace.
        callout_overlays = emphasis_timeline(
            beat_spans, [s.emphasis for s in sb.scenes], [s.narration for s in sb.scenes]
        )
        kept_callouts = {bi: text for text, bi, _s, _e in callout_overlays}
        rec.set_callouts([(text, bi, start) for text, bi, start, _e in callout_overlays])

        # Style pre-flight: BEFORE the main image loop below, not after — refuses a run that would
        # otherwise pay for ~200 off-style Agnes images before anyone notices the art has drifted.
        _style_preflight(rec, sb, images, channel_refs, skip_style_check)

        for i, sc in enumerate(sb.scenes):
            start, end = beat_spans[i]
            dur = end - start
            is_char = shot_uses_character(sc.shot_type)
            provider = images.character if is_char else images.concept
            refs = channel_refs if is_char else []
            rec.scene_started(
                i, sc.shot_type, sc.image_prompt,
                ref_count=len(refs), narration=sc.narration, cite=sc.cite,
                emphasis=kept_callouts.get(i, ""),  # only badge callouts that survive the spacing cap
                intense=sc.intense,
                frame_count=frames_per_beat[i],  # >1 → a fire spot; dashboard shows both frames
            )
            styled = styled_prompt(
                sc.image_prompt, sb.style, use_character_ref=bool(refs), shot_type=sc.shot_type
            )
            n = frames_per_beat[i]
            rec.log(f"scene {i}: {sc.shot_type} · {dur:.1f}s · {n} fresh frame(s) ({provider.name})")
            for k in range(n):  # each frame is its own fresh generation (no reuse/repeat)
                target = rec.dir / _frame_name(i, k)
                if resume and target.is_file():  # reuse frames from a partial run
                    continue
                # extra frames of the same beat are a clearly different shot (see _frame_prompt) so
                # the on-screen switch reads as a real cut, not a near-duplicate.
                _generate_frame(provider, _frame_prompt(styled, k), target, refs, fallback, rec, i, k)
            rec.scene_image(i, rec.dir / f"img_{i}.png")
            rec.scene_narration(i, dur)
            rec.scene_rendered(i, rec.dir / f"img_{i}.png")
            print(f"  scene {i}: {sc.shot_type:9} {dur:4.1f}s  {n}img  “{sc.narration[:38]}…”")

        # 3) Human-in-the-loop gate: with review on, stop here — all images exist, but NOTHING is
        # assembled until the user approves in the dashboard (they can regenerate any image first).
        if pause_for_review:
            rec.pending_approval()
            rec.log("all images generated — awaiting your review/approval before assembling")
            print("\n⏸  images ready — review them in the dashboard, then Approve to assemble")
            return None
        # Otherwise assemble the whole video under the continuous audio right away.
        return _assemble_video(
            rec, sb, wav, beat_spans, frames_per_beat, callout_overlays, captions,
            words=words, word_starts=word_starts, word_ends=word_ends,
        )
    except Exception as exc:  # record the failure into the manifest, then re-raise for the exit code
        rec.failed(exc)
        print(f"\n❌ run {rec.run_id} failed: {exc}", file=sys.stderr)
        raise


def main() -> None:
    load_dotenv()  # GEMINI_API_KEY / CARTESIA_* from .env
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--images", choices=list(IMAGE_PROVIDER_NAMES), default="placeholder",
        help="shorthand: pick a legacy provider mix for all image roles",
    )
    # Per-role overrides (the new run page): choose a provider for each image role independently.
    ap.add_argument("--char-model", choices=list(IMAGE_PROVIDER_NAMES))
    ap.add_argument("--concept-model", choices=list(IMAGE_PROVIDER_NAMES))
    ap.add_argument("--voice", choices=["say", "cartesia"], default="say")
    ap.add_argument("--storyboard", help="path to a generated storyboard.json (else the canned demo)")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--run-id", help="pre-assigned run id (the dashboard passes this to locate the run dir)")
    ap.add_argument("--out", help="optional extra copy of the final mp4 (always written into the run dir)")
    ap.add_argument("--resume", action="store_true", help="reuse frames already on disk for this run-id")
    ap.add_argument("--fallback", choices=list(IMAGE_PROVIDER_NAMES),
                    help="secondary provider for frames the primary refuses/fails (e.g. a safety block)")
    ap.add_argument(
        "--skip-style-check", action="store_true",
        help="render even if the pre-flight style probe drifts outside the reference envelope "
             "(informed-operator escape hatch)",
    )
    # Human-in-the-loop review gate.
    ap.add_argument("--review", action="store_true",
                    help="stop after generating all images; assemble only after approval")
    ap.add_argument("--assemble-only", action="store_true",
                    help="assemble the video from images + narration already on disk (approve step)")
    ap.add_argument("--regenerate", type=int, metavar="SCENE",
                    help="re-draw one scene's image(s) in an existing run (review step), then exit")
    ap.add_argument("--prompt", help="edited image prompt to use with --regenerate (else the script's)")
    # Thumbnail generation.
    ap.add_argument("--thumbnail", action="store_true",
                    help="generate a YouTube thumbnail for an existing run, then exit")
    ap.add_argument("--thumb-text", help="the big title words for the thumbnail (else the run title)")
    ap.add_argument("--thumb-subject", help="focal subject for the thumbnail (else a striking scene)")
    args = ap.parse_args()

    if args.char_model or args.concept_model:  # per-role selection
        images = providers_from_roles(
            args.char_model or args.images, args.concept_model or args.images
        )
        images_label = f"{images.character.name}/{images.concept.name}"
    else:
        images = build_providers(args.images)
        images_label = args.images
    voice = CartesiaVoiceProvider() if args.voice == "cartesia" else SayVoiceProvider()
    sb = (
        storyboard_from_dict(json.loads(Path(args.storyboard).read_text()))
        if args.storyboard
        else DEMO_STORYBOARD
    )

    # Review-gate follow-ups operate on an EXISTING run (loaded, not reset): approve → assemble the
    # reviewed images; regenerate → re-draw one scene's image(s) and stay awaiting approval.
    if args.assemble_only or args.regenerate is not None or args.thumbnail:
        if not args.run_id:
            ap.error("--assemble-only / --regenerate / --thumbnail require --run-id")
        rec = RunRecorder.load(RUNS_DIR, args.run_id)
        if args.assemble_only:
            assemble_storyboard(rec, sb, captions=not args.no_captions)
        elif args.thumbnail:
            generate_thumbnail(rec, sb, images.character, text=args.thumb_text,
                               subject=args.thumb_subject)
        else:
            fallback = make_image_provider(args.fallback) if args.fallback else None
            regenerate_scene(rec, sb, images, args.regenerate, fallback, prompt_override=args.prompt)
        return

    # Each run records itself into result/axen/poc/runs/<run_id>/ (manifest + log + its own assets),
    # so the dashboard can replay logs, intermediate images, and the final video while it runs.
    rec = RunRecorder.create(
        RUNS_DIR,
        title=sb.title,
        images_provider=images_label,
        voice_provider=voice.name,
        scene_count=len(sb.scenes),
        run_id=args.run_id,
    )
    # Record the operator's actual CLI choices onto the manifest (mirrors dashboard/app.py's
    # `_spawn_run`, which pre-writes the same settings before this subprocess starts — without this
    # call, this RunRecorder.create() above would silently reset them back to defaults).
    rec.set_settings(RunSettings(
        captions=not args.no_captions, images_provider=images_label, voice=voice.name,
    ))
    print(f"Storyboard: {sb.title!r} · {len(sb.scenes)} scenes · images={images_label} · voice={voice.name}")
    print(f"Run: {rec.run_id}  →  {rec.dir}")
    if args.storyboard:
        attach_script_artifacts(rec, Path(args.storyboard))

    fallback = make_image_provider(args.fallback) if args.fallback else None
    out = render_storyboard(
        rec, sb, images, voice, captions=not args.no_captions,
        resume=args.resume, fallback=fallback, pause_for_review=args.review,
        skip_style_check=args.skip_style_check,
    )
    if args.out and out is not None:  # optional convenience copy (skipped when paused for review)
        shutil.copy(out, args.out)


if __name__ == "__main__":
    main()
