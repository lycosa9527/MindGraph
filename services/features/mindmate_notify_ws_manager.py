"""
Per-user MindMate notify WebSocket connections (presence + poke toasts).

Does not require workshop chat access — used on MindMate pages for org
presence and collab poke delivery.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from fastapi.websockets import WebSocketState

from services.features import workshop_chat_presence_store
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


class MindmateNotifyWsManager:
    """Track one notify socket per user (MindMate sidebar / collab pages)."""

    def __init__(self) -> None:
        self._connections: Dict[int, WebSocket] = {}
        self._presence_org_by_user: Dict[int, int] = {}

    async def connect(self, user_id: int, websocket: WebSocket) -> None:
        """Register or replace the user's notify socket."""
        previous = self._connections.get(user_id)
        self._connections[user_id] = websocket
        if previous is not None and previous is not websocket:
            try:
                if previous.client_state == WebSocketState.CONNECTED:
                    await previous.close(code=4003, reason="replaced_by_new_session")
            except BACKGROUND_INFRA_ERRORS as exc:
                logger.debug("[MindmateNotifyWS] close superseded failed: %s", exc)

    async def disconnect(self, user_id: int) -> Optional[int]:
        """Remove a notify socket; returns org id if presence was scoped."""
        self._connections.pop(user_id, None)
        return self._presence_org_by_user.pop(user_id, None)

    async def set_presence_org(self, user_id: int, org_id: int) -> None:
        """Scope org-wide presence for this notify connection."""
        self._presence_org_by_user[user_id] = org_id
        await workshop_chat_presence_store.touch_presence_org_user(org_id, user_id)

    def get_presence_org_id(self, user_id: int) -> Optional[int]:
        """Return org id subscribed for presence, if any."""
        return self._presence_org_by_user.get(user_id)

    async def touch_presence(self, user_id: int) -> None:
        """Refresh Redis presence TTL for the user's org scope."""
        org_id = self._presence_org_by_user.get(user_id)
        if org_id is None:
            return
        await workshop_chat_presence_store.touch_presence_org_user(org_id, user_id)

    async def presence_org_online_ids(self, org_id: int) -> Set[int]:
        """Online user ids in org (Redis + local notify sockets)."""
        online = await workshop_chat_presence_store.online_user_ids_for_org(org_id)
        for uid, scoped_org in self._presence_org_by_user.items():
            if scoped_org == org_id and uid in self._connections:
                online.add(uid)
        return online

    async def broadcast_org_presence(
        self,
        user_id: int,
        status: str,
        org_id: int,
        *,
        exclude_user: Optional[int] = None,
    ) -> None:
        """Notify org-scoped peers of a presence change."""
        payload = json.dumps(
            {
                "type": "presence",
                "user_id": user_id,
                "status": status,
            },
        )
        for uid, scoped_org in list(self._presence_org_by_user.items()):
            if scoped_org != org_id:
                continue
            if exclude_user is not None and uid == exclude_user:
                continue
            ws = self._connections.get(uid)
            if ws is not None:
                await self._safe_send(ws, payload, uid)

    async def send_to_user(self, user_id: int, payload: Dict[str, Any]) -> bool:
        """Deliver a JSON payload to a connected notify socket."""
        ws = self._connections.get(user_id)
        if ws is None:
            return False
        data = json.dumps(payload)
        return await self._safe_send(ws, data, user_id)

    async def _safe_send(self, websocket: WebSocket, data: str, user_id: int) -> bool:
        try:
            if websocket.client_state != WebSocketState.CONNECTED:
                return False
            await websocket.send_text(data)
            return True
        except BACKGROUND_INFRA_ERRORS as exc:
            logger.debug("[MindmateNotifyWS] send failed user=%s: %s", user_id, exc)
            return False


mindmate_notify_ws_manager = MindmateNotifyWsManager()
