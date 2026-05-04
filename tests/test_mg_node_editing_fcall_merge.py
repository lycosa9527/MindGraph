"""
Integration test for mg_node_editing Redis Function merge semantics.

Requires Redis 7+ with FUNCTION + FCALL and optional HEXPIRE. Skips when
``REDIS_TEST_URL`` is unset or the server is unreachable.
"""

from __future__ import annotations

import json
import os
import uuid

import pytest

pytest.importorskip("redis.asyncio")


@pytest.mark.asyncio
async def test_mg_node_editing_set_merges_two_users_on_same_node() -> None:
    import redis.asyncio as redis_async

    from services.online_collab.redis.online_collab_redis_locks import (
        ensure_online_collab_functions_loaded,
        fcall_node_editing_del,
        fcall_node_editing_set,
    )

    url = os.environ.get("REDIS_TEST_URL", "redis://127.0.0.1:6379/15")
    client = redis_async.from_url(url, decode_responses=True)
    try:
        await client.ping()
    except (OSError, RuntimeError):
        await client.aclose()
        pytest.skip("Redis not reachable for FCALL merge test")

    loaded = await ensure_online_collab_functions_loaded(client)
    if not loaded:
        await client.aclose()
        pytest.skip("Redis Functions not available")

    room = uuid.uuid4().hex[:12]
    key = f"mg:test:node_editing:{{{room}}}"
    field = "node-a"
    try:
        await client.delete(key)
        assert await fcall_node_editing_set(
            client, key, field, "1", "alice", 30, 3600,
        )
        assert await fcall_node_editing_set(
            client, key, field, "2", "bob", 30, 3600,
        )
        raw = await client.hget(key, field)
        assert raw is not None
        data = json.loads(raw)
        assert data.get("1") == "alice"
        assert data.get("2") == "bob"

        assert await fcall_node_editing_del(client, key, field, "1", 30, 3600)
        raw2 = await client.hget(key, field)
        assert raw2 is not None
        data2 = json.loads(raw2)
        assert data2 == {"2": "bob"}

        assert await fcall_node_editing_del(client, key, field, "2", 30, 3600)
        assert await client.hget(key, field) is None
    finally:
        await client.delete(key)
        await client.aclose()
