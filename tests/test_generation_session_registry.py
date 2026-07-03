"""Tests for generation session registry."""

from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.diagram.generation_session_registry import (
    SESSION_PREFIX,
    lookup_generation_session,
    lookup_solo_recent_mindbot_session,
    register_generation_session,
)


@pytest.mark.asyncio
async def test_register_generation_session_mindmate() -> None:
    """MindMate session stores user id and dify key."""
    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)
    with patch(
        "services.diagram.generation_session_registry.get_async_redis",
        return_value=redis,
    ):
        ok = await register_generation_session(
            channel="web",
            dify_user_id="mg_user_3",
            user_id=3,
            organization_id=9,
            conversation_id="conv-abc",
        )
    assert ok is True
    keys = [call.args[0] for call in redis.set.await_args_list]
    assert f"{SESSION_PREFIX}dify:mg_user_3" in keys
    assert f"{SESSION_PREFIX}conv:conv-abc" in keys


@pytest.mark.asyncio
async def test_lookup_generation_session_by_conversation() -> None:
    """Conversation id returns registered MindMate user."""
    payload = json.dumps(
        {
            "channel": "mindmate",
            "dify_user_id": "mg_user_3",
            "organization_id": 9,
            "user_id": 3,
            "registered_at": time.time(),
        }
    )
    redis = MagicMock()
    redis.get = AsyncMock(return_value=payload)
    with patch(
        "services.diagram.generation_session_registry.get_async_redis",
        return_value=redis,
    ):
        ctx = await lookup_generation_session(conversation_id="conv-abc")
    assert ctx is not None
    assert ctx["user_id"] == 3
    assert ctx["dify_user_id"] == "mg_user_3"


@pytest.mark.asyncio
async def test_lookup_solo_recent_mindbot_session() -> None:
    """Single active MindBot session resolves by dify key."""
    payload = json.dumps(
        {
            "channel": "mindbot",
            "dify_user_id": "mindbot_5_staff42",
            "organization_id": 5,
            "user_id": 3,
            "registered_at": time.time(),
        }
    )
    redis = MagicMock()
    redis.zrangebyscore = AsyncMock(return_value=[b"mindbot_5_staff42"])
    redis.get = AsyncMock(return_value=payload)
    with patch(
        "services.diagram.generation_session_registry.get_async_redis",
        return_value=redis,
    ):
        ctx = await lookup_solo_recent_mindbot_session()
    assert ctx is not None
    assert ctx["user_id"] == 3


@pytest.mark.asyncio
async def test_lookup_solo_recent_mindbot_session_ambiguous() -> None:
    """Multiple active MindBot sessions return None."""
    redis = MagicMock()
    redis.zrangebyscore = AsyncMock(return_value=[b"mindbot_5_a", b"mindbot_5_b"])
    with patch(
        "services.diagram.generation_session_registry.get_async_redis",
        return_value=redis,
    ):
        ctx = await lookup_solo_recent_mindbot_session()
    assert ctx is None
