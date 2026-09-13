"""In-process sockets for 校本培训 watch HUD snapshots.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Dict, Set

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


class TrainingRemoteWsManager:
    """Track training-remote sockets. Several tabs per user are allowed."""

    def __init__(self) -> None:
        """Create an empty per-user socket map."""
        self._sockets: Dict[int, Set[WebSocket]] = {}

    def connect(self, user_id: int, websocket: WebSocket) -> None:
        """Register a socket for ``user_id``."""
        sockets = self._sockets.get(user_id)
        if sockets is None:
            sockets = set()
            self._sockets[user_id] = sockets
        sockets.add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """Forget a socket (idempotent)."""
        sockets = self._sockets.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            self._sockets.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: str) -> int:
        """Push ``payload`` to every local socket for ``user_id``. Returns sends."""
        return await self._send_many(list(self._sockets.get(user_id) or ()), payload, user_id)

    async def send_to_all(self, payload: str) -> int:
        """Push ``payload`` to every local training-remote socket."""
        sockets: list[WebSocket] = []
        for group in self._sockets.values():
            sockets.extend(group)
        return await self._send_many(sockets, payload, 0)

    async def _send_many(
        self,
        sockets: list[WebSocket],
        payload: str,
        user_id: int,
    ) -> int:
        delivered = 0
        seen: set[int] = set()
        for websocket in sockets:
            marker = id(websocket)
            if marker in seen:
                continue
            seen.add(marker)
            if await self._safe_send(websocket, payload, user_id):
                delivered += 1
        return delivered

    async def _safe_send(self, websocket: WebSocket, payload: str, user_id: int) -> bool:
        try:
            if websocket.client_state != WebSocketState.CONNECTED:
                return False
            await websocket.send_text(payload)
            return True
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("[TrainingRemote] ws send failed user=%s: %s", user_id, exc)
            return False


training_remote_ws_manager = TrainingRemoteWsManager()
