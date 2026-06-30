"""Tests for the migration-safe double-submit CSRF middleware."""

from unittest.mock import patch

import pytest
from starlette.responses import JSONResponse

from routers.auth import helpers as auth_helpers
from services.infrastructure.http import middleware as middleware_module
from utils.auth.request_helpers import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


def _make_request(method: str, path: str, cookies: dict, headers: dict):
    """Build a minimal ASGI request for the CSRF middleware."""
    header_list = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    if cookies:
        cookie_value = "; ".join(f"{k}={v}" for k, v in cookies.items())
        header_list.append((b"cookie", cookie_value.encode()))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": header_list,
        "scheme": "https",
        "server": ("testserver", 443),
        "client": ("203.0.113.5", 12345),
    }
    return middleware_module.Request(scope)


def _set_cookie_names(response: JSONResponse) -> set[str]:
    """Cookie names written via Set-Cookie on the response."""
    names: set[str] = set()
    for header_name, header_value in response.raw_headers:
        if header_name == b"set-cookie":
            cookie_pair = header_value.decode("latin-1").split(";", 1)[0]
            names.add(cookie_pair.split("=", 1)[0].strip())
    return names


async def _passthrough(_request):
    return JSONResponse(content={"ok": True})


@pytest.mark.asyncio
async def test_csrf_bootstrap_allows_when_cookie_absent_and_sets_it() -> None:
    """Authenticated mutation without a csrf cookie is allowed once and seeds it."""
    request = _make_request(
        "POST",
        "/api/auth/refresh",
        cookies={"access_token": "jwt"},
        headers={"Origin": "https://testserver"},
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 200
    assert CSRF_COOKIE_NAME in _set_cookie_names(response)


@pytest.mark.asyncio
async def test_csrf_enforced_when_cookie_present_and_header_missing() -> None:
    """Once the csrf cookie exists, a mutation without the header is rejected."""
    request = _make_request(
        "POST",
        "/api/conversations/rename",
        cookies={"access_token": "jwt", CSRF_COOKIE_NAME: "tok-abc"},
        headers={"Origin": "https://testserver"},
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_rejects_header_cookie_mismatch() -> None:
    """A mismatched header/cookie pair is rejected."""
    request = _make_request(
        "POST",
        "/api/conversations/rename",
        cookies={"access_token": "jwt", CSRF_COOKIE_NAME: "tok-abc"},
        headers={"Origin": "https://testserver", CSRF_HEADER_NAME: "tok-different"},
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_csrf_allows_matching_header_and_cookie() -> None:
    """A matching double-submit token passes."""
    request = _make_request(
        "POST",
        "/api/conversations/rename",
        cookies={"access_token": "jwt", CSRF_COOKIE_NAME: "tok-abc"},
        headers={"Origin": "https://testserver", CSRF_HEADER_NAME: "tok-abc"},
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_skips_login_path() -> None:
    """Login stays exempt (no csrf cookie exists yet at first login)."""
    request = _make_request(
        "POST",
        "/api/auth/login",
        cookies={},
        headers={"Origin": "https://testserver"},
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_ignores_unauthenticated_requests() -> None:
    """No access_token cookie means no CSRF enforcement."""
    request = _make_request(
        "POST",
        "/api/public/thing",
        cookies={},
        headers={"Origin": "https://testserver"},
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_skips_when_mgat_bearer_present_despite_session_cookies() -> None:
    """API clients with Bearer mgat_ must not be blocked by incidental session cookies."""
    request = _make_request(
        "POST",
        "/api/ai_assistant/stream",
        cookies={"access_token": "jwt", CSRF_COOKIE_NAME: "tok-abc"},
        headers={
            "Origin": "chrome-extension://hnchjmifggjoialimclegdnfnfobnkkb",
            "Authorization": "Bearer mgat_test_token",
            "X-MG-Client": "chrome-extension",
        },
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_csrf_enforced_when_jwt_bearer_with_session_cookies() -> None:
    """Non-mgat Bearer does not bypass double-submit CSRF when session cookies are present."""
    request = _make_request(
        "POST",
        "/api/conversations/rename",
        cookies={"access_token": "jwt", CSRF_COOKIE_NAME: "tok-abc"},
        headers={
            "Origin": "https://testserver",
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.sig",
        },
    )
    response = await middleware_module.csrf_protection(request, _passthrough)
    assert response.status_code == 403


def test_set_auth_cookies_seeds_csrf_cookie() -> None:
    """Login/refresh cookie helper issues a csrf_token alongside access/refresh."""
    response = JSONResponse(content={"ok": True})
    request = _make_request("POST", "/api/auth/login", cookies={}, headers={})
    with patch.object(auth_helpers, "is_https", return_value=True):
        auth_helpers.set_auth_cookies(response, "access-jwt", "refresh-token", request)
    cookie_names = _set_cookie_names(response)
    assert "access_token" in cookie_names
    assert "refresh_token" in cookie_names
    assert CSRF_COOKIE_NAME in cookie_names
