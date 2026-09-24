"""
In-process sockets for one shared diagram.

Redis fan-out delivers the same payload to sockets on other workers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

_rooms: dict[str, dict[str, WebSocket]] = {}


def attach_share_socket(diagram_id: str, tab_id: str, websocket: WebSocket) -> None:
    """Remember a socket that should receive spec snapshots."""
    room = _rooms.setdefault(diagram_id, {})
    room[tab_id] = websocket


def detach_share_socket(diagram_id: str, tab_id: str, websocket: WebSocket) -> None:
    """Forget a socket if it is still the one registered for this tab."""
    room = _rooms.get(diagram_id)
    if not room:
        return
    if room.get(tab_id) is websocket:
        room.pop(tab_id, None)
    if not room:
        _rooms.pop(diagram_id, None)


async def relay_share_spec(diagram_id: str, from_tab: str, payload: str) -> None:
    """Send one spec snapshot to every other local socket in the room."""
    room = list(_rooms.get(diagram_id, {}).items())
    for tab_id, socket in room:
        if tab_id == from_tab:
            continue
        try:
            await socket.send_text(payload)
        except (WebSocketDisconnect, RuntimeError, OSError) as exc:
            logger.debug("[DiagramShareWS] drop viewer tab=%s: %s", tab_id, exc)
            detach_share_socket(diagram_id, tab_id, socket)
