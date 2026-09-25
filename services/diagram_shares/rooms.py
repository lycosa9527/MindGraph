"""
In-process sockets for one shared diagram.

Redis fan-out delivers the same payload to sockets on other workers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_CLOSE_ERRORS = (WebSocketDisconnect, RuntimeError, OSError)


@dataclass
class _ShareSocket:
    """One canvas tab subscribed to a shared diagram."""

    user_id: int
    websocket: WebSocket


_rooms: dict[str, dict[str, _ShareSocket]] = {}


def attach_share_socket(diagram_id: str, tab_id: str, user_id: int, websocket: WebSocket) -> WebSocket | None:
    """Remember a socket. Returns the previous socket for this tab when it was replaced."""
    room = _rooms.setdefault(diagram_id, {})
    previous = room.get(tab_id)
    room[tab_id] = _ShareSocket(user_id=user_id, websocket=websocket)
    if previous is not None and previous.websocket is not websocket:
        return previous.websocket
    return None


def detach_share_socket(diagram_id: str, tab_id: str, websocket: WebSocket) -> None:
    """Forget a socket if it is still the one registered for this tab."""
    room = _rooms.get(diagram_id)
    if not room:
        return
    current = room.get(tab_id)
    if current is not None and current.websocket is websocket:
        room.pop(tab_id, None)
    if not room:
        _rooms.pop(diagram_id, None)


async def _close_socket(websocket: WebSocket, code: int, reason: str) -> None:
    try:
        await websocket.close(code=code, reason=reason)
    except _CLOSE_ERRORS as exc:
        logger.debug("[DiagramShareWS] close failed: %s", exc)


async def close_share_sockets_for_user(diagram_id: str, user_id: int) -> None:
    """Drop every local socket for a user who lost this diagram."""
    room = _rooms.get(diagram_id)
    if not room:
        return
    stale = [(tab_id, entry.websocket) for tab_id, entry in room.items() if entry.user_id == user_id]
    for tab_id, websocket in stale:
        current = room.get(tab_id)
        if current is not None and current.websocket is websocket:
            room.pop(tab_id, None)
        await _close_socket(websocket, 4003, "Share ended")
    if not room:
        _rooms.pop(diagram_id, None)


async def close_share_room(diagram_id: str) -> None:
    """Drop every local socket when the diagram or its queue is gone."""
    room = _rooms.pop(diagram_id, None)
    if not room:
        return
    for entry in room.values():
        await _close_socket(entry.websocket, 4003, "Share ended")


async def relay_share_spec(diagram_id: str, from_tab: str, payload: str) -> None:
    """Send one spec snapshot to every other local socket in the room."""
    room = list(_rooms.get(diagram_id, {}).items())
    for tab_id, entry in room:
        if tab_id == from_tab:
            continue
        try:
            await entry.websocket.send_text(payload)
        except _CLOSE_ERRORS as exc:
            logger.debug("[DiagramShareWS] drop viewer tab=%s: %s", tab_id, exc)
            detach_share_socket(diagram_id, tab_id, entry.websocket)
