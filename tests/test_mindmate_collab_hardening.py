"""MindMate collab production hardening unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.config import MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS
from services.features.mindmate_collab.dify_stream_control import acquire_dify_stream_lock
from services.features.mindmate_collab.manager import MindmateCollabManager


@pytest.mark.asyncio
async def test_acquire_dify_stream_lock_fails_closed_without_redis() -> None:
    """Stream lock acquisition fails when Redis is unavailable."""
    with patch(
        "services.features.mindmate_collab.dify_stream_control.get_async_redis",
        return_value=None,
    ):
        assert await acquire_dify_stream_lock("ABC-DEF") is False


@pytest.mark.asyncio
async def test_acquire_dify_stream_lock_fails_closed_on_redis_error() -> None:
    """Stream lock acquisition fails closed when Redis raises."""
    redis = AsyncMock()
    redis.set = AsyncMock(side_effect=ConnectionError("down"))
    with patch(
        "services.features.mindmate_collab.dify_stream_control.get_async_redis",
        return_value=redis,
    ):
        assert await acquire_dify_stream_lock("ABC-DEF") is False


@pytest.mark.asyncio
async def test_session_is_closing_true_when_marker_present() -> None:
    """Closing marker in Redis blocks new joins."""
    mgr = MindmateCollabManager()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=b"1")
    with patch(
        "services.features.mindmate_collab.manager.get_async_redis",
        return_value=redis,
    ):
        assert await mgr.session_is_closing("abc-def") is True


@pytest.mark.asyncio
async def test_session_is_closing_false_when_marker_absent() -> None:
    """Rooms without a closing marker accept joins."""
    mgr = MindmateCollabManager()
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    with patch(
        "services.features.mindmate_collab.manager.get_async_redis",
        return_value=redis,
    ):
        assert await mgr.session_is_closing("abc-def") is False


@pytest.mark.asyncio
async def test_start_session_rolls_back_db_when_redis_write_fails() -> None:
    """Start flow marks the DB row ended when Redis session write fails."""
    mgr = MindmateCollabManager()
    user = MagicMock()
    user.id = 9
    user.organization_id = 2
    user.name = "Host"
    user.phone = None
    user.email = None

    fake_sess = AsyncMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none.return_value = user
    fake_sess.execute = AsyncMock(return_value=fake_result)
    fake_sess.add = MagicMock()
    fake_sess.commit = AsyncMock()
    fake_sess.rollback = AsyncMock()

    user_ctx = AsyncMock()
    user_ctx.__aenter__ = AsyncMock(return_value=fake_sess)
    user_ctx.__aexit__ = AsyncMock(return_value=None)

    system_sess = AsyncMock()
    system_sess.execute = AsyncMock()
    system_sess.commit = AsyncMock()
    system_ctx = AsyncMock()
    system_ctx.__aenter__ = AsyncMock(return_value=system_sess)
    system_ctx.__aexit__ = AsyncMock(return_value=None)

    redis = AsyncMock()
    redis.set = AsyncMock(return_value=True)

    with (
        patch(
            "services.features.mindmate_collab.manager.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.features.mindmate_collab.manager.acquire_nx_lock",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_collab.manager.release_nx_lock",
            AsyncMock(),
        ),
        patch.object(mgr, "stop_hosted_sessions_for_user", AsyncMock(return_value=0)),
        patch(
            "services.features.mindmate_collab.manager.user_rls_session",
            return_value=user_ctx,
        ),
        patch(
            "services.features.mindmate_collab.manager.system_rls_session",
            return_value=system_ctx,
        ),
        patch(
            "services.features.mindmate_collab.manager._allocate_unique_online_collab_code",
            AsyncMock(return_value="ABC-DEF"),
        ),
        patch.object(mgr, "_write_redis_session", AsyncMock(return_value=False)),
    ):
        payload, error = await mgr.start_session(9, title="Room")

    assert payload is None
    assert error == "Collaboration service unavailable"
    system_sess.execute.assert_awaited_once()
    system_sess.commit.assert_awaited_once()


def test_default_chat_content_cap_is_reasonable() -> None:
    """Default chat content cap stays within practical UI bounds."""
    assert 256 <= MINDMATE_COLLAB_MAX_CHAT_CONTENT_CHARS <= 65536
