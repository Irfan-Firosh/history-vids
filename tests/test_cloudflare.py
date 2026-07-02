"""Tests for the Cloudflare Workers AI image helpers + provider routing."""

from __future__ import annotations

import base64

import pytest

from studio import cloudflare


def test_run_endpoint_builds_account_and_model_path():
    url = cloudflare.run_endpoint("acct123")
    assert url.endswith("/accounts/acct123/ai/run/@cf/black-forest-labs/flux-2-dev")


def test_parse_image_decodes_base64_result():
    raw = b"\x89PNG\r\n fake image bytes"
    payload = {"success": True, "result": {"image": base64.b64encode(raw).decode()}}
    assert cloudflare.parse_image(payload) == raw


def test_parse_image_raises_on_error_envelope():
    with pytest.raises(cloudflare.CloudflareError):
        cloudflare.parse_image({"success": False, "errors": [{"message": "boom"}]})


def test_parse_image_raises_when_no_image():
    with pytest.raises(cloudflare.CloudflareError):
        cloudflare.parse_image({"success": True, "result": {}})
