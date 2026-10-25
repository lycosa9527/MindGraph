"""Edit/delete REST handlers broadcast workshop chat WebSocket events."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from routers.features.workshop_chat import messages as messages_mod
from routers.features.workshop_chat.schemas import EditMessageRequest
from services.features.workshop_ws_connection_state import ConnectionHandle, _writer_loop
from tests.typing_helpers import as_type, as_user, mock_await_args


@pytest.mark.asyncio
async def test_edit_message_broadcasts_ws_event() -> None:
    """Other clients must see the edited body without a reload."""
    updated = {
        "id": 12,
        "channel_id": 4,
        "topic_id": 6,
        "content": "edited",
    }
    with (
        patch.object(messages_mod, "access_channel_message", new=AsyncMock()),
        patch.object(
            messages_mod.message_service,
            "edit_message",
            new=AsyncMock(return_value=updated),
        ),
        patch.object(
            messages_mod.chat_ws_manager,
            "broadcast_to_channel",
            new=AsyncMock(),
        ) as broadcast,
    ):
        result = await messages_mod.edit_message(
            12,
            as_type(SimpleNamespace(content="edited"), EditMessageRequest),
            db=MagicMock(),
            current_user=as_user(SimpleNamespace(id=1)),
        )

    assert result == updated
    broadcast.assert_awaited_once()
    channel_id, payload = mock_await_args(broadcast)
    assert channel_id == 4
    assert payload["type"] == "message_edited"
    assert payload["message"] == updated


@pytest.mark.asyncio
async def test_delete_message_broadcasts_ws_event() -> None:
    """Soft-delete must fan out so other tabs drop the row."""
    message = SimpleNamespace(id=12, topic_id=6)
    channel = SimpleNamespace(id=4)
    with (
        patch.object(
            messages_mod,
            "access_channel_message",
            new=AsyncMock(return_value=(message, channel)),
        ),
        patch.object(
            messages_mod.message_service,
            "delete_message",
            new=AsyncMock(return_value=True),
        ),
        patch.object(
            messages_mod.chat_ws_manager,
            "broadcast_to_channel",
            new=AsyncMock(),
        ) as broadcast,
    ):
        result = await messages_mod.delete_message(
            12,
            db=MagicMock(),
            current_user=as_user(SimpleNamespace(id=1)),
        )

    assert result == {"ok": True}
    broadcast.assert_awaited_once()
    channel_id, payload = mock_await_args(broadcast)
    assert channel_id == 4
    assert payload["type"] == "message_deleted"
    assert payload["message_id"] == 12


@pytest.mark.asyncio
async def test_writer_loop_closes_on_disconnect() -> None:
    """A client drop during send is a normal close, not an unexpected task error."""
    ws = MagicMock()
    ws.send_text = AsyncMock(side_effect=WebSocketDisconnect())
    queue: asyncio.Queue = asyncio.Queue()
    await queue.put(("text", "hi"))
    handle = ConnectionHandle(
        websocket=ws,
        code="G8U-XSX",
        user_id=3751,
        send_queue=queue,
    )

    await _writer_loop(handle)
