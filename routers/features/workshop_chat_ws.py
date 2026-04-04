"""
Workshop Chat WebSocket Router
================================

WebSocket endpoint at /api/ws/chat for real-time messaging.
Handles authentication, message routing, typing indicators, and presence.

Per-topic read receipts and unread counts use REST, not this socket.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import config
from config.database import AsyncSessionLocal
from models.domain.auth import User as UserModel
from models.domain.workshop_chat import ChatChannel, ChannelMember
from routers.features.workshop_chat.dependencies import (
    get_effective_org_id,
    require_post_permission,
)
from services.features.workshop_chat import (
    channel_service,
    message_service,
    dm_service,
)
from services.features.workshop_chat.mention_resolution import (
    MentionResolutionError,
)
from services.features.workshop_chat_ws_manager import chat_ws_manager
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_auth_failure,
    record_ws_rate_limit_hit,
)
from utils.auth import can_access_workshop_chat
from utils.auth_ws import authenticate_websocket_user
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Cap channel_ids per subscribe_channels message (abuse bound).
MAX_CHANNEL_IDS_SUBSCRIBE = 512


async def _ws_channel_post_gate(
    websocket: WebSocket,
    db: AsyncSession,
    channel_id: int,
    user,
) -> ChatChannel | None:
    """Load channel, enforce membership (except announce), posting policy; else error."""
    result = await db.execute(
        select(ChatChannel).where(
            ChatChannel.id == channel_id,
            ChatChannel.is_archived.is_(False),
        )
    )
    channel = result.scalar_one_or_none()
    if not channel:
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "message": "Channel not found",
                }
            )
        )
        return None
    if channel.channel_type != "announce":
        member_result = await db.execute(
            select(ChannelMember).where(
                ChannelMember.channel_id == channel_id,
                ChannelMember.user_id == user.id,
            )
        )
        if not member_result.scalar_one_or_none():
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "You must join this channel first",
                    }
                )
            )
            return None
    try:
        require_post_permission(channel, user)
    except HTTPException as exc:
        detail = exc.detail
        msg = detail if isinstance(detail, str) else "Forbidden"
        await websocket.send_text(
            json.dumps(
                {
                    "type": "error",
                    "message": msg,
                }
            )
        )
        return None
    return channel


@router.websocket("/api/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for workshop chat real-time messaging.

    Client messages:
        subscribe_channels, subscribe_presence,
        channel_message, topic_message, dm,
        typing_channel, typing_topic, typing_dm,
        read_channel, presence, ping

    Server messages:
        channel_message, topic_message, dm,
        typing_channel, typing_topic, typing_dm,
        presence, presence_snapshot, topic_updated,
        error, pong

    Auth: JWT from query ``token`` or ``access_token`` cookie (prefer cookie
    for same-origin clients). Per-topic read state: REST only.
    """
    if not config.FEATURE_WORKSHOP_CHAT:
        await websocket.close(code=4403, reason="Workshop Chat feature is disabled")
        return
    user, error = await authenticate_websocket_user(websocket)
    if not user:
        try:
            record_ws_auth_failure()
        except Exception as exc:
            logger.debug("Failed to record auth failure metric: %s", exc)
        await websocket.close(code=4001, reason=error or "Auth failed")
        logger.warning("[ChatWS] Auth rejected: %s", error)
        return

    if not can_access_workshop_chat(user):
        try:
            record_ws_auth_failure()
        except Exception as exc:
            logger.debug("Failed to record access rejection metric: %s", exc)
        await websocket.close(code=4003, reason="Elevated access required")
        logger.warning(
            "[ChatWS] User %d rejected (no workshop chat access)",
            user.id,
        )
        return

    await websocket.accept()
    logger.info(
        "[ChatWS] connection accepted user_id=%s",
        user.id,
    )
    chat_ws_manager.connect(
        websocket,
        user.id,
        user.name or f"User {user.id}",
        user.avatar,
    )
    rate_limiter = WebsocketMessageRateLimiter(
        DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    )

    try:
        while True:
            raw = await websocket.receive_text()
            if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": "Message too large",
                        }
                    )
                )
                continue
            if not rate_limiter.allow():
                try:
                    record_ws_rate_limit_hit()
                except Exception as exc:
                    logger.debug("Failed to record rate limit metric: %s", exc)
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "message": "Rate limit exceeded",
                        }
                    )
                )
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                continue
            await _handle_message(websocket, user, data)
    except WebSocketDisconnect:
        logger.info("[ChatWS] User %d disconnected", user.id)
    except Exception:
        logger.exception("[ChatWS] Error in WS loop for user %d", user.id)
    finally:
        old_channels, presence_org = chat_ws_manager.disconnect(user.id)
        if presence_org is not None:
            await chat_ws_manager.broadcast_presence_to_presence_org(
                user.id,
                "offline",
                presence_org,
                exclude_user=user.id,
            )
        await chat_ws_manager.broadcast_presence(
            user.id,
            "offline",
            channel_ids=old_channels,
        )
        if presence_org is not None:
            async with AsyncSessionLocal() as db_local:
                row = (await db_local.execute(select(UserModel).where(UserModel.id == user.id))).scalar_one_or_none()
                if row:
                    row.workshop_last_seen_at = datetime.now(UTC)
                    await db_local.commit()


