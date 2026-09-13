"""In-process sockets for 演讲模式 command wakes and HUD snapshots.

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


class SlidesRemoteWsManager:
    """Track desktop and watch sockets. Several tabs per user are allowed."""

    def __init__(self) -> None:
        """Create empty per-user socket maps."""
        self._desktop: Dict[int, Set[WebSocket]] = {}
        self._watch: Dict[int, Set[WebSocket]] = {}

    def connect(self, user_id: int, websocket: WebSocket, *, watch: bool = False) -> None:
        """Register a socket for ``user_id``."""
        bucket = self._watch if watch else self._desktop
        sockets = bucket.get(user_id)
        if sockets is None:
            sockets = set()
            bucket[user_id] = sockets
        sockets.add(websocket)

    def disconnect(self, user_id: int, websocket: WebSocket) -> None:
        """Forget a socket (idempotent)."""
        self._drop(self._desktop, user_id, websocket)
        self._drop(self._watch, user_id, websocket)

    def desktop_count(self, user_id: int) -> int:
        """Desktop sockets for ``user_id`` on this worker."""
        sockets = self._desktop.get(user_id)
        return 0 if sockets is None else len(sockets)

    def _drop(
        self,
        bucket: Dict[int, Set[WebSocket]],
        user_id: int,
        websocket: WebSocket,
    ) -> None:
        sockets = bucket.get(user_id)
        if sockets is None:
            return
        sockets.discard(websocket)
        if not sockets:
            bucket.pop(user_id, None)

    async def send_to_user(self, user_id: int, payload: str) -> int:
        """Push ``payload`` to every local socket for ``user_id``. Returns sends."""
        sockets = list(self._desktop.get(user_id) or ())
        sockets.extend(self._watch.get(user_id) or ())
        delivered = 0
        for websocket in sockets:
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
            logger.debug("[SlideRemote] ws send failed user=%s: %s", user_id, exc)
            return False


slides_remote_ws_manager = SlidesRemoteWsManager()
