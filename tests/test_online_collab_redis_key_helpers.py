"""Unit tests for collab Redis key helpers (no Redis I/O)."""

from __future__ import annotations

from typing import Any, AsyncIterator

import pytest

from services.online_collab.redis.online_collab_redis_keys import (
    client_op_dedupe_key,
    purge_online_collab_redis_keys,
    resync_rate_limit_key,
)


def test_resync_rate_limit_key_stable_shape(monkeypatch):
    """Test resync rate limit key stable shape."""
    monkeypatch.setenv("COLLAB_REDIS_HASH_TAGS", "0")
    key = resync_rate_limit_key("ABC", 42)
    assert "ABC" in key
    assert "42" in key


def test_client_op_dedupe_truncates_long_id(monkeypatch):
    """Test client op dedupe truncates long id."""
    monkeypatch.setenv("COLLAB_REDIS_HASH_TAGS", "0")
    long_id = "x" * 200
    key = client_op_dedupe_key("ROOM", 7, long_id)
    assert len(key) < len(long_id) + 80


class _FailingPipeline:
    """_FailingPipeline helper."""

    def delete(self, *_keys: str) -> "_FailingPipeline":
        """Delete."""
        return self

    async def execute(self) -> None:
        """Execute."""
        raise RuntimeError("cross-slot")

    async def __aenter__(self) -> "_FailingPipeline":
        """aenter  ."""
        return self

    async def __aexit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> bool:
        """aexit  ."""
        return False


class _PurgeRedis:
    """_PurgeRedis helper."""

    def __init__(self) -> None:
        """init  ."""
        self.unlinked: list[str] = []
        self.deleted: list[str] = []
        self.zrem_calls: list[tuple[str, str]] = []
        self.srem_calls: list[tuple[str, str]] = []

    async def hgetall(self, _key: str) -> dict[bytes, bytes]:
        """Hgetall."""
        return {b"org_id": b"88", b"visibility": b"organization"}

    def pipeline(self, **_kwargs: Any) -> _FailingPipeline:
        """Pipeline."""
        return _FailingPipeline()

    async def unlink(self, key: str) -> int:
        """Unlink."""
        self.unlinked.append(key)
        return 1

    async def delete(self, key: str) -> int:
        """Delete."""
        self.deleted.append(key)
        return 1

    async def zrem(self, key: str, code: str) -> int:
        """Zrem."""
        self.zrem_calls.append((key, code))
        return 1

    async def srem(self, key: str, code: str) -> int:
        """Srem."""
        self.srem_calls.append((key, code))
        return 1

    async def scan_iter(self, **_kwargs: Any) -> AsyncIterator[str]:
        """Scan iter."""
        for item in ():
            yield item


@pytest.mark.asyncio
async def test_purge_cleans_global_indexes_after_room_key_fallback(monkeypatch):
    """Test purge cleans global indexes after room key fallback."""
    monkeypatch.setenv("COLLAB_REDIS_HASH_TAGS", "1")
    redis = _PurgeRedis()

    await purge_online_collab_redis_keys(redis, "ABC-123")

    assert redis.unlinked
    assert redis.zrem_calls == [("workshop:idle_scores", "ABC-123")]
    assert ("workshop:registry:org:{88}", "ABC-123") in redis.srem_calls
