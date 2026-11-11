"""Tests for DingTalk bind Redis guess limits and scoped cancel."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.auth.dingtalk_bind_redis import is_bind_code_guess_blocked, revoke_pending_bind_token


@pytest.mark.asyncio
async def test_guess_blocked_when_redis_unavailable() -> None:
    """Brute-force protection must fail closed when Redis is down."""
    with patch(
        "services.auth.dingtalk_bind_redis.get_async_redis",
        return_value=None,
    ):
        blocked = await is_bind_code_guess_blocked("staffA", "token-xyz")

    assert blocked is True


@pytest.mark.asyncio
async def test_guess_blocked_when_redis_mget_errors() -> None:
    """Redis errors during guess lookup must fail closed."""
    redis = AsyncMock()
    redis.mget = AsyncMock(side_effect=ConnectionError("redis down"))

    with patch(
        "services.auth.dingtalk_bind_redis.get_async_redis",
        return_value=redis,
    ):
        blocked = await is_bind_code_guess_blocked("staffA", "token-xyz")

    assert blocked is True


def _redis_get(key: str) -> str | None:
    if "minter" in key:
        return "abandoned-token"
    return None


@pytest.mark.asyncio
async def test_scoped_revoke_leaves_a_newer_pair_session() -> None:
    """A late mint must not cancel the session that replaced it."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value="newer-token")

    with patch(
        "services.auth.dingtalk_bind_redis.get_async_redis",
        return_value=redis,
    ):
        await revoke_pending_bind_token(7, only_token="abandoned-token")

    redis.delete.assert_not_called()


@pytest.mark.asyncio
async def test_scoped_revoke_drops_the_matching_pair_session() -> None:
    """Cancel removes the pending session when the token still matches."""
    redis = AsyncMock()
    redis.get = AsyncMock(side_effect=_redis_get)

    with patch(
        "services.auth.dingtalk_bind_redis.get_async_redis",
        return_value=redis,
    ):
        await revoke_pending_bind_token(7, only_token="abandoned-token")

    assert redis.delete.await_count == 2
