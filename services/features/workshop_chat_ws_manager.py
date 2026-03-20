"""
Workshop Chat WebSocket Manager
================================

Connection registry, channel/DM subscriptions, and real-time broadcast
for the workshop chat system.

Each connected user has one WebSocket. The manager tracks which channels
and DM partners the client is subscribed to, and routes messages accordingly.

For multi-worker scaling, Redis Pub/Sub can be layered on top.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket
from fastapi.websockets import WebSocketState


def _dumps(obj: Any) -> str:
    """Serialize a dict to a JSON string."""
    return json.dumps(obj, ensure_ascii=False)

logger = logging.getLogger(__name__)

TYPING_EXPIRE_SECONDS = 5


class _UserConnection:
    """Tracks a single user's WebSocket state."""

    __slots__ = (
        "websocket", "user_id", "username", "avatar",
        "subscribed_channels", "subscribed_dm_partners",
        "presence_org_id",
    )

    def __init__(
        self, websocket: WebSocket, user_id: int,
        username: str, avatar: Optional[str],
    ):
        self.websocket = websocket
        self.user_id = user_id
        self.username = username
        self.avatar = avatar
        self.subscribed_channels: Set[int] = set()
        self.subscribed_dm_partners: Set[int] = set()
        self.presence_org_id: Optional[int] = None


