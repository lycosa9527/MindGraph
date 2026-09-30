"""
In-process WebSocket registry for MindMate collab rooms.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from services.features.mindmate_collab.redis_keys import fanout_room_key, normalize_collab_code
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

# Reconnectable close when this socket can no longer be given room frames.
DELIVERY_FAILURE_CLOSE_CODE = 1011

# room_key -> user_id -> handle
ACTIVE_CONNECTIONS: Dict[str, Dict[int, "MindmateCollabWsHandle"]] = {}

# Frames a peer must not lose. Stream chunks may be dropped; the end frame has the full text.
_RETAINED_FRAME_TYPES = frozenset(
    {
        "user_message",
        "ai_message_end",
        "joined",
        "snapshot",
        "error",
        "pong",
        "session_closing",
        "room_idle_warning",
        "user_joined",
        "user_left",
        "read_cursor",
        "read_cursors",
        "resync",
    },
)


class MindmateCollabWsHandle:
    """Local WebSocket handle with outbound queue and writer task."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.send_queue: asyncio.Queue[tuple[str, str]] = asyncio.Queue(maxsize=256)
        self.qsize_high_water = 0
        self.writer_task: Optional[asyncio.Task] = None
        # False only during join, until the snapshot is queued ahead of fan-out.
        self.accepts_fanout = True


def room_key_for_code(code: str) -> str:
    """Map invite code to in-process connection bucket key."""
    return fanout_room_key(normalize_collab_code(code))


def register_connection(code: str, user_id: int, handle: MindmateCollabWsHandle) -> Optional[MindmateCollabWsHandle]:
    """
    Track a local WebSocket handle for fan-out delivery.

    Returns the previous handle for the same user in this room, if any.
    """
    key = room_key_for_code(code)
    bucket = ACTIVE_CONNECTIONS.setdefault(key, {})
    previous = bucket.get(int(user_id))
    bucket[int(user_id)] = handle
    return previous if previous is not handle else None


def unregister_connection(
    code: str,
    user_id: int,
    *,
    handle: MindmateCollabWsHandle | None = None,
) -> None:
    """Remove a local WebSocket handle when the client disconnects."""
    key = room_key_for_code(code)
    bucket = ACTIVE_CONNECTIONS.get(key)
    if not bucket:
        return
    uid = int(user_id)
    if handle is not None and bucket.get(uid) is not handle:
        return
    bucket.pop(uid, None)
    if not bucket:
        ACTIVE_CONNECTIONS.pop(key, None)


def teardown_superseded_connection(
    code: str,
    user_id: int,
    superseded: MindmateCollabWsHandle,
) -> None:
    """
    Remove a superseded handle from ACTIVE_CONNECTIONS if still registered.

    Call when the same user opens a new tab so the prior socket's disconnect
    cleanup does not evict the active connection.
    """
    key = room_key_for_code(code)
    bucket = ACTIVE_CONNECTIONS.get(key)
    if bucket is not None and bucket.get(int(user_id)) is superseded:
        bucket.pop(int(user_id), None)
        if not bucket:
            ACTIVE_CONNECTIONS.pop(key, None)


def local_participant_count(code: str) -> int:
    """Count in-process sockets for a room (dev/single-node diagnostics)."""
    key = room_key_for_code(code)
    return len(ACTIVE_CONNECTIONS.get(key, {}))


def frame_must_be_delivered(data_str: str) -> bool:
    """True when dropping this outbound frame would hide a chat line."""
    try:
        payload = json.loads(data_str)
    except json.JSONDecodeError:
        return False
    if not isinstance(payload, dict):
        return False
    return payload.get("type") in _RETAINED_FRAME_TYPES


def _is_stream_chunk(item: tuple[str, str]) -> bool:
    if item[0] != "text":
        return False
    try:
        payload = json.loads(item[1])
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("type") == "ai_message_chunk"


def _drop_one_stream_chunk(handle: MindmateCollabWsHandle) -> bool:
    """Free one queue slot by discarding an AI stream chunk. Returns False if none exist."""
    kept: list[tuple[str, str]] = []
    dropped = False
    while True:
        try:
            item = handle.send_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
        if not dropped and _is_stream_chunk(item):
            dropped = True
            continue
        kept.append(item)
    for item in kept:
        try:
            handle.send_queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("[MindmateCollabWS] outbound queue overflow while compacting")
            break
    return dropped


