"""Regression tests for security production hardening."""

from pathlib import Path
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from jose import jwt

from routers.auth.admin.api_keys import mask_api_key_for_display
from services.infrastructure.http import middleware as middleware_module
from services.infrastructure.security import production_secrets_guard as production_secrets_guard_module
from services.redis.session.redis_session_manager import RedisSessionManager
from utils.auth.config import JWT_ALGORITHM
from utils.auth import request_helpers
from utils.auth.connection_types import HttpOrWebSocket
from utils.auth.passkey_utils import verify_dashboard_passkey
from utils.auth.tokens import decode_access_token


@pytest.mark.asyncio
async def test_is_session_valid_fail_closed_on_redis_error() -> None:
    """Redis errors during session validation must deny access."""
    mgr = RedisSessionManager()
    with patch.object(mgr, "_use_redis", return_value=True):
        with patch(
            "services.redis.session.redis_session_manager.get_async_redis",
            return_value=AsyncMock(),
        ):
            with patch(
                "services.redis.session.redis_session_manager.AsyncRedisOps.get",
                new_callable=AsyncMock,
                side_effect=ConnectionError("redis down"),
            ):
                valid = await mgr.is_session_valid(user_id=1, token="jwt-token")

    assert valid is False


def test_mask_api_key_hides_plaintext() -> None:
    """Admin list responses must not expose full API keys."""
    masked = mask_api_key_for_display("sk-live-abcdef1234")
    assert masked.endswith("1234")
    assert "sk-live-abcdef" not in masked
    assert masked.count("*") >= 4


def test_decode_access_token_rejects_non_access_type() -> None:
    """Access-token decoder rejects refresh/other token types."""
    with patch("utils.auth.tokens.get_jwt_secret", return_value="x" * 32):
        token = jwt.encode(
            {"sub": "1", "type": "refresh", "exp": 9999999999},
            "x" * 32,
            algorithm=JWT_ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401


def test_decode_access_token_accepts_previous_secret() -> None:
    """Dual-verify window accepts tokens signed with the previous secret."""
    previous = "p" * 32
    current = "c" * 32
    token = jwt.encode(
        {"sub": "1", "type": "access", "exp": 9999999999},
        previous,
        algorithm=JWT_ALGORITHM,
    )
    with patch("utils.auth.tokens.get_jwt_secret", return_value=current):
        with patch("utils.auth.tokens.get_jwt_secret_previous", return_value=previous):
            payload = decode_access_token(token)
    assert payload["sub"] == "1"


def test_get_client_ip_websocket_ignores_spoofed_forwarded_without_trusted_proxy() -> None:
    """WebSocket IP resolution must not trust forwarded headers from untrusted peers."""
    websocket = SimpleNamespace(
        client=SimpleNamespace(host="203.0.113.10"),
        headers={"X-Forwarded-For": "198.51.100.1"},
    )
    with patch.object(request_helpers, "TRUSTED_PROXY_IPS", []):
        assert request_helpers.get_client_ip(cast(HttpOrWebSocket, websocket)) == "203.0.113.10"


def test_web_content_fetch_disables_redirects() -> None:
    """SSRF guard must not follow redirects after host validation."""
    source_path = Path(__file__).resolve().parents[1] / "routers" / "api" / "web_content_generation.py"
    source = source_path.read_text(encoding="utf-8")
    assert "follow_redirects=False" in source


@pytest.mark.asyncio
async def test_add_security_headers_includes_hsts_on_https() -> None:
    """HTTPS responses must include Strict-Transport-Security."""
    request = MagicMock()
    request.url.scheme = "https"
    response = MagicMock()
    response.headers = {}

    async def _call_next(_req):
        return response

    with patch.object(middleware_module, "is_https", return_value=True):
        with patch.object(middleware_module, "config") as mock_config:
            mock_config.debug = False
            result = await middleware_module.add_security_headers(request, _call_next)

    assert "Strict-Transport-Security" in result.headers
    assert "includeSubDomains" in result.headers["Strict-Transport-Security"]


def test_production_guard_rejects_placeholder_dashboard_passkey() -> None:
    """Startup guard must reject env.example-style placeholder passkeys when dashboard is enabled."""
    guard = production_secrets_guard_module
    with patch.object(guard, "_require_non_debug", return_value=True):
        with patch.object(guard, "AUTH_MODE", "standard"):
            with patch.object(guard, "PUBLIC_DASHBOARD_PASSKEY", "CHANGE-ME-before-production"):
                with pytest.raises(RuntimeError, match="PUBLIC_DASHBOARD_PASSKEY"):
                    guard.enforce_production_security_guards()


def test_production_guard_allows_unset_dashboard_passkey() -> None:
    """Startup guard must not require PUBLIC_DASHBOARD_PASSKEY when dashboard is disabled."""
    guard = production_secrets_guard_module
    with patch.object(guard, "_require_non_debug", return_value=True):
        with patch.object(guard, "AUTH_MODE", "standard"):
            with patch.object(guard, "PUBLIC_DASHBOARD_PASSKEY", ""):
                guard.enforce_production_security_guards()


def test_verify_dashboard_passkey_rejects_when_disabled() -> None:
    """Empty configured passkey must not accept an empty submitted passkey."""
    with patch("utils.auth.passkey_utils.config.PUBLIC_DASHBOARD_PASSKEY", ""):
        assert verify_dashboard_passkey("") is False
        assert verify_dashboard_passkey("123456") is False
