"""Redis failures in WebSocket metrics stay best-effort."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError

from services.infrastructure.monitoring import ws_metrics


def _redis_with_failing_pipeline(exc: Exception) -> MagicMock:
    pipe = MagicMock()
    pipe.execute = AsyncMock(side_effect=exc)
    pipe_ctx = MagicMock()
    pipe_ctx.__aenter__ = AsyncMock(return_value=pipe)
    pipe_ctx.__aexit__ = AsyncMock(return_value=False)
    client = MagicMock()
    client.pipeline.return_value = pipe_ctx
    return client


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "exc",
    [RedisTimeoutError("Timeout connecting to server"), RedisConnectionError("down")],
)
async def test_increment_active_total_swallows_redis_errors(exc: Exception) -> None:
    """A Redis outage must not escape WebSocket session teardown."""
    client = _redis_with_failing_pipeline(exc)
    with patch.object(ws_metrics, "get_async_redis", return_value=client):
        await ws_metrics.redis_increment_active_total(-1)


@pytest.mark.asyncio
async def test_metrics_snapshot_swallows_redis_timeout() -> None:
    """The health snapshot omits the Redis gauge when Redis times out."""
    client = MagicMock()
    client.get = AsyncMock(side_effect=RedisTimeoutError("Timeout connecting to server"))
    with patch.object(ws_metrics, "get_async_redis", return_value=client):
        snap = await ws_metrics.get_ws_metrics_snapshot()
    assert "ws_active_total_redis" not in snap
