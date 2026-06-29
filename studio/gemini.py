"""Pure helpers for the Gemini image API — request build + response parse (no I/O).

The side-effecting HTTP call lives in ``tools/studio_poc.py::GeminiImageProvider``; everything here
is pure and unit-tested offline so we never spend image quota in CI. Gemini bills a flat ~1290
tokens per output image (~$0.039); the prompt and reference images are essentially free, so we pass
REF-1/REF-2 on every character shot. See ``context/project/blueprints/gemini-image-provider.md``.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence

#: REST surface. Endpoint = ``{BASE}/{model}:generateContent?key={key}``.
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"
#: Validated "Nano Banana" image model. Override per-channel via ``GEMINI_IMAGE_MODEL``.
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"
#: Request native 16:9 (→ 1344x768); ``scene_filter`` still crops to 1920x1080 as a safety net.
DEFAULT_ASPECT_RATIO = "16:9"


class GeminiError(RuntimeError):
    """The transport succeeded but the API returned an error (or no image)."""

    def __init__(self, code: int | None, status: str, message: str) -> None:
        self.code = code
        self.status = status
        self.api_message = message
        super().__init__(f"Gemini {code or ''} {status}: {message}".strip())

    @property
    def is_billing(self) -> bool:
        """True for quota/billing walls — retrying is pointless; the user must top up."""
        m = self.api_message.lower()
        return any(s in m for s in ("deplet", "billing", "free_tier", "limit: 0"))

    @property
    def is_retryable(self) -> bool:
        """Transient server/rate errors worth a backoff retry (but never a billing wall)."""
        return self.code in (429, 500, 503) and not self.is_billing


def endpoint(model: str, key: str) -> str:
    """Build the generateContent URL for a model + API key."""
    return f"{GEMINI_API_BASE}/{model}:generateContent?key={key}"


def encode_image(data: bytes) -> str:
    """Base64-encode raw image bytes for an inline reference part."""
    return base64.b64encode(data).decode("ascii")


def build_request(
    prompt: str,
    ref_images_b64: Sequence[str] = (),
    aspect_ratio: str | None = DEFAULT_ASPECT_RATIO,
) -> dict:
    """Build the generateContent JSON body: text prompt + any inline reference images.

    ``ref_images_b64`` are base64 PNG strings (the character/expression sheets). Pass ``aspect_ratio
    =None`` to let the model use its default square (e.g. for reference sheets).
    """
    parts: list[dict] = [{"text": prompt}]
    parts += [{"inlineData": {"mimeType": "image/png", "data": b64}} for b64 in ref_images_b64]
    gen: dict = {"responseModalities": ["IMAGE"]}
    if aspect_ratio:
        gen["imageConfig"] = {"aspectRatio": aspect_ratio}
    return {"contents": [{"parts": parts}], "generationConfig": gen}


def parse_image(response: dict) -> bytes:
    """Extract the generated PNG bytes from a generateContent response, or raise ``GeminiError``."""
    if "error" in response:
        err = response["error"]
        raise GeminiError(err.get("code"), err.get("status", "ERROR"), err.get("message", ""))
    try:
        candidate = response["candidates"][0]
    except (KeyError, IndexError, TypeError) as exc:
        snippet = str(response)[:200]
        raise GeminiError(None, "NO_CANDIDATES", f"unexpected response: {snippet}") from exc
    content = candidate.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not parts:
        # No image content — the model declined. `finishReason` says why (NO_IMAGE, IMAGE_SAFETY,
        # PROHIBITED_CONTENT). Surfaced as the error status so the caller can fall back.
        reason = candidate.get("finishReason") or "NO_CONTENT"
        raise GeminiError(None, str(reason), f"no image ({reason})")
    for part in parts:
        inline = part.get("inlineData") or part.get("inline_data")
        if inline and inline.get("data"):
            return base64.b64decode(inline["data"])
    raise GeminiError(None, "NO_IMAGE", "response contained no inline image data")
