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
        self._extra_presence_orgs: Dict[int, Set[int]] = {}

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

    async def disconnect(self, user_id: int) -> list[int]:
        """Remove a notify socket and return every presence org it covered."""
        self._connections.pop(user_id, None)
        primary = self._presence_org_by_user.pop(user_id, None)
        extras = self._extra_presence_orgs.pop(user_id, set())
        org_ids: list[int] = []
        if primary is not None:
            org_ids.append(primary)
        for org_id in sorted(extras):
            if org_id not in org_ids:
                org_ids.append(org_id)
        return org_ids

    async def set_presence_org(self, user_id: int, org_id: int) -> None:
        """Scope org-wide presence for this notify connection."""
        await self.set_presence_orgs(user_id, [org_id])

    def _presence_org_ids(self, user_id: int) -> Set[int]:
        """Schools this notify socket currently marks the user online in."""
        org_ids: Set[int] = set()
        primary = self._presence_org_by_user.get(user_id)
        if primary is not None:
            org_ids.add(primary)
        org_ids.update(self._extra_presence_orgs.get(user_id, set()))
        return org_ids

    def _covers_org(self, user_id: int, org_id: int) -> bool:
        """True when this user's notify socket is watching that school."""
        return org_id in self._presence_org_ids(user_id)

    async def set_presence_orgs(self, user_id: int, org_ids: list[int]) -> None:
        """Mark the user online in each bound school and drop schools they left."""
        if not org_ids:
            return
        previous = self._presence_org_ids(user_id)
        primary = int(org_ids[0])
        extras = {int(org_id) for org_id in org_ids[1:]}
        self._presence_org_by_user[user_id] = primary
        self._extra_presence_orgs[user_id] = extras
        desired = {primary, *extras}
        for org_id in org_ids:
            await workshop_chat_presence_store.touch_presence_org_user(int(org_id), user_id)
        for org_id in previous - desired:
            await workshop_chat_presence_store.remove_presence_org_user(org_id, user_id)
            await self.broadcast_org_presence(user_id, "offline", org_id, exclude_user=user_id)

    async def replace_presence_orgs(self, user_id: int, org_ids: list[int]) -> None:
        """Move a connected user onto exactly these schools."""
        if user_id not in self._connections:
            return
        previous = self._presence_org_ids(user_id)
        desired = [int(org_id) for org_id in org_ids if int(org_id) > 0]
        if not desired:
            self._presence_org_by_user.pop(user_id, None)
            self._extra_presence_orgs.pop(user_id, None)
            for org_id in previous:
                await workshop_chat_presence_store.remove_presence_org_user(org_id, user_id)
                await self.broadcast_org_presence(user_id, "offline", org_id, exclude_user=user_id)
            return
        await self.set_presence_orgs(user_id, desired)
        for org_id in set(desired) - previous:
            await self.broadcast_org_presence(user_id, "active", org_id, exclude_user=user_id)

    def get_presence_org_id(self, user_id: int) -> Optional[int]:
        """Return org id subscribed for presence, if any."""
        return self._presence_org_by_user.get(user_id)

    async def touch_presence(self, user_id: int) -> None:
        """Refresh Redis presence TTL for the user's org scope."""
        org_ids = set(self._extra_presence_orgs.get(user_id, set()))
        primary = self._presence_org_by_user.get(user_id)
        if primary is not None:
            org_ids.add(primary)
        for org_id in org_ids:
            await workshop_chat_presence_store.touch_presence_org_user(org_id, user_id)

    async def presence_org_online_ids(self, org_id: int) -> Set[int]:
        """Online user ids in org (Redis + local notify sockets)."""
        online = await workshop_chat_presence_store.online_user_ids_for_org(org_id)
        for uid, scoped_org in self._presence_org_by_user.items():
            if scoped_org == org_id and uid in self._connections:
                online.add(uid)
        for uid, extras in self._extra_presence_orgs.items():
            if org_id in extras and uid in self._connections:
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
        for uid in list(self._connections):
            if not self._covers_org(uid, org_id):
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