class ChatConnectionManager:
    """Manages WebSocket connections for workshop chat."""

    def __init__(self):
        self._connections: Dict[int, _UserConnection] = {}
        self._channel_subscribers: Dict[int, Set[int]] = {}
        self._typing_state: Dict[str, float] = {}

    @property
    def online_user_ids(self) -> Set[int]:
        """Set of currently connected user IDs."""
        return set(self._connections.keys())

    def connect(
        self, websocket: WebSocket, user_id: int,
        username: str, avatar: Optional[str] = None,
    ) -> None:
        """Register a new WebSocket connection."""
        old = self._connections.get(user_id)
        if old:
            self._remove_subscriptions(user_id)

        self._connections[user_id] = _UserConnection(
            websocket, user_id, username, avatar,
        )
        logger.info("[ChatWS] User %d (%s) connected", user_id, username)

    def disconnect(self, user_id: int) -> tuple[Set[int], Optional[int]]:
        """Remove a connection and all its subscriptions.

        Returns subscribed channel IDs and presence org (for offline broadcast).
        """
        conn = self._connections.get(user_id)
        subscribed = conn.subscribed_channels.copy() if conn else set()
        presence_org = conn.presence_org_id if conn else None
        self._remove_subscriptions(user_id)
        self._connections.pop(user_id, None)
        logger.info("[ChatWS] User %d disconnected", user_id)
        return subscribed, presence_org

    def set_presence_org(self, user_id: int, org_id: int) -> None:
        """Scope workshop presence (contacts sidebar) to this organization."""
        conn = self._connections.get(user_id)
        if conn:
            conn.presence_org_id = org_id

    def get_presence_org_id(self, user_id: int) -> Optional[int]:
        """Organization ID used for org-wide presence, if subscribed."""
        conn = self._connections.get(user_id)
        return conn.presence_org_id if conn else None

    def online_user_ids_for_presence_org(self, org_id: int) -> Set[int]:
        """User IDs with an active WS and the same presence org scope."""
        return {
            uid for uid, conn in self._connections.items()
            if conn.presence_org_id == org_id
        }

    async def broadcast_presence_to_presence_org(
        self, user_id: int, status: str, org_id: int,
        exclude_user: Optional[int] = None,
    ) -> None:
        """Notify everyone in the same presence org (workshop contacts list)."""
        payload = _dumps({
            "type": "presence", "user_id": user_id, "status": status,
        })
        tasks = []
        for uid, conn in self._connections.items():
            if exclude_user is not None and uid == exclude_user:
                continue
            if conn.presence_org_id != org_id:
                continue
            tasks.append(self._safe_send(conn.websocket, payload, uid))
        if tasks:
            await asyncio.gather(*tasks)

    def subscribe_channels(self, user_id: int, channel_ids: list) -> None:
        """Subscribe user to a set of channels for broadcast."""
        conn = self._connections.get(user_id)
        if not conn:
            return

        old_channels = conn.subscribed_channels.copy()
        for ch_id in old_channels - set(channel_ids):
            subs = self._channel_subscribers.get(ch_id)
            if subs:
                subs.discard(user_id)
                if not subs:
                    del self._channel_subscribers[ch_id]
            conn.subscribed_channels.discard(ch_id)

        for ch_id in channel_ids:
            conn.subscribed_channels.add(ch_id)
            self._channel_subscribers.setdefault(ch_id, set()).add(user_id)

    def subscribe_dm(self, user_id: int, partner_ids: list) -> None:
        """Subscribe user to receive DMs from specific partners."""
        conn = self._connections.get(user_id)
        if not conn:
            return
        conn.subscribed_dm_partners = set(partner_ids)

    def is_user_subscribed_to_channel(
        self, user_id: int, channel_id: int,
    ) -> bool:
        """Return True if the user is connected and subscribed to the channel."""
        conn = self._connections.get(user_id)
        if not conn:
            return False
        return channel_id in conn.subscribed_channels

    async def broadcast_to_channel(
        self, channel_id: int, payload: Dict[str, Any],
        exclude_user: Optional[int] = None,
    ) -> None:
        """Send a message to all subscribers of a channel."""
        subscriber_ids = self._channel_subscribers.get(channel_id, set()).copy()
        if exclude_user:
            subscriber_ids.discard(exclude_user)

        data = _dumps(payload)
        tasks = []
        for uid in subscriber_ids:
            conn = self._connections.get(uid)
            if conn:
                tasks.append(self._safe_send(conn.websocket, data, uid))
        if tasks:
            await asyncio.gather(*tasks)

    async def send_to_user(
        self, user_id: int, payload: Dict[str, Any],
    ) -> bool:
        """Send a message to a specific user if online."""
        conn = self._connections.get(user_id)
        if not conn:
            return False
        data = _dumps(payload)
        return await self._safe_send(conn.websocket, data, user_id)

    async def broadcast_typing_channel(
        self, channel_id: int, user_id: int,
        username: str, topic_id: Optional[int] = None,
    ) -> None:
        """Broadcast typing indicator for a channel or topic."""
        self.cleanup_typing_state()
        key = f"ch:{channel_id}:t:{topic_id}:u:{user_id}"
        now = time.time()
        if now - self._typing_state.get(key, 0) < 2:
            return
        self._typing_state[key] = now

        msg_type = "typing_topic" if topic_id else "typing_channel"
        payload: Dict[str, Any] = {
            "type": msg_type, "channel_id": channel_id,
            "user_id": user_id, "username": username,
        }
        if topic_id:
            payload["topic_id"] = topic_id
        await self.broadcast_to_channel(
            channel_id, payload, exclude_user=user_id,
        )

    async def broadcast_typing_dm(
        self, sender_id: int, recipient_id: int, username: str,
    ) -> None:
        """Broadcast typing indicator for a DM conversation."""
        self.cleanup_typing_state()
        key = f"dm:{sender_id}:{recipient_id}"
        now = time.time()
        if now - self._typing_state.get(key, 0) < 2:
            return
        self._typing_state[key] = now

        await self.send_to_user(recipient_id, {
            "type": "typing_dm", "sender_id": sender_id, "username": username,
        })

    async def broadcast_presence(
        self, user_id: int, status: str,
        channel_ids: Optional[Set[int]] = None,
    ) -> None:
        """Broadcast presence change to channels the user is in.

        If *channel_ids* is supplied (e.g. from disconnect), those are used
        instead of reading from the live connection (which may already be
        removed).
        """
        if channel_ids is None:
            conn = self._connections.get(user_id)
            channel_ids = conn.subscribed_channels.copy() if conn else set()
        payload = {"type": "presence", "user_id": user_id, "status": status}
        for ch_id in channel_ids:
            await self.broadcast_to_channel(ch_id, payload, exclude_user=user_id)

    def cleanup_typing_state(self) -> None:
        """Remove expired typing indicators."""
        now = time.time()
        expired = [
            k for k, v in self._typing_state.items()
            if now - v > TYPING_EXPIRE_SECONDS
        ]
        for key in expired:
            del self._typing_state[key]

    def _remove_subscriptions(self, user_id: int) -> None:
        """Remove all channel subscriptions for a user."""
        conn = self._connections.get(user_id)
        if not conn:
            return
        for ch_id in conn.subscribed_channels:
            subs = self._channel_subscribers.get(ch_id)
            if subs:
                subs.discard(user_id)
                if not subs:
                    del self._channel_subscribers[ch_id]
        conn.subscribed_channels.clear()
        conn.subscribed_dm_partners.clear()

    @staticmethod
    async def _safe_send(websocket: WebSocket, data: str, user_id: int) -> bool:
        """Send data to a WebSocket, handling connection errors."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(data)
                return True
        except Exception:
            logger.debug("[ChatWS] Failed to send to user %d", user_id)
        return False


chat_ws_manager = ChatConnectionManager()
