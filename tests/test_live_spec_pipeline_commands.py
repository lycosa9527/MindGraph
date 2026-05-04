"""Live-spec mutate path issues a single RedisJSON pipeline."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.online_collab.spec.online_collab_live_spec_ops import (
    mutate_live_spec_after_ws_update,
)


class _FakePipeline:
    """Captures pipeline commands; returns a fixed ``execute()`` result list."""

    def __init__(self, execute_results):
        self._execute_results = execute_results
        self.records = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def execute_command(self, *args):
        self.records.append(("execute_command", args))
        return self

    def expire(self, key, ttl_sec, **kwargs):
        self.records.append(("expire", key, ttl_sec, kwargs))
        return self

    def sadd(self, key, *members):
        self.records.append(("sadd", key, members))
        return self

    def incr(self, key):
        self.records.append(("incr", key))
        return self

    async def execute(self):
        return self._execute_results


@pytest.mark.asyncio
async def test_mutate_granular_json_merge_pipeline(monkeypatch):
    current = {"v": 1, "nodes": [], "type": "mindmap"}
    # Pipeline for a granular update (no deletions): JSON.MERGE, expire(key),
    # sadd(ck_key), expire(ck_key), incr(seq_key) — 5 commands, no NUMINCRBY.
    fake = _FakePipeline(
        [True, True, 1, True, 42],
    )
    redis = MagicMock()
    redis.pipeline = MagicMock(side_effect=lambda **_: fake)
    redis.setex = AsyncMock()

    monkeypatch.setattr(
        "services.online_collab.spec.online_collab_live_spec_ops."
        "collab_hash_tags_enabled",
        lambda: False,
    )
    with patch(
        "services.online_collab.spec.online_collab_live_spec_ops.json_get_live_spec",
        new_callable=AsyncMock,
        return_value=current,
    ), patch(
        "services.online_collab.spec.online_collab_live_spec_ops._nodes_minus_tombstones",
        new_callable=AsyncMock,
        return_value=[{"id": "n1", "text": "hello"}],
    ), patch(
        "services.online_collab.spec.online_collab_live_spec_ops.fcall_spec_granular_apply",
        new_callable=AsyncMock,
        return_value=None,
    ):
        out = await mutate_live_spec_after_ws_update(
            redis,
            "ROOM1",
            "diagram-id",
            3600,
            spec=None,
            nodes=[{"id": "n1", "text": "hello"}],
            connections=None,
        )

    assert out is not None
    # version is computed in-app as current["v"] + 1 and written inside the MERGE patch
    assert out["v"] == 2
    assert out["__seq__"] == 42

    rec = fake.records
    merge = rec[0][1]
    assert merge[0] == "JSON.MERGE"
    assert merge[2] == "$"
    patch_loaded = json.loads(merge[3])
    assert "nodes" in patch_loaded
    # Version is written explicitly inside the MERGE patch (no separate NUMINCRBY).
    assert patch_loaded["v"] == 2
    assert rec[1][0] == "expire"
    assert rec[2][0] == "sadd"
    assert rec[3][0] == "expire"
    assert rec[4][0] == "incr"
    redis.setex.assert_awaited_once()


@pytest.mark.asyncio
async def test_mutate_full_replace_json_set_pipeline(monkeypatch):
    current = {"v": 5, "nodes": [{"id": "old"}], "type": "mindmap"}
    fake = _FakePipeline([True, True, 1, True, 99])
    redis = MagicMock()
    redis.pipeline = MagicMock(side_effect=lambda **_: fake)
    redis.setex = AsyncMock()

    monkeypatch.setattr(
        "services.online_collab.spec.online_collab_live_spec_ops."
        "collab_hash_tags_enabled",
        lambda: False,
    )
    replacement = {"type": "mindmap", "nodes": []}
    with patch(
        "services.online_collab.spec.online_collab_live_spec_ops.json_get_live_spec",
        new_callable=AsyncMock,
        return_value=current,
    ):
        out = await mutate_live_spec_after_ws_update(
            redis,
            "ROOM1",
            "diagram-id",
            3600,
            spec=replacement,
            nodes=None,
            connections=None,
        )

    assert out is not None
    assert out["v"] == 6
    assert out["__seq__"] == 99

    rec = fake.records
    assert rec[0][0] == "execute_command"
    assert rec[0][1][0] == "JSON.SET"
    assert rec[0][1][2] == "$"
    loaded = json.loads(rec[0][1][3])
    assert loaded["type"] == "mindmap"
    assert loaded["nodes"] == []
    assert rec[1][0] == "expire"
    assert rec[2][0] == "sadd"
    assert rec[2][2] == ("__full__",)
    assert rec[3][0] == "expire"
    assert rec[4][0] == "incr"
    redis.setex.assert_awaited_once()
