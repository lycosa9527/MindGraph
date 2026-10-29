"""MindMate collab WS broadcast shutdown and manager auth tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_seminar.manager import MindmateSeminarManager
from services.features.mindmate_seminar.ws_broadcast import (
    ROOM_IDLE_CLOSE_CODE,
    SESSION_ENDED_CLOSE_CODE,
    _dispatch_local,
)
from services.features.mindmate_seminar.ws_registry import (
    ACTIVE_CONNECTIONS,
    MindmateSeminarWsHandle,
)


@pytest.mark.asyncio
async def test_dispatch_local_idle_shutdown_force_closes_4010() -> None:
    """Idle shutdown fan-out closes local sockets with WebSocket code 4010."""
    room_key = "mms:ABCDEF"
    ws = MagicMock()
    ws.client_state = MagicMock()
    handle = MindmateSeminarWsHandle(ws)
    ACTIVE_CONNECTIONS[room_key] = {7: handle}

    with patch(
        "services.features.mindmate_seminar.ws_registry._close_handle",
        new_callable=AsyncMock,
    ) as close_mock:
        await _dispatch_local(room_key, '{"type":"room_idle_shutdown"}', None)

    close_mock.assert_awaited_once_with(handle, ROOM_IDLE_CLOSE_CODE, "seminar expired")
    assert room_key not in ACTIVE_CONNECTIONS


@pytest.mark.asyncio
async def test_dispatch_local_session_ended_force_closes_4011() -> None:
    """Host stop fan-out closes local sockets with WebSocket code 4011."""
    room_key = "mms:XYZ123"
    ws = MagicMock()
    handle = MindmateSeminarWsHandle(ws)
    ACTIVE_CONNECTIONS[room_key] = {3: handle}

    with patch(
        "services.features.mindmate_seminar.ws_registry._close_handle",
        new_callable=AsyncMock,
    ) as close_mock:
        await _dispatch_local(room_key, '{"type":"session_ended_shutdown"}', None)

    close_mock.assert_awaited_once_with(handle, SESSION_ENDED_CLOSE_CODE, "session ended by host")
    assert room_key not in ACTIVE_CONNECTIONS


@pytest.mark.asyncio
async def test_user_may_connect_denies_network_without_membership() -> None:
    """Public seminars are closed: a code holder who was not added cannot connect."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-net"
    session.expires_at = None
    session.visibility = "network"
    session.owner_user_id = 1

    with (
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.manager.list_invited_member_ids",
            AsyncMock(return_value=[]),
        ),
        patch(
            "services.features.mindmate_seminar.manager.accepted_member_ids",
            AsyncMock(return_value=[]),
        ),
    ):
        allowed = await mgr.user_may_connect(99, session)

    assert allowed is False


@pytest.mark.asyncio
async def test_user_may_connect_allows_accepted_network_member() -> None:
    """A school or accepted member can open the public seminar."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-net"
    session.expires_at = None
    session.visibility = "network"
    session.owner_user_id = 1

    with (
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.manager.list_invited_member_ids",
            AsyncMock(return_value=[99]),
        ),
        patch(
            "services.features.mindmate_seminar.manager.accepted_member_ids",
            AsyncMock(return_value=[99]),
        ),
    ):
        allowed = await mgr.user_may_connect(99, session)

    assert allowed is True


@pytest.mark.asyncio
async def test_user_may_connect_denies_pending_network_member() -> None:
    """Cross-school invitees stay out until they agree."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-net"
    session.expires_at = None
    session.visibility = "network"
    session.owner_user_id = 1

    with (
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=True),
        ),
        patch(
            "services.features.mindmate_seminar.manager.list_invited_member_ids",
            AsyncMock(return_value=[99]),
        ),
        patch(
            "services.features.mindmate_seminar.manager.accepted_member_ids",
            AsyncMock(return_value=[]),
        ),
    ):
        allowed = await mgr.user_may_connect(99, session)

    assert allowed is False


@pytest.mark.asyncio
async def test_open_school_seminar_stays_open_after_the_host_is_recorded() -> None:
    """The host history row does not turn a school seminar into an invite-only room."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-org"
    session.visibility = "organization"
    session.owner_user_id = 1
    session.organization_id = 4
    db_ctx = AsyncMock()
    db_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    db_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.features.mindmate_seminar.manager.user_rls_session",
            return_value=db_ctx,
        ),
        patch(
            "services.features.mindmate_seminar.manager.user_may_join_mindmate_seminar",
            AsyncMock(return_value=True),
        ) as may_join,
    ):
        allowed = await mgr.user_may_connect(2, session)

    assert allowed is True
    may_join.assert_awaited_once()


@pytest.mark.asyncio
async def test_open_school_seminar_still_rejects_another_school() -> None:
    """An open school seminar still checks the joiner's school."""
    mgr = MindmateSeminarManager()
    session = MagicMock()
    session.id = "sess-org"
    session.visibility = "organization"
    session.owner_user_id = 1
    session.organization_id = 4
    db_ctx = AsyncMock()
    db_ctx.__aenter__ = AsyncMock(return_value=AsyncMock())
    db_ctx.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "services.features.mindmate_seminar.manager.seminar_room_is_closed",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.features.mindmate_seminar.manager.user_rls_session",
            return_value=db_ctx,
        ),
        patch(
            "services.features.mindmate_seminar.manager.user_may_join_mindmate_seminar",
            AsyncMock(return_value=False),
        ),
    ):
        allowed = await mgr.user_may_connect(99, session)

    assert allowed is False


@pytest.mark.asyncio
async def test_add_participant_returns_false_when_room_full() -> None:
    """Participant cap Lua script returning -1 surfaces as join failure."""
    mgr = MindmateSeminarManager()
    redis = AsyncMock()
    redis.hlen = AsyncMock(return_value=50)

    with (
        patch("services.features.mindmate_seminar.manager.get_async_redis", return_value=redis),
        patch(
            "services.features.mindmate_seminar.manager.evalsha_with_reload",
            new_callable=AsyncMock,
            return_value=-1,
        ),
    ):
        ok = await mgr.add_participant("ABC-DEF", 42)

    assert ok is False
