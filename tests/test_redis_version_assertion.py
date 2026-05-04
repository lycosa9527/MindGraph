"""Startup Redis version check for online collab."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.online_collab.redis.online_collab_redis_health import (
    check_online_collab_redis_version,
)


@pytest.mark.asyncio
async def test_check_version_exits_below_8_when_collab_enabled(monkeypatch):
    monkeypatch.delenv("COLLAB_DISABLED", raising=False)
    redis = MagicMock()
    redis.info = AsyncMock(return_value={"redis_version": "7.4.0"})
    with patch("os._exit") as exit_mock:
        with patch(
            "services.online_collab.redis.online_collab_redis_health."
            "CriticalAlertService.send_startup_failure_alert_sync",
        ):
            await check_online_collab_redis_version(redis)
    exit_mock.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_check_version_warns_only_when_collab_disabled(monkeypatch):
    monkeypatch.setenv("COLLAB_DISABLED", "1")
    redis = MagicMock()
    redis.info = AsyncMock(return_value={"redis_version": "7.4.0"})
    with patch("os._exit") as exit_mock:
        await check_online_collab_redis_version(redis)
    exit_mock.assert_not_called()


@pytest.mark.asyncio
async def test_check_version_ok_at_8(monkeypatch):
    monkeypatch.delenv("COLLAB_DISABLED", raising=False)
    redis = MagicMock()
    redis.info = AsyncMock(return_value={"redis_version": "8.0.0"})
    with patch("os._exit") as exit_mock:
        await check_online_collab_redis_version(redis)
    exit_mock.assert_not_called()
