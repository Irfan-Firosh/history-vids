"""Tests for the Agnes image helpers + per-role provider selection."""

from __future__ import annotations

import base64

import pytest

from studio import agnes


# ── pure request/response helpers ──────────────────────────────────────────────
def test_text_to_image_body_uses_top_level_return_base64():
    b = agnes.text_to_image_body("a cave", size="1024x576")
    assert b["model"] == "agnes-image-2.1-flash" and b["size"] == "1024x576"
    assert b["return_base64"] is True
    assert "response_format" not in b  # must NOT be top-level (per the API docs)


def test_image_to_image_body_nests_image_and_response_format():
    b = agnes.image_to_image_body("redraw", ["data:image/png;base64,AAA"], size="1024x576")
    assert "response_format" not in b  # only under extra_body
    assert b["extra_body"]["image"] == ["data:image/png;base64,AAA"]
    assert b["extra_body"]["response_format"] == "b64_json"


def test_extract_decodes_b64():
    raw = b"\x89PNG\r\n img"
    img, url = agnes.extract({"data": [{"b64_json": base64.b64encode(raw).decode(), "url": None}]})
    assert img == raw and url is None


def test_extract_returns_url_when_no_b64():
    img, url = agnes.extract({"data": [{"b64_json": None, "url": "https://x/y.png"}]})
    assert img is None and url == "https://x/y.png"


def test_extract_raises_when_empty():
    with pytest.raises(agnes.AgnesError):
        agnes.extract({"data": [{}]})
