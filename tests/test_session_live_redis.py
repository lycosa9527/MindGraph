"""Live Redis contract: FIFO kick-off, refresh TTL, no reuse-nuke on kick."""

from __future__ import annotations

import hashlib
from contextlib import ExitStack, asynccontextmanager
from typing import AsyncIterator
from unittest.mock import patch

import pytest
import redis.asyncio as aioredis
from redis.exceptions import RedisError
from starlette.requests import Request
from starlette.responses import JSONResponse

from routers.auth import helpers as auth_helpers
from services.redis import keys as redis_keys
from services.redis.session.redis_session_manager import (
    RefreshTokenManager,
    RedisSessionManager,
)
from utils.auth.config import REFRESH_TOKEN_EXPIRY_DAYS
from utils.auth.tokens import DEVICE_COOKIE_NAME, assign_device_id, compute_device_hash

_TEST_REDIS_URL = "redis://localhost:6379/15"
_USER_ID = 9_260_826


def _token_hash(token: str) -> str:
    """SHA256 hex of a raw access token, matching Redis session members."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _http_request(user_agent: str, cookies: dict[str, str] | None = None) -> Request:
    """Minimal HTTPS request for cookie helpers (no dummy objects)."""
    header_list = [(b"user-agent", user_agent.encode("latin-1"))]
    if cookies:
        cookie_value = "; ".join(f"{name}={value}" for name, value in cookies.items())
        header_list.append((b"cookie", cookie_value.encode("latin-1")))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "raw_path": b"/api/auth/login",
            "query_string": b"",
            "headers": header_list,
            "scheme": "https",
            "server": ("testserver", 443),
            "client": ("203.0.113.5", 12345),
        }
    )


async def _ping_or_skip() -> aioredis.Redis:
    client = aioredis.from_url(
        _TEST_REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1.5,
        socket_timeout=2.0,
    )
    try:
        await client.ping()
    except (OSError, RedisError) as exc:
        await client.aclose()
        pytest.skip(f"Redis not reachable for live session test: {exc}")
    return client


@asynccontextmanager
async def _live_managers() -> AsyncIterator[tuple[RedisSessionManager, RefreshTokenManager, aioredis.Redis]]:
    client = await _ping_or_skip()
    await client.flushdb()
    session_mgr = RedisSessionManager()
    refresh_mgr = RefreshTokenManager()
    with ExitStack() as stack:
        stack.enter_context(patch.object(session_mgr, "_use_redis", return_value=True))
        stack.enter_context(patch.object(refresh_mgr, "_use_redis", return_value=True))
        stack.enter_context(
            patch(
                "services.redis.session.redis_session_manager.get_async_redis",
                return_value=client,
            )
        )
        stack.enter_context(patch("services.redis.redis_async_ops.get_async_redis", return_value=client))
        stack.enter_context(patch("services.redis.redis_async_ops._is_redis_available", return_value=True))
        stack.enter_context(patch("services.redis.redis_async_ops._breaker_enabled", return_value=False))
        stack.enter_context(
            patch(
                "services.redis.session.redis_session_manager.get_refresh_token_manager",
                return_value=refresh_mgr,
            )
        )
        stack.enter_context(patch("services.redis.session.redis_session_manager.MAX_CONCURRENT_SESSIONS", 2))
        try:
            yield session_mgr, refresh_mgr, client
        finally:
            await client.flushdb()
            await client.aclose()


@pytest.mark.asyncio
async def test_live_fifo_third_login_kicks_oldest_fourth_kicks_next() -> None:
    """C kicks A, D kicks B. New logins stay; kicked access cannot validate."""
    async with _live_managers() as (session_mgr, _refresh_mgr, _client):
        stored_a = await session_mgr.store_session(_USER_ID, "access-a", device_hash="deva")
        stored_b = await session_mgr.store_session(_USER_ID, "access-b", device_hash="devb")
        stored_c = await session_mgr.store_session(_USER_ID, "access-c", device_hash="devc")
        assert stored_a and stored_b and stored_c
        assert await session_mgr.is_session_valid(_USER_ID, "access-a") is False
        assert await session_mgr.is_session_valid(_USER_ID, "access-b") is True
        assert await session_mgr.is_session_valid(_USER_ID, "access-c") is True
        kick_a = await session_mgr.check_invalidation_notification(_USER_ID, _token_hash("access-a"))
        assert kick_a is not None

        stored_d = await session_mgr.store_session(_USER_ID, "access-d", device_hash="devd")
        assert stored_d is True
        assert await session_mgr.is_session_valid(_USER_ID, "access-b") is False
        assert await session_mgr.is_session_valid(_USER_ID, "access-c") is True
        assert await session_mgr.is_session_valid(_USER_ID, "access-d") is True
        kick_b = await session_mgr.check_invalidation_notification(_USER_ID, _token_hash("access-b"))
        assert kick_b is not None
        assert await session_mgr.check_invalidation_notification(_USER_ID, _token_hash("access-c")) is None


@pytest.mark.asyncio
async def test_live_kick_revokes_refresh_without_reuse_nuke() -> None:
    """Oldest refresh is dropped; presenting it must not wipe the new login."""
    async with _live_managers() as (session_mgr, refresh_mgr, client):
        await refresh_mgr.store_refresh_token(_USER_ID, "hash-a", "10.0.0.1", "Chrome/140", "deva")
        await refresh_mgr.store_refresh_token(_USER_ID, "hash-b", "10.0.0.1", "Chrome/140", "devb")
        await session_mgr.store_session(_USER_ID, "access-a", device_hash="deva")
        await session_mgr.store_session(_USER_ID, "access-b", device_hash="devb")
        await session_mgr.store_session(_USER_ID, "access-c", device_hash="devc")
        await refresh_mgr.store_refresh_token(_USER_ID, "hash-c", "10.0.0.1", "Chrome/140", "devc")

        valid_a, _data, error = await refresh_mgr.validate_refresh_token(
            _USER_ID,
            "hash-a",
            current_device_hash="deva",
            current_user_agent="Chrome/140",
        )
        assert valid_a is False
        assert error == "Invalid or expired refresh token"
        reuse_key = redis_keys.REFRESH_REUSE_MARKER.format(token_hash="hash-a")
        assert await client.get(reuse_key) is None

        valid_c, _cdata, _cerr = await refresh_mgr.validate_refresh_token(
            _USER_ID,
            "hash-c",
            current_device_hash="devc",
            current_user_agent="Chrome/140",
        )
        assert valid_c is True
        assert await session_mgr.is_session_valid(_USER_ID, "access-c") is True


@pytest.mark.asyncio
async def test_live_refresh_ttl_is_seven_days() -> None:
    """The refresh key must outlive an overnight close."""
    async with _live_managers() as (_session_mgr, refresh_mgr, client):
        await refresh_mgr.store_refresh_token(_USER_ID, "hash-ttl", "10.0.0.1", "Chrome/140", "devttl")
        token_key = redis_keys.REFRESH_TOKEN.format(user_id=_USER_ID, token_hash="hash-ttl")
        ttl = await client.ttl(token_key)
        assert ttl >= (REFRESH_TOKEN_EXPIRY_DAYS * 86_400) - 30


def test_set_auth_cookies_writes_device_and_refresh_for_seven_days() -> None:
    """Browser cookies issued on login must carry the minted device id."""
    request = _http_request("Chrome/140")
    device_id = assign_device_id(request)
    response = JSONResponse(content={"ok": True})
    auth_helpers.set_auth_cookies(
        response,
        "access-jwt",
        "refresh-token",
        request,
        device_hash=device_id,
    )
    headers = {
        header_value.decode("latin-1")
        for header_name, header_value in response.raw_headers
        if header_name == b"set-cookie"
    }
    refresh = next(item for item in headers if item.startswith("refresh_token="))
    device = next(item for item in headers if item.startswith(f"{DEVICE_COOKIE_NAME}="))
    assert f"Max-Age={REFRESH_TOKEN_EXPIRY_DAYS * 24 * 60 * 60}" in refresh
    assert "samesite=lax" in refresh.lower()
    assert device_id in device
    follow = _http_request("Chrome/141 zstd", {DEVICE_COOKIE_NAME: device_id})
    assert compute_device_hash(follow) == device_id
