"""Token-refresh rate limit: missing cookie and login reset."""

from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from routers.auth import helpers as auth_helpers
from routers.auth import session as session_mod
from services.redis.rate_limiting.redis_rate_limiter import RedisRateLimiter


def _http_request(cookies: dict[str, str] | None = None, ip: str = "203.0.113.10") -> Request:
    """Build a minimal ASGI request for /refresh and cookie helpers."""
    header_list: list[tuple[bytes, bytes]] = []
    if cookies:
        cookie_value = "; ".join(f"{key}={value}" for key, value in cookies.items())
        header_list.append((b"cookie", cookie_value.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/refresh",
        "raw_path": b"/api/auth/refresh",
        "query_string": b"",
        "headers": header_list,
        "scheme": "https",
        "server": ("testserver", 443),
        "client": (ip, 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_refresh_without_cookie_does_not_count_against_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guest / logged-out /refresh must 401 without incrementing the IP window."""
    rate_check = AsyncMock(return_value=(True, 1, ""))
    monkeypatch.setattr(RedisRateLimiter, "check_and_record", rate_check)

    with pytest.raises(HTTPException) as exc_info:
        await session_mod.refresh_token(_http_request(), Response())

    assert exc_info.value.status_code == 401
    rate_check.assert_not_called()


@pytest.mark.asyncio
async def test_refresh_with_cookie_is_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    """A present refresh cookie still consumes the sliding window."""
    rate_check = AsyncMock(return_value=(False, 61, ""))
    monkeypatch.setattr(RedisRateLimiter, "check_and_record", rate_check)

    with pytest.raises(HTTPException) as exc_info:
        await session_mod.refresh_token(
            _http_request({"refresh_token": "rt-present"}),
            Response(),
        )

    assert exc_info.value.status_code == 429
    rate_check.assert_awaited_once()


@pytest.mark.asyncio
async def test_issue_new_auth_cookies_clears_refresh_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Login/register/OAuth must reset token_refresh so the new session can rotate."""
    cleared: list[str] = []

    async def _clear(ip: str) -> None:
        cleared.append(ip)

    monkeypatch.setattr(auth_helpers, "clear_token_refresh_attempts", _clear)
    monkeypatch.setattr(auth_helpers, "is_https", lambda _req: True)
    monkeypatch.setattr(auth_helpers, "get_client_ip", lambda _req: "203.0.113.10")

    response = JSONResponse(content={"ok": True})
    await auth_helpers.issue_new_auth_cookies(
        response,
        "access-jwt",
        "refresh-token",
        _http_request(),
    )

    assert cleared == ["203.0.113.10"]
    cookie_names = {
        header_value.decode("latin-1").split(";", 1)[0].split("=", 1)[0].strip()
        for header_name, header_value in response.raw_headers
        if header_name == b"set-cookie"
    }
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names
