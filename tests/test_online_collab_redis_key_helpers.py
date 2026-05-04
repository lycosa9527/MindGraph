"""Unit tests for collab Redis key helpers (no Redis I/O)."""

from __future__ import annotations

from services.online_collab.redis.online_collab_redis_keys import (
    client_op_dedupe_key,
    resync_rate_limit_key,
)


def test_resync_rate_limit_key_stable_shape(monkeypatch):
    monkeypatch.setenv("COLLAB_REDIS_HASH_TAGS", "0")
    key = resync_rate_limit_key("ABC", 42)
    assert "ABC" in key
    assert "42" in key


def test_client_op_dedupe_truncates_long_id(monkeypatch):
    monkeypatch.setenv("COLLAB_REDIS_HASH_TAGS", "0")
    long_id = "x" * 200
    key = client_op_dedupe_key("ROOM", 7, long_id)
    assert len(key) < len(long_id) + 80
