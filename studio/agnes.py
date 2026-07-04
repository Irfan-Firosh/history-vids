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
import re
from collections.abc import Sequence

ENDPOINT = "https://apihub.agnes-ai.com/v1/images/generations"
DEFAULT_MODEL = "agnes-image-2.1-flash"
DEFAULT_SIZE = "1024x576"  # 16:9 (scaled/cropped to 1920x1080 downstream)


class AgnesError(RuntimeError):
    """Agnes returned no usable image in the response."""


class ContentPolicyError(RuntimeError):
    """Agnes rejected the PROMPT itself on content policy (HTTP 400 content_policy_violation).

    Distinct from a transient error: a plain retry of the same prompt fails again, so the caller
    retries with a :func:`soften_prompt` variant instead of backing off.
    """


def is_content_policy_error(status_code: int, body: dict | str | None) -> bool:
    """True when an Agnes error is a prompt content-policy block (so we should soften + retry, not
    back off). Matches the documented ``content_policy_violation`` code and the "modify your prompt"
    message across either a parsed JSON error or the raw response text."""
    if status_code != 400:
        return False
    if isinstance(body, dict):
        err = body.get("error") or {}
        code = str(err.get("code") or "")
        msg = str(err.get("message") or "")
    else:
        code = msg = str(body or "")
    blob = f"{code} {msg}".lower()
    return "content_policy" in blob or "content policy" in blob or "modify your prompt" in blob


#: Graphic terms that commonly trip image content filters. A history channel hits these constantly
#: (death, weapons), so on a policy block we swap them for mild, symbolic synonyms rather than give
#: up. Deliberately EXCLUDES ordinary history words like "war"/"battle"/"attack" (rarely blocked;
#: neutering them would flatten every video). Multi-word phrases match before single words.
_SOFTEN_MAP: dict[str, str] = {
    "dead bodies": "fallen figures", "dead body": "fallen figure",
    "corpses": "fallen figures", "corpse": "fallen figure",
    "bloody": "dramatic", "blood": "", "gore": "", "gory": "dramatic",
    "killing": "defeating", "killed": "defeated", "kill": "defeat",
    "murdered": "defeated", "murder": "conflict",
    "slaughter": "clash", "massacre": "clash",
    "execution": "solemn scene", "executed": "confronted", "execute": "confront",
    "beheaded": "solemn", "behead": "confront",
    "decapitated": "solemn", "decapitate": "confront",
    "hanged": "solemn", "hanging": "still", "hang": "stand", "noose": "rope",
    "tortured": "weary", "torture": "hardship",
    "stabbed": "struck", "stab": "reach",
    "gunshot": "flash", "shooting": "commotion",
    "guns": "tools", "gun": "tool", "rifle": "tool", "pistol": "tool",
    "weapons": "objects", "weapon": "object",
    "knife": "tool", "sword": "staff", "blade": "staff",
    "wounded": "weary", "wound": "mark",
    "brutality": "intensity", "brutal": "intense",
    "violence": "conflict", "violent": "intense",
    "nudity": "clothed figures", "naked": "clothed", "nude": "clothed",
    "sexual": "romantic",
}
_FLAGGED_RE = re.compile(
    r"\b(" + "|".join(sorted((re.escape(w) for w in _SOFTEN_MAP), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_SAFETY = (
    " Keep it mild, non-graphic, symbolic and family-friendly — no blood, no gore, no weapons, "
    "no violence, no nudity."
)


def _neutralise(text: str, drop: bool) -> str:
    """Replace flagged words with mild synonyms (``drop=False``) or remove them (``drop=True``),
    then collapse the whitespace the removals leave behind."""
    def repl(m: re.Match) -> str:
        return "" if drop else _SOFTEN_MAP.get(m.group(0).lower(), "")
    return re.sub(r"\s+", " ", _FLAGGED_RE.sub(repl, text)).strip()


def soften_prompt(prompt: str, level: int = 1) -> str:
    """A milder version of a prompt Agnes blocked on content policy, escalating with ``level``:

    * ``1`` — swap graphic words for mild symbolic synonyms + append a safety note.
    * ``2`` — drop the graphic words entirely + safety note.
    * ``3+`` — strip them and wrap in a blunt "nothing graphic or disturbing" framing.
    """
    if level <= 1:
        return _neutralise(prompt, drop=False) + _SAFETY
    if level == 2:
        return _neutralise(prompt, drop=True) + _SAFETY
    return (
        "A calm, non-graphic, symbolic stick-figure explainer cartoon. "
        + _neutralise(prompt, drop=True)
        + _SAFETY
        + " Absolutely nothing graphic or disturbing."
    )


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
