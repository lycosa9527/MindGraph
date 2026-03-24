"""
Workshop Chat WebSocket Manager
================================

Connection registry, channel subscriptions, and real-time broadcast
for the workshop chat system.

Each connected user has one WebSocket. The manager tracks which channels
the client is subscribed to, and routes messages accordingly.

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

from services.features import workshop_chat_presence_store
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.ws_redis_fanout_publish import publish_chat_fanout_async
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_chat_connection_delta,
    redis_increment_active_total,
)


def _dumps(obj: Any) -> str:
    """Serialize a dict to a JSON string."""
    return json.dumps(obj, ensure_ascii=False)

logger = logging.getLogger(__name__)

TYPING_EXPIRE_SECONDS = 5


class _UserConnection:
    """Tracks a single user's WebSocket state."""

    __slots__ = (
        "websocket", "user_id", "username", "avatar",
        "subscribed_channels",
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
        try:
            record_ws_chat_connection_delta(1)
            redis_increment_active_total(1)
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("WebSocket connect metrics update failed: %s", exc)

    def disconnect(self, user_id: int) -> tuple[Set[int], Optional[int]]:
        """Remove a connection and all its subscriptions.

        Returns subscribed channel IDs and presence org (for offline broadcast).
        """
        conn = self._connections.get(user_id)
        subscribed = conn.subscribed_channels.copy() if conn else set()
        presence_org = conn.presence_org_id if conn else None
        if presence_org is not None and is_ws_fanout_enabled():
            try:
                workshop_chat_presence_store.remove_presence_org_user(
                    presence_org, user_id,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Presence org user removal failed: %s", exc)
        self._remove_subscriptions(user_id)
        self._connections.pop(user_id, None)
        logger.info("[ChatWS] User %d disconnected", user_id)
        try:
            record_ws_chat_connection_delta(-1)
            redis_increment_active_total(-1)
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("WebSocket disconnect metrics update failed: %s", exc)
        return subscribed, presence_org

    def set_presence_org(self, user_id: int, org_id: int) -> None:
        """Scope workshop presence (contacts sidebar) to this organization."""
        conn = self._connections.get(user_id)
        if conn:
            conn.presence_org_id = org_id
        if is_ws_fanout_enabled():
            try:
                workshop_chat_presence_store.touch_presence_org_user(
                    org_id, user_id,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Presence org user touch failed: %s", exc)

    def get_presence_org_id(self, user_id: int) -> Optional[int]:
        """Organization ID used for org-wide presence, if subscribed."""
        conn = self._connections.get(user_id)
        return conn.presence_org_id if conn else None

    def touch_presence_heartbeat(self, user_id: int) -> None:
        """Refresh Redis org presence TTL for active/idle heartbeats."""
        if not is_ws_fanout_enabled():
            return
        conn = self._connections.get(user_id)
        if not conn or conn.presence_org_id is None:
            return
        try:
            workshop_chat_presence_store.touch_presence_org_user(
                conn.presence_org_id, user_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.debug("Presence heartbeat refresh failed: %s", exc)

    def online_user_ids_for_presence_org(self, org_id: int) -> Set[int]:
        """User IDs with an active WS and the same presence org scope."""
        if is_ws_fanout_enabled():
            try:
                return workshop_chat_presence_store.online_user_ids_for_org(
                    org_id,
                )
            except Exception as exc:  # pylint: disable=broad-except
                logger.debug("Presence org online users lookup failed: %s", exc)
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
        if is_ws_fanout_enabled():
            await publish_chat_fanout_async({
                "v": 1, "k": "po", "oid": org_id,
                "ex": exclude_user, "d": payload,
            })
            return
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
        data = _dumps(payload)
        if is_ws_fanout_enabled():
            await publish_chat_fanout_async({
                "v": 1, "k": "ch", "cid": channel_id,
                "ex": exclude_user, "d": data,
            })
            return
        subscriber_ids = self._channel_subscribers.get(channel_id, set()).copy()
        if exclude_user:
            subscriber_ids.discard(exclude_user)

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
        data = _dumps(payload)
        if is_ws_fanout_enabled():
            await publish_chat_fanout_async({
                "v": 1, "k": "u", "uid": user_id, "d": data,
            })
            return True
        conn = self._connections.get(user_id)
        if not conn:
            return False
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

    async def deliver_local_channel_broadcast(
        self,
        channel_id: int,
        exclude_user: Optional[int],
        data: str,
    ) -> None:
        """Deliver a channel payload to local subscribers (Redis fan-out path)."""
        subscriber_ids = self._channel_subscribers.get(channel_id, set()).copy()
        if exclude_user is not None:
            subscriber_ids.discard(exclude_user)
        tasks = []
        for uid in subscriber_ids:
            conn = self._connections.get(uid)
            if conn:
                tasks.append(self._safe_send(conn.websocket, data, uid))
        if tasks:
            await asyncio.gather(*tasks)

    async def deliver_local_user_message(self, user_id: int, data: str) -> None:
        """Deliver a user-targeted payload on this worker only."""
        conn = self._connections.get(user_id)
        if conn:
            await self._safe_send(conn.websocket, data, user_id)

    async def deliver_local_presence_org(
        self,
        org_id: int,
        exclude_user: Optional[int],
        data: str,
    ) -> None:
        """Deliver presence org payload to local connections scoped to org."""
        tasks = []
        for uid, conn in self._connections.items():
            if exclude_user is not None and uid == exclude_user:
                continue
            if conn.presence_org_id != org_id:
                continue
            tasks.append(self._safe_send(conn.websocket, data, uid))
        if tasks:
            await asyncio.gather(*tasks)


chat_ws_manager = ChatConnectionManager()
