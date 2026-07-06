"""
In-process WebSocket registry for MindMate collab rooms.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from services.features.mindmate_collab.redis_keys import fanout_room_key, normalize_collab_code
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)

# room_key -> user_id -> handle
ACTIVE_CONNECTIONS: Dict[str, Dict[int, "MindmateCollabWsHandle"]] = {}


class MindmateCollabWsHandle:
    """Local WebSocket handle with outbound queue and writer task."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.send_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        self.qsize_high_water = 0
        self.writer_task: Optional[asyncio.Task] = None


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
