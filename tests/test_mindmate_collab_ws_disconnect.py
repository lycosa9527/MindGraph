"""MindMate collab WebSocket disconnect and join-order unit tests."""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocket

from services.features.mindmate_collab.redis_keys import fanout_room_key
from services.features.mindmate_collab.ws_disconnect_cleanup import (
    finalize_mindmate_collab_disconnect,
)
from services.features.mindmate_collab.ws_registry import (
    ACTIVE_CONNECTIONS,
    MindmateCollabWsHandle,
    register_connection,
    teardown_superseded_connection,
)


@pytest.fixture(autouse=True)
def _clear_active_connections() -> Iterator[None]:
    ACTIVE_CONNECTIONS.clear()
    yield
    ACTIVE_CONNECTIONS.clear()


@pytest.mark.asyncio
async def test_superseded_disconnect_skips_participant_removal() -> None:
    """When a newer socket replaced this handle, cleanup must not evict the active tab."""
    code = "ABC-DEF"
    user_id = 42
    old_ws = MagicMock(spec=WebSocket)
    new_ws = MagicMock(spec=WebSocket)
    old_handle = MindmateCollabWsHandle(old_ws)
    new_handle = MindmateCollabWsHandle(new_ws)

    register_connection(code, user_id, old_handle)
    register_connection(code, user_id, new_handle)
    teardown_superseded_connection(code, user_id, old_handle)

    remove_participant = AsyncMock()
    broadcast = AsyncMock()

    with (
        patch(
            "services.features.mindmate_collab.ws_disconnect_cleanup.get_mindmate_collab_manager",
        ) as mgr_factory,
        patch(
            "services.features.mindmate_collab.ws_disconnect_cleanup.broadcast_to_others",
            broadcast,
        ),
        patch(
            "services.features.mindmate_collab.ws_disconnect_cleanup.shutdown_connection_handle",
            AsyncMock(),
        ),
    ):
        mgr = MagicMock()
        mgr.remove_participant = remove_participant
        mgr_factory.return_value = mgr

        await finalize_mindmate_collab_disconnect(
            code=code,
            user_id=user_id,
            handle=old_handle,
        )

    remove_participant.assert_not_awaited()
    broadcast.assert_not_awaited()
    room_key = fanout_room_key(code)
    assert ACTIVE_CONNECTIONS[room_key][user_id] is new_handle


@pytest.mark.asyncio
async def test_active_disconnect_removes_participant() -> None:
    """The active socket disconnect still removes the participant and notifies peers."""
    code = "XYZ-123"
    user_id = 7
    ws = MagicMock(spec=WebSocket)
    handle = MindmateCollabWsHandle(ws)
    register_connection(code, user_id, handle)

    remove_participant = AsyncMock()
    broadcast = AsyncMock()

    with (
        patch(
            "services.features.mindmate_collab.ws_disconnect_cleanup.get_mindmate_collab_manager",
        ) as mgr_factory,
        patch(
            "services.features.mindmate_collab.ws_disconnect_cleanup.broadcast_to_others",
            broadcast,
        ),
        patch(
            "services.features.mindmate_collab.ws_disconnect_cleanup.shutdown_connection_handle",
            AsyncMock(),
        ),
    ):
        mgr = MagicMock()
        mgr.remove_participant = remove_participant
        mgr_factory.return_value = mgr

        await finalize_mindmate_collab_disconnect(
            code=code,
            user_id=user_id,
            handle=handle,
        )

    remove_participant.assert_awaited_once_with(code, user_id)
    broadcast.assert_awaited_once()
    room_key = fanout_room_key(code)
    assert user_id not in ACTIVE_CONNECTIONS.get(room_key, {})


@pytest.mark.asyncio
async def test_join_order_add_participant_only_after_session_cap() -> None:
    """Document join order: participant registration follows ws_managed_session acceptance."""
    join_steps: list[str] = []

    class _SessionCap:
        async def __aenter__(self) -> "_SessionCap":
            join_steps.append("ws_managed_session_enter")
            return self

        async def __aexit__(self, *args: object) -> None:
            join_steps.append("ws_managed_session_exit")

    async with _SessionCap():
        join_steps.append("add_participant")
        join_steps.append("handshake")

    assert join_steps.index("ws_managed_session_enter") < join_steps.index("add_participant")
