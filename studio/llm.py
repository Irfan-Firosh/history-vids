"""Pure helpers for an OpenAI-compatible chat LLM — request build + response/JSON parse (no I/O).

Targets the local Open WebUI / Ollama endpoint (``gpt-oss:120b``) for script generation. The
side-effecting HTTP call lives in ``tools/`` (``LLMScriptProvider``); everything here is pure and
unit-tested offline. The model is asked to emit a Storyboard JSON object; ``parse_json_block`` is
tolerant of code fences / surrounding prose since local models rarely return clean JSON.
"""

from __future__ import annotations

import json
import re


class LLMError(RuntimeError):
    """The LLM endpoint returned an error, or its output couldn't be parsed."""


def chat_endpoint(base_url: str) -> str:
    """OpenAI-compatible chat-completions URL (Open WebUI exposes ``{base}/chat/completions``)."""
    return f"{base_url.rstrip('/')}/chat/completions"


def build_chat_request(
    model: str,
    system: str,
    user: str,
    temperature: float = 0.7,
    max_tokens: int | None = None,
) -> dict:
    """Build the chat-completions JSON body (system + user messages, non-streaming)."""
    body: dict = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    return body


def extract_message(response: dict) -> str:
    """Return the assistant message text from a chat-completions response, or raise ``LLMError``."""
    if "error" in response:
        err = response["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        raise LLMError(f"LLM API error: {msg}")
    try:
        return response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"unexpected LLM response: {str(response)[:200]}") from exc


def parse_json_block(text: str) -> dict:
    """Extract the first JSON object from model text, tolerating ```json fences and prose.

    Two tiers: (1) ``raw_decode`` parses exactly one complete JSON value from the first ``{`` and
    ignores trailing content (local models append a second object/commentary → "Extra data"). (2) if
    that fails because the JSON itself is malformed (an unescaped quote or missing comma the local
    model emitted → "Expecting ',' delimiter"), fall back to ``json_repair`` to salvage it rather
    than aborting a whole run over one bad character.
    """
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.S)
    if fenced:
        candidate = fenced.group(1).strip()
    start = candidate.find("{")
    if start == -1:
        raise LLMError(f"no JSON object found in LLM output: {text[:160]}")
    body = candidate[start:]
    try:
        obj, _ = json.JSONDecoder().raw_decode(body)
    except json.JSONDecodeError:
        obj = _repair_json(body)  # local-model JSON is often slightly broken; salvage it
    if not isinstance(obj, dict):
        raise LLMError(f"expected JSON object, got {type(obj).__name__}: {text[:160]}")
    return obj


def _repair_json(body: str) -> object:
    """Salvage malformed LLM JSON (unescaped quotes, missing commas) via ``json_repair``."""
    from json_repair import repair_json

    try:
        obj = repair_json(body, return_objects=True)
    except Exception as exc:  # noqa: BLE001 - any repair failure → a clean LLMError for the caller
        raise LLMError(f"invalid JSON in LLM output (unrepairable): {str(exc)[:160]}") from exc
    if obj in ("", None, {}, []):  # repair gave up (empty) → surface a clear error
        raise LLMError(f"invalid JSON in LLM output: could not repair {body[:160]}")
    return obj
