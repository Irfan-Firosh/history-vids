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
import unicodedata
import wave
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))


from studio import (  # noqa: E402
    agnes,
    cloudflare,
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


class CloudflareImageProvider:
    """Cloudflare Workers AI **FLUX.2 [dev]** — text-to-image + up to 4 reference images for
    character consistency (the Cloudflare-billed counterpart to Gemini). Needs CLOUDFLARE_ACCOUNT_ID
    + CLOUDFLARE_API_TOKEN.

    `refs` (REF-1 character sheet, REF-2 expressions) are downscaled to < 512px and sent as
    ``input_image_0..N`` in a multipart request, so the recurring stick-figure stays on-model. Pure
    endpoint/parse logic lives in ``studio.cloudflare``; this is the httpx side-effect wrapper.
    """

    name = "cloudflare"

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
        # text-to-image succeeds. Default to text-to-image (ignore refs); set AGNES_IMG2IMG=1 to re-enable.
        self.use_img2img = os.environ.get("AGNES_IMG2IMG", "0") == "1"

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
        if refs and self.use_img2img:  # character/wide → image-to-image off the reference(s)
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


def make_caption_png(text: str, out: Path) -> None:
    """Render a full-frame transparent caption PNG (this ffmpeg lacks drawtext/libass, so we
    overlay a PNG — the same pattern the repo's caption renderer uses)."""
    from PIL import Image, ImageDraw, ImageFont

    text = _clean_caption(text)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    ff = _fontfile()
    font = ImageFont.truetype(ff, 46) if ff else ImageFont.load_default()
    lines = textwrap.wrap(text, width=46)
    line_h = 60
    block_h = line_h * len(lines)
    top = H - block_h - 110
    maxw = max((d.textlength(ln, font=font) for ln in lines), default=0)
    pad = 32
    d.rectangle([(W - maxw) / 2 - pad, top - pad, (W + maxw) / 2 + pad, top + block_h + pad - 12],
                fill=(0, 0, 0, 150))
    y = top
    for ln in lines:
        w = d.textlength(ln, font=font)
        d.text(((W - w) / 2, y), ln, font=font, fill=(255, 255, 255, 255))
        y += line_h
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


#: Providers that condition on a reference image to keep the recurring character on-model
#: (Gemini reference-conditioning, Cloudflare FLUX.2 input images, Agnes image-to-image).
REF_CAPABLE = frozenset({"gemini", "cloudflare", "agnes"})

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
