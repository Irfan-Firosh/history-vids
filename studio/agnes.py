"""Pure helpers for Agnes Image 2.1 Flash (Sapiens AI) — request bodies + response parse.

OpenAI-compatible image endpoint (``POST /v1/images/generations``) supporting **text-to-image** and
**image-to-image** (reference images in ``extra_body.image`` as public URLs or base64 data URIs).
Free/cheap, fast, on-style, and reliable in testing. The side-effecting POST (with RPM-aware retry)
lives in ``tools/studio_poc.py`` (``AgnesImageProvider``).

Quirk (from the docs): ``response_format`` must NOT be top-level — it goes in ``extra_body``. For
text-to-image base64 use top-level ``return_base64: true``; for image-to-image use
``extra_body.response_format: "b64_json"``.
"""

from __future__ import annotations

import base64
from collections.abc import Sequence

ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_MODEL = "agnes-image-2.1-flash"
DEFAULT_SIZE = "1024x576"  # 16:9 (scaled/cropped to 1920x1080 downstream)


class AgnesError(RuntimeError):
    """Agnes returned no usable image in the response."""


def text_to_image_body(prompt: str, size: str = DEFAULT_SIZE, model: str = DEFAULT_MODEL) -> dict:
    """Text-to-image request body (base64 output via top-level ``return_base64``)."""
    return {"model": model, "prompt": prompt, "size": size, "return_base64": True}


def image_to_image_body(
    prompt: str, images: Sequence[str], size: str = DEFAULT_SIZE, model: str = DEFAULT_MODEL
) -> dict:
    """Image-to-image body — reference image(s) as URLs/data URIs in ``extra_body.image``.

    ``response_format`` is nested under ``extra_body`` (top-level would error, per the API docs).
    """
    return {
        "model": model,
        "prompt": prompt,
        "size": size,
        "extra_body": {"image": list(images), "response_format": "b64_json"},
    }


def extract(payload: dict) -> tuple[bytes | None, str | None]:
    """From a response, return ``(image_bytes, url)`` — decoded base64 if present, else a URL.

    Raises :class:`AgnesError` if neither is present.
    """
    if not isinstance(payload, dict):
        raise AgnesError("unexpected Agnes response (not a JSON object)")
    data = payload.get("data") or []
    first = data[0] if data else {}
    if first.get("b64_json"):
        return base64.b64decode(first["b64_json"]), None
    if first.get("url"):
        return None, first["url"]
    raise AgnesError(f"Agnes response had no image (keys={list(first.keys())})")
