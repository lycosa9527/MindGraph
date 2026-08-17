"""Async Redis client must not outlive the asyncio loop that created it."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from services.redis import redis_async_client


def test_get_async_redis_rebuilds_after_loop_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Celery prefork runs ``asyncio.run`` per task; the second loop needs a new client."""
    built: list[MagicMock] = []

    def _fake_build() -> MagicMock:
        client = MagicMock(name=f"redis-{len(built)}")
        built.append(client)
        return client

    monkeypatch.setattr(redis_async_client, "_build_async_client", _fake_build)

    async def _use() -> object:
        return redis_async_client.get_async_redis()

    async def _reset() -> None:
        await redis_async_client.close_async_redis()

    asyncio.run(_reset())
    first = asyncio.run(_use())
    second = asyncio.run(_use())
    assert first is not second
    assert len(built) == 2
    asyncio.run(_reset())