async def _handle_message(websocket: WebSocket, user, data: dict):
    """Route an incoming WebSocket message to the appropriate handler."""
    msg_type = data.get("type", "")
    handler = _MESSAGE_HANDLERS.get(msg_type)
    if handler:
        await handler(websocket, user, data)
    else:
        await websocket.send_text(json.dumps({"type": "error", "message": f"Unknown type: {msg_type}"}))


async def _handle_subscribe_channels(
    _websocket: WebSocket,
    user,
    data: dict,
):
    """Subscribe to channel broadcasts (only channels user is a member of)."""
    channel_ids = data.get("channel_ids", [])
    if not isinstance(channel_ids, list):
        return
    channel_ids = channel_ids[:MAX_CHANNEL_IDS_SUBSCRIBE]
    if not channel_ids:
        return
    async with AsyncSessionLocal() as db:
        # Batch membership check: single SELECT instead of one per channel.
        member_ids = await channel_service.get_user_member_channel_ids(db, user.id, channel_ids)
    valid_ids = [cid for cid in channel_ids if cid in member_ids]
    chat_ws_manager.subscribe_channels(user.id, valid_ids)


async def _handle_subscribe_presence(
    websocket: WebSocket,
    user,
    data: dict,
):
    """Scope org-wide presence for the workshop contacts list (sidebar).

    Client sends the same org_id used for REST /org-members and /channels.
    """
    raw = data.get("org_id")
    requested = int(raw) if raw is not None else None
    try:
        effective = get_effective_org_id(user, requested)
    except HTTPException:
        logger.warning(
            "[ChatWS] subscribe_presence rejected for user %s",
            user.id,
        )
        return
    chat_ws_manager.set_presence_org(user.id, effective)
    online_here = chat_ws_manager.online_user_ids_for_presence_org(effective)
    others = [uid for uid in online_here if uid != user.id]
    await websocket.send_text(
        json.dumps(
            {
                "type": "presence_snapshot",
                "user_ids": others,
            }
        )
    )
    await chat_ws_manager.broadcast_presence_to_presence_org(
        user.id,
        "active",
        effective,
        exclude_user=user.id,
    )


async def _handle_channel_message(
    websocket: WebSocket,
    user,
    data: dict,
):
    """Handle a channel message sent via WebSocket."""
    channel_id = data.get("channel_id")
    content = data.get("content", "")
    if not channel_id or not content:
        return

    async with AsyncSessionLocal() as db:
        post_channel = await _ws_channel_post_gate(websocket, db, channel_id, user)
        if post_channel is None:
            return
        try:
            result = await message_service.send_message(
                db,
                channel_id,
                user.id,
                content,
            )
        except MentionResolutionError as exc:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "code": "invalid_mentions",
                        "unknown": exc.unknown_names,
                        "ambiguous": exc.ambiguous_names,
                        "message": "Invalid or ambiguous @mentions in message",
                    }
                )
            )
            return
        await chat_ws_manager.send_to_user(
            user.id,
            {
                "type": "channel_message",
                "channel_id": channel_id,
                "message": result,
            },
        )
        await chat_ws_manager.broadcast_to_channel(
            channel_id,
            {
                "type": "channel_message",
                "channel_id": channel_id,
                "message": result,
            },
            exclude_user=user.id,
        )


async def _handle_topic_message(
    websocket: WebSocket,
    user,
    data: dict,
):
    """Handle a topic message sent via WebSocket."""
    channel_id = data.get("channel_id")
    topic_id = data.get("topic_id")
    content = data.get("content", "")
    if not channel_id or not topic_id or not content:
        return

    async with AsyncSessionLocal() as db:
        post_channel = await _ws_channel_post_gate(websocket, db, channel_id, user)
        if post_channel is None:
            return
        try:
            result = await message_service.send_message(
                db,
                channel_id,
                user.id,
                content,
                topic_id=topic_id,
            )
        except MentionResolutionError as exc:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "code": "invalid_mentions",
                        "unknown": exc.unknown_names,
                        "ambiguous": exc.ambiguous_names,
                        "message": "Invalid or ambiguous @mentions in message",
                    }
                )
            )
            return
        await chat_ws_manager.send_to_user(
            user.id,
            {
                "type": "topic_message",
                "channel_id": channel_id,
                "topic_id": topic_id,
                "message": result,
            },
        )
        await chat_ws_manager.broadcast_to_channel(
            channel_id,
            {
                "type": "topic_message",
                "channel_id": channel_id,
                "topic_id": topic_id,
                "message": result,
            },
            exclude_user=user.id,
        )