def enqueue_text(handle: MindmateCollabWsHandle, data_str: str, *, critical: bool) -> bool:
    """
    Queue one outbound frame.

    A full queue drops an AI chunk to keep chat lines. Returns False when a
    critical frame still cannot be queued.
    """
    item = ("text", data_str)
    try:
        handle.send_queue.put_nowait(item)
    except asyncio.QueueFull:
        if not critical or not _drop_one_stream_chunk(handle):
            logger.warning(
                "[MindmateCollabWS] outbound queue full critical=%s",
                critical,
            )
            return False
        try:
            handle.send_queue.put_nowait(item)
        except asyncio.QueueFull:
            logger.warning("[MindmateCollabWS] outbound queue full after compacting")
            return False
    handle.qsize_high_water = max(handle.qsize_high_water, handle.send_queue.qsize())
    return True


def enqueue_json(handle: MindmateCollabWsHandle, message: Dict[str, Any]) -> bool:
    """Serialize and queue one server frame. Retained frame types are not dropped for chunks."""
    data_str = json.dumps(message, ensure_ascii=False)
    critical = message.get("type") in _RETAINED_FRAME_TYPES
    return enqueue_text(handle, data_str, critical=critical)


def enqueue_transcript_resync() -> None:
    """Ask sockets already in a seminar to pull lines missed while fan-out was down."""
    frame = {"type": "resync"}
    for bucket in list(ACTIVE_CONNECTIONS.values()):
        for handle in list(bucket.values()):
            if not handle.accepts_fanout:
                continue
            if enqueue_json(handle, frame):
                continue
            schedule_close_slow_consumer(handle)


_SLOW_CONSUMER_CLOSES: set[asyncio.Task[None]] = set()


def schedule_close_slow_consumer(handle: MindmateCollabWsHandle) -> None:
    """Close a socket that cannot accept another chat frame so the client reloads history."""
    task = asyncio.create_task(
        _close_handle(
            handle,
            DELIVERY_FAILURE_CLOSE_CODE,
            "outbound queue full",
        ),
        name="mindmate-collab-slow-consumer",
    )
    _SLOW_CONSUMER_CLOSES.add(task)
    task.add_done_callback(_SLOW_CONSUMER_CLOSES.discard)


async def shutdown_connection_handle(handle: MindmateCollabWsHandle) -> None:
    """Stop outbound writer task for a handle (disconnect cleanup)."""
    await _stop_writer(handle)


async def _stop_writer(handle: MindmateCollabWsHandle) -> None:
    try:
        handle.send_queue.put_nowait(("stop", ""))
    except asyncio.QueueFull:
        pass
    if handle.writer_task is not None:
        handle.writer_task.cancel()
        handle.writer_task = None


async def _close_handle(handle: MindmateCollabWsHandle, close_code: int, close_reason: str) -> None:
    await _stop_writer(handle)
    try:
        if handle.websocket.client_state == WebSocketState.CONNECTED:
            await handle.websocket.close(code=close_code, reason=close_reason)
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.debug("[MindmateCollabWS] close failed: %s", exc)


async def close_superseded_connection(previous: MindmateCollabWsHandle) -> None:
    """Close a duplicate tab socket (canvas collab parity: 4003)."""
    await _close_handle(previous, 4003, "replaced_by_new_session")


async def force_disconnect_local_room(code: str, *, close_code: int, close_reason: str) -> None:
    """Close every local socket in the room with the given WebSocket close code."""
    key = room_key_for_code(code)
    bucket = ACTIVE_CONNECTIONS.get(key)
    if not bucket:
        return
    snapshot = list(bucket.items())
    for user_id, handle in snapshot:
        await _close_handle(handle, close_code, close_reason)
        logger.debug(
            "[MindmateCollabWS] force disconnect user=%s code=%s close=%s",
            user_id,
            normalize_collab_code(code),
            close_code,
        )
    ACTIVE_CONNECTIONS.pop(key, None)
