"""Tests for API key DingTalk generation usage aggregates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from utils.auth import api_key_usage_stats, api_keys
from utils.auth.api_key_usage_stats import GENERATE_DINGTALK_ENDPOINT


def test_generate_dingtalk_endpoint_constant() -> None:
    assert GENERATE_DINGTALK_ENDPOINT == "/api/generate_dingtalk"


@pytest.mark.asyncio
async def test_dingtalk_request_counts_by_api_key_id_maps_rows() -> None:
    row_a = MagicMock()
    row_a.api_key_id = 3
    row_a.request_count = 12
    row_b = MagicMock()
    row_b.api_key_id = 7
    row_b.request_count = 1

    result_mock = MagicMock()
    result_mock.all.return_value = [row_a, row_b]
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result_mock)

    counts = await api_key_usage_stats.dingtalk_request_counts_by_api_key_id(db)

    assert counts == {3: 12, 7: 1}
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_track_api_key_usage_falls_back_when_redis_incr_returns_zero() -> None:
    cached = {"id": 9, "key": "mg_test", "name": "t"}
    fake_cache = MagicMock()
    fake_cache.get = AsyncMock(return_value=cached)
    fake_cache.incr_usage = AsyncMock(return_value=0)
    original_cache = api_keys._api_key_cache
    api_keys._api_key_cache = fake_cache
    api_keys._persist_api_key_usage_to_db = AsyncMock(return_value=True)

    db = AsyncMock()
    try:
        await api_keys.track_api_key_usage("mg_test", db)
    finally:
        api_keys._api_key_cache = original_cache

    api_keys._persist_api_key_usage_to_db.assert_awaited_once_with("mg_test", db)
    fake_cache.incr_usage.assert_awaited_once_with(9)