async def _handle_dm(
    websocket: WebSocket,
    user,
    data: dict,
):
    """Handle a DM sent via WebSocket (same org only)."""
    recipient_id = data.get("recipient_id")
    content = data.get("content", "")
    if not recipient_id or not content:
        return

    async with AsyncSessionLocal() as db:
        recip_row = await db.execute(select(UserModel).where(UserModel.id == recipient_id))
        recipient = recip_row.scalar_one_or_none()
        if not recipient:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "User not found",
                    }
                )
            )
            return
        sender_row = await db.execute(select(UserModel).where(UserModel.id == user.id))
        sender = sender_row.scalar_one_or_none()
        if not sender or not sender.organization_id or sender.organization_id != recipient.organization_id:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": "Cannot message users outside your organization",
                    }
                )
            )
            return
        try:
            dm_result = await dm_service.send(
                db,
                user.id,
                recipient_id,
                content,
            )
        except MentionResolutionError as exc:
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "code": "invalid_mentions",
                        "unknown": exc.unknown_names,
                        "ambiguous": exc.ambiguous_names,
                        "message": "Invalid or ambiguous @mentions in message",
                    }
                )
            )
            return
        await chat_ws_manager.send_to_user(
            user.id,
            {
                "type": "dm",
                "message": dm_result,
            },
        )
        await chat_ws_manager.send_to_user(
            recipient_id,
            {
                "type": "dm",
                "message": dm_result,
            },
        )


async def _handle_typing_channel(
    _websocket: WebSocket,
    user,
    data: dict,
):
    """Broadcast typing in a channel (only if subscribed)."""
    channel_id = data.get("channel_id")
    if not channel_id:
        return
    if not chat_ws_manager.is_user_subscribed_to_channel(user.id, channel_id):
        return
    await chat_ws_manager.broadcast_typing_channel(
        channel_id,
        user.id,
        user.name or f"User {user.id}",
    )


async def _handle_typing_topic(
    _websocket: WebSocket,
    user,
    data: dict,
):
    """Broadcast typing in a topic (only if subscribed)."""
    channel_id = data.get("channel_id")
    topic_id = data.get("topic_id")
    if not channel_id or not topic_id:
        return
    if not chat_ws_manager.is_user_subscribed_to_channel(user.id, channel_id):
        return
    await chat_ws_manager.broadcast_typing_channel(
        channel_id,
        user.id,
        user.name or f"User {user.id}",
        topic_id=topic_id,
    )


async def _handle_typing_dm(
    _websocket: WebSocket,
    user,
    data: dict,
):
    """Broadcast typing in a DM (same org only)."""
    recipient_id = data.get("recipient_id")
    if not recipient_id:
        return

    async with AsyncSessionLocal() as db:
        recip_row = await db.execute(select(UserModel).where(UserModel.id == recipient_id))
        recipient = recip_row.scalar_one_or_none()
        sender_row = await db.execute(select(UserModel).where(UserModel.id == user.id))
        sender = sender_row.scalar_one_or_none()
        can_send = recipient is not None and sender is not None and sender.organization_id == recipient.organization_id
    if not can_send:
        return
    await chat_ws_manager.broadcast_typing_dm(
        user.id,
        recipient_id,
        user.name or f"User {user.id}",
    )


async def _handle_read_channel(
    _websocket: WebSocket,
    user,
    data: dict,
):
    """Update last-read position for a channel."""
    channel_id = data.get("channel_id")
    msg_id = data.get("message_id")
    if channel_id and msg_id:
        async with AsyncSessionLocal() as db:
            await message_service.update_last_read(
                db,
                channel_id,
                user.id,
                msg_id,
            )


async def _handle_presence(
    _websocket: WebSocket,
    user,
    data: dict,
):
    """Rebroadcast a client-driven presence update (active / idle)."""
    presence_status = data.get("status")
    if presence_status not in ("active", "idle"):
        return
    chat_ws_manager.touch_presence_heartbeat(user.id)
    org_pid = chat_ws_manager.get_presence_org_id(user.id)
    if org_pid is not None:
        await chat_ws_manager.broadcast_presence_to_presence_org(
            user.id,
            presence_status,
            org_pid,
            exclude_user=user.id,
        )
    else:
        await chat_ws_manager.broadcast_presence(user.id, presence_status)


async def _handle_ping(websocket: WebSocket, _user, _data: dict):
    """Respond to ping."""
    await websocket.send_text(json.dumps({"type": "pong"}))


_MESSAGE_HANDLERS = {
    "subscribe_channels": _handle_subscribe_channels,
    "subscribe_presence": _handle_subscribe_presence,
    "channel_message": _handle_channel_message,
    "topic_message": _handle_topic_message,
    "dm": _handle_dm,
    "typing_channel": _handle_typing_channel,
    "typing_topic": _handle_typing_topic,
    "typing_dm": _handle_typing_dm,
    "read_channel": _handle_read_channel,
    "presence": _handle_presence,
    "ping": _handle_ping,
}
