"""Pure helpers for the HuggingFace Inference image API (endpoints + cutaway prompt).

Used for everything that does NOT need character consistency — concept/map shots and the trivial
"cutaway" symbols (question marks, numbers, icons) interleaved with the main Gemini character shots.
FLUX text-to-image has no reference conditioning, so it must never render the recurring stickman.
The side-effecting POST lives in ``tools/studio_poc.py`` (``HuggingFaceImageProvider``).
"""

from __future__ import annotations

from collections.abc import Sequence

#: The HF router is the current serverless path; the classic endpoint is a fallback.
HF_ROUTER = "https://router.huggingface.co/hf-inference/models"
HF_CLASSIC = "https://api-inference.huggingface.co/models"
DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"


def endpoints(model: str) -> Sequence[str]:
    """Try the router first, then the classic inference endpoint."""
    return (f"{HF_ROUTER}/{model}", f"{HF_CLASSIC}/{model}")


def request_body(prompt: str) -> dict:
    """HF serverless text-to-image body."""
    return {"inputs": prompt}
