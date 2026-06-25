"""Tests for DingTalk bind Redis guess-limit fail-closed behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.auth.dingtalk_bind_redis import is_bind_code_guess_blocked


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
