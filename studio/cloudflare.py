"""Pure helpers for Cloudflare Workers AI image models (endpoint + response parse).

Best image-input model = **FLUX.2 [dev]** (``@cf/black-forest-labs/flux-2-dev``): text-to-image plus
up to 4 reference images (each < 512x512) for character consistency — the Cloudflare-billed
counterpart to Gemini's reference conditioning. Cloudflare bills this (Workers AI "Neurons"), not
Google. The side-effecting multipart POST lives in ``tools/studio_poc.py``.
"""

from __future__ import annotations

import base64

WORKERS_AI_RUN = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
DEFAULT_IMAGE_MODEL = "@cf/black-forest-labs/flux-2-dev"
MAX_REFERENCE_IMAGES = 4  # FLUX.2 accepts input_image_0 .. input_image_3
REFERENCE_MAX_DIM = 512  # each reference image must be smaller than 512x512
DEFAULT_STEPS = 12  # FLUX.2 [dev] is heavy (~25-30s/image at 12); tunable via CF_FLUX_STEPS
DEFAULT_WIDTH, DEFAULT_HEIGHT = 1024, 576  # 16:9


class CloudflareError(RuntimeError):
    """Workers AI returned an error, or no image in the response."""


def run_endpoint(account_id: str, model: str = DEFAULT_IMAGE_MODEL) -> str:
    """The Workers AI 'run a model' REST endpoint for this account + model."""
    return WORKERS_AI_RUN.format(account=account_id, model=model)


def parse_image(payload: dict) -> bytes:
    """Extract image bytes from a Workers AI JSON response (base64 in ``result.image``).

    Raises :class:`CloudflareError` on an error envelope or a response with no image.
    """
    if not isinstance(payload, dict):
        raise CloudflareError("unexpected Workers AI response (not a JSON object)")
    if payload.get("success") is False or payload.get("errors"):
        raise CloudflareError(f"Workers AI error: {payload.get('errors')}")
    result = payload.get("result")
    b64 = result.get("image") if isinstance(result, dict) else None
    if not b64:
        raise CloudflareError("Workers AI response had no result.image")
    return base64.b64decode(b64)
