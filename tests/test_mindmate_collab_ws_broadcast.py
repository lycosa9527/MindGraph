"""MindMate collab WS broadcast shutdown and manager auth tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.manager import MindmateCollabManager
from services.features.mindmate_collab.ws_broadcast import (
    ROOM_IDLE_CLOSE_CODE,
    SESSION_ENDED_CLOSE_CODE,
    _dispatch_local,
)
from services.features.mindmate_collab.ws_registry import (
    ACTIVE_CONNECTIONS,
    MindmateCollabWsHandle,
)


@pytest.mark.asyncio
async def test_dispatch_local_idle_shutdown_force_closes_4010() -> None:
    """Idle shutdown fan-out closes local sockets with WebSocket code 4010."""
    room_key = "mmc:ABCDEF"
    ws = MagicMock()
    ws.client_state = MagicMock()
    handle = MindmateCollabWsHandle(ws)
    ACTIVE_CONNECTIONS[room_key] = {7: handle}

    with patch(
        "services.features.mindmate_collab.ws_registry._close_handle",
        new_callable=AsyncMock,
    ) as close_mock:
        await _dispatch_local(room_key, '{"type":"room_idle_shutdown"}', None)

    close_mock.assert_awaited_once_with(handle, ROOM_IDLE_CLOSE_CODE, "room idle timeout")
    assert room_key not in ACTIVE_CONNECTIONS


@pytest.mark.asyncio
async def test_dispatch_local_session_ended_force_closes_4011() -> None:
    """Host stop fan-out closes local sockets with WebSocket code 4011."""
    room_key = "mmc:XYZ123"
    ws = MagicMock()
    handle = MindmateCollabWsHandle(ws)
    ACTIVE_CONNECTIONS[room_key] = {3: handle}

    with patch(
        "services.features.mindmate_collab.ws_registry._close_handle",
        new_callable=AsyncMock,
    ) as close_mock:
        await _dispatch_local(room_key, '{"type":"session_ended_shutdown"}', None)

    close_mock.assert_awaited_once_with(handle, SESSION_ENDED_CLOSE_CODE, "session ended by host")
    assert room_key not in ACTIVE_CONNECTIONS


@pytest.mark.asyncio
async def test_user_may_connect_allows_network_without_db() -> None:
    """Network-visible rooms allow any authenticated joiner at the WS gate."""
    mgr = MindmateCollabManager()
    session = MagicMock()
    session.expires_at = None
    session.visibility = "network"
    allowed = await mgr.user_may_connect(99, session)
    assert allowed is True


@pytest.mark.asyncio
async def test_user_may_connect_denies_expired_session() -> None:
    """Expired sessions are rejected before WebSocket accept."""
    mgr = MindmateCollabManager()
    session = MagicMock()
    session.expires_at = MagicMock()
    session.visibility = "network"

    with patch(
        "services.features.mindmate_collab.manager.is_online_collab_expired",
        return_value=True,
    ):
        allowed = await mgr.user_may_connect(1, session)

    assert allowed is False


@pytest.mark.asyncio
async def test_add_participant_returns_false_when_room_full() -> None:
    """Participant cap Lua script returning -1 surfaces as join failure."""
    mgr = MindmateCollabManager()
    redis = AsyncMock()
    redis.hlen = AsyncMock(return_value=50)

    with (
        patch("services.features.mindmate_collab.manager.get_async_redis", return_value=redis),
        patch(
            "services.features.mindmate_collab.manager.evalsha_with_reload",
            new_callable=AsyncMock,
            return_value=-1,
        ),
    ):
        ok = await mgr.add_participant("ABC-DEF", 42)

    assert ok is False
