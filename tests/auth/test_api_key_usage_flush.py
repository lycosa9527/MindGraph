"""Tests for API key usage Redis flush restore behavior."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.redis.cache import redis_api_key_usage_flush as flush_mod


@pytest.mark.asyncio
async def test_flush_restores_delta_on_apply_failure_for_one_key() -> None:
    cache = MagicMock()
    cache.get_usage_delta = AsyncMock(return_value=4)
    cache.restore_usage_delta = AsyncMock()

    redis = MagicMock()

    async def fake_scan_iter(*_args, **_kwargs):
        yield "apikey:usage:11"

    redis.scan_iter = fake_scan_iter

    with patch.object(flush_mod, "api_key_cache", cache):
        with patch.object(flush_mod, "is_redis_available", return_value=True):
            with patch.object(flush_mod, "get_async_redis", return_value=redis):
                with patch.object(
                    flush_mod,
                    "apply_api_key_usage_delta",
                    new_callable=AsyncMock,
                    return_value=False,
                ):
                    flushed = await flush_mod.flush_api_key_usage_to_db()

    assert flushed == 0
    cache.restore_usage_delta.assert_awaited_once_with(11, 4)
