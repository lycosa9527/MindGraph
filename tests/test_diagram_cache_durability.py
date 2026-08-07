"""Tests for diagram cache durability (Layer D): invalidate + soft CAS helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.api.diagrams import _as_utc_aware_datetime, _updated_at_matches
from services.redis.cache._redis_diagram_cache_helpers import DIAGRAM_KEY, USER_LIST_KEY
from services.redis.cache.redis_diagram_cache import RedisDiagramCache


def test_as_utc_aware_datetime_accepts_z_suffix() -> None:
    """Z and +00:00 normalize to the same UTC instant."""
    with_z = _as_utc_aware_datetime("2026-01-01T12:00:00Z")
    with_offset = _as_utc_aware_datetime("2026-01-01T12:00:00+00:00")
    assert with_z == with_offset
    assert with_z.tzinfo is not None


def test_updated_at_matches_tolerant_of_z_vs_offset() -> None:
    """CAS compare treats Z and +00:00 as equal."""
    expected = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert _updated_at_matches(expected, "2026-01-01T12:00:00Z") is True
    assert _updated_at_matches(expected, "2026-01-01T12:00:00+00:00") is True
    assert _updated_at_matches(expected, "2026-01-01T12:00:01Z") is False
    assert _updated_at_matches(expected, None) is False


def test_updated_at_matches_naive_stored_as_utc() -> None:
    """Naive stored timestamps are treated as UTC."""
    expected = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert _updated_at_matches(expected, "2026-01-01T12:00:00") is True


@pytest.mark.asyncio
async def test_invalidate_diagram_deletes_diagram_and_list_keys() -> None:
    """invalidate_diagram removes per-diagram and list Redis keys."""
    cache = RedisDiagramCache()
    pipe = MagicMock()
    pipe.delete = MagicMock(return_value=pipe)
    pipe.execute = AsyncMock(return_value=[1, 1])
    pipe_ctx = MagicMock()
    pipe_ctx.__aenter__ = AsyncMock(return_value=pipe)
    pipe_ctx.__aexit__ = AsyncMock(return_value=None)

    redis = MagicMock()
    redis.pipeline = MagicMock(return_value=pipe_ctx)

    with (
        patch.object(cache, "_use_redis", return_value=True),
        patch(
            "services.redis.cache.redis_diagram_cache.get_async_redis",
            return_value=redis,
        ),
    ):
        await cache.invalidate_diagram(7, "diag-1")

    pipe.delete.assert_any_call(DIAGRAM_KEY.format(user_id=7, diagram_id="diag-1"))
    pipe.delete.assert_any_call(USER_LIST_KEY.format(user_id=7))
    pipe.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_save_diagram_deletes_key_when_redis_write_fails() -> None:
    """After DB success, Redis write failure must delete the diagram key."""
    cache = RedisDiagramCache()
    redis = MagicMock()
    redis.pipeline = MagicMock(side_effect=ConnectionError("redis down"))
    redis.delete = AsyncMock(return_value=1)

    with (
        patch.object(cache, "_use_redis", return_value=True),
        patch(
            "services.redis.cache.redis_diagram_cache.get_async_redis",
            return_value=redis,
        ),
        patch.object(cache, "_resolve_diagram_cap", new=AsyncMock(return_value=100)),
        patch.object(
            cache,
            "get_diagram",
            new=AsyncMock(
                return_value={
                    "id": "diag-1",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "is_pinned": False,
                    "folder_id": None,
                }
            ),
        ),
        patch.object(
            cache,
            "_update_in_database",
            new=AsyncMock(return_value=(True, None)),
        ),
    ):
        ok, diagram_id, error = await cache.save_diagram(
            user_id=7,
            diagram_id="diag-1",
            title="T",
            diagram_type="mind_map",
            spec={"topic": "x"},
        )

    assert ok is True
    assert diagram_id == "diag-1"
    assert error is None
    redis.delete.assert_awaited_once_with(DIAGRAM_KEY.format(user_id=7, diagram_id="diag-1"))
