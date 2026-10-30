"""Durable seminar fields are copied onto a live Redis hash after Postgres commits."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.features.mindmate_seminar.redis_mirror import mirror_live_session_fields


@pytest.mark.asyncio
async def test_mirror_updates_an_existing_live_hash() -> None:
    """A committed title lands on the room hash that already has a session id."""
    redis = AsyncMock()
    redis.hexists = AsyncMock(return_value=True)
    redis.hset = AsyncMock()
    with patch(
        "services.features.mindmate_seminar.redis_mirror.get_async_redis",
        return_value=redis,
    ):
        await mirror_live_session_fields("abc-def", {"title": "Renamed"})
    redis.hset.assert_awaited_once()
    assert redis.hset.await_args.kwargs["mapping"]["title"] == "Renamed"


@pytest.mark.asyncio
async def test_mirror_does_not_create_a_partial_hash() -> None:
    """A missing room hash stays missing until the next connect republishes the row."""
    redis = AsyncMock()
    redis.hexists = AsyncMock(return_value=False)
    redis.hset = AsyncMock()
    with patch(
        "services.features.mindmate_seminar.redis_mirror.get_async_redis",
        return_value=redis,
    ):
        await mirror_live_session_fields("abc-def", {"dify_conversation_id": "s1:conv"})
    redis.hset.assert_not_called()
