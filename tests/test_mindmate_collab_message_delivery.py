"""MindMate collab chat delivery: snapshot order, fan-out miss, and catch-up."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.message_history import catchup_frames, history_row_ids
from services.features.mindmate_collab.ws_broadcast import _push_local, broadcast_to_all
from services.features.mindmate_collab.ws_registry import (
    ACTIVE_CONNECTIONS,
    MindmateCollabWsHandle,
    enqueue_json,
)


def test_catchup_frames_skip_snapshot_rows() -> None:
    """Only rows saved after the join snapshot become extra frames."""
    baseline = [{"id": 1, "role": "user", "content": "already"}]
    fresh = [
        {"id": 1, "role": "user", "content": "already", "sender_user_id": 4, "username": "ada"},
        {"id": 2, "role": "user", "content": "missed", "sender_user_id": 8, "username": "bea"},
        {"id": 3, "role": "assistant", "content": "reply"},
    ]
    frames = catchup_frames(history_row_ids(baseline), fresh)
    assert [frame["type"] for frame in frames] == ["user_message", "ai_message_end"]
    assert frames[0]["content"] == "missed"
    assert frames[0]["sender_user_id"] == 8
    assert frames[0]["prev_id"] == 1
    assert frames[1]["id"] == 3
    assert frames[1]["prev_id"] == 2


@pytest.mark.asyncio
async def test_push_local_waits_until_snapshot_is_queued() -> None:
    """Join holds fan-out until the history snapshot is already in the queue."""
    room_key = "mmc:HOLD01"
    handle = MindmateCollabWsHandle(MagicMock())
    handle.accepts_fanout = False
    ACTIVE_CONNECTIONS[room_key] = {4: handle}
    try:
        await _push_local(
            room_key,
            json.dumps({"type": "user_message", "id": 2, "content": "early"}),
            None,
        )
        assert handle.send_queue.empty()
        assert enqueue_json(handle, {"type": "snapshot", "messages": []})
        handle.accepts_fanout = True
        await _push_local(
            room_key,
            json.dumps({"type": "user_message", "id": 2, "content": "early"}),
            None,
        )
        first = json.loads(handle.send_queue.get_nowait()[1])
        second = json.loads(handle.send_queue.get_nowait()[1])
        assert first["type"] == "snapshot"
        assert second["type"] == "user_message"
    finally:
        ACTIVE_CONNECTIONS.pop(room_key, None)


def test_full_queue_keeps_user_message_over_stream_chunk() -> None:
    """A chat line replaces a queued AI chunk instead of being dropped."""
    handle = MindmateCollabWsHandle(MagicMock())
    handle.send_queue = asyncio.Queue(maxsize=1)
    assert enqueue_json(handle, {"type": "ai_message_chunk", "content": "tok"})
    assert enqueue_json(handle, {"type": "user_message", "id": 5, "content": "hi"})
    queued = json.loads(handle.send_queue.get_nowait()[1])
    assert queued["type"] == "user_message"
    assert queued["content"] == "hi"
    assert handle.send_queue.empty()


@pytest.mark.asyncio
async def test_broadcast_delivers_locally_when_fanout_has_no_subscribers() -> None:
    """A publish that reaches nobody still lands on sockets in this process."""
    room_key = "mmc:ABC-DEF"
    handle = MindmateCollabWsHandle(MagicMock())
    ACTIVE_CONNECTIONS[room_key] = {4: handle}
    try:
        with (
            patch(
                "services.features.mindmate_collab.ws_broadcast.is_ws_fanout_enabled",
                return_value=True,
            ),
            patch(
                "services.features.mindmate_collab.ws_broadcast.publish_workshop_fanout_async",
                new_callable=AsyncMock,
                return_value=0,
            ),
        ):
            await broadcast_to_all(
                "ABC-DEF",
                {"type": "user_message", "id": 3, "content": "hello"},
            )
        queued = json.loads(handle.send_queue.get_nowait()[1])
        assert queued["type"] == "user_message"
        assert queued["content"] == "hello"
    finally:
        ACTIVE_CONNECTIONS.pop(room_key, None)


@pytest.mark.asyncio
async def test_broadcast_does_not_double_deliver_when_subscribers_exist() -> None:
    """Local sockets receive the frame from the fan-out listener, not twice."""
    room_key = "mmc:ABC-DEF"
    handle = MindmateCollabWsHandle(MagicMock())
    ACTIVE_CONNECTIONS[room_key] = {4: handle}
    try:
        with (
            patch(
                "services.features.mindmate_collab.ws_broadcast.is_ws_fanout_enabled",
                return_value=True,
            ),
            patch(
                "services.features.mindmate_collab.ws_broadcast.publish_workshop_fanout_async",
                new_callable=AsyncMock,
                return_value=2,
            ),
        ):
            await broadcast_to_all(
                "ABC-DEF",
                {"type": "user_message", "id": 3, "content": "hello"},
            )
        assert handle.send_queue.empty()
    finally:
        ACTIVE_CONNECTIONS.pop(room_key, None)
