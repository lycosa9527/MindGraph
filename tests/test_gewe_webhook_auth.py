"""Tests for Gewe webhook HMAC verification."""

import hashlib
import hmac
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from services.infrastructure.security.gewe_webhook_auth import verify_gewe_webhook_request


def _make_request(
    *,
    headers: dict[str, str] | None = None,
    client_host: str = "127.0.0.1",
) -> Request:
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/gewe/webhook",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": (client_host, 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


def test_verify_gewe_webhook_rejects_missing_secret() -> None:
    """Webhook returns 503 when GEWE_WEBHOOK_SECRET is unset."""
    body = b'{"testMsg":"hello"}'
    request = _make_request(headers={"X-Gewe-Signature": "deadbeef"})
    with patch("services.infrastructure.security.gewe_webhook_auth._webhook_secret", return_value=""):
        with pytest.raises(HTTPException) as exc:
            verify_gewe_webhook_request(request, body)
        assert exc.value.status_code == 503


def test_verify_gewe_webhook_accepts_valid_signature() -> None:
    """A correct HMAC-SHA256 signature passes verification."""
    secret = "test-secret"
    body = b'{"Appid":"a","Wxid":"w"}'
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    request = _make_request(headers={"X-Gewe-Signature": digest})
    with patch("services.infrastructure.security.gewe_webhook_auth._webhook_secret", return_value=secret):
        verify_gewe_webhook_request(request, body)


def test_verify_gewe_webhook_rejects_ip_not_in_allowlist() -> None:
    """A peer outside GEWE_WEBHOOK_ALLOWED_IPS is rejected with 403."""
    secret = "test-secret"
    body = b'{"Appid":"a"}'
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    request = _make_request(headers={"X-Gewe-Signature": digest}, client_host="203.0.113.9")
    with patch("services.infrastructure.security.gewe_webhook_auth._webhook_secret", return_value=secret):
        with patch("services.infrastructure.security.gewe_webhook_auth._allowed_ips", return_value={"198.51.100.1"}):
            with pytest.raises(HTTPException) as exc:
                verify_gewe_webhook_request(request, body)
            assert exc.value.status_code == 403
