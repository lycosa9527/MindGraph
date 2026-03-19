"""
Workshop Chat WebSocket Router
================================

WebSocket endpoint at /api/ws/chat for real-time messaging.
Handles authentication, message routing, typing indicators, and presence.

Protocol mirrors the plan's WebSocket specification.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config.database import SessionLocal
from models.domain.auth import User as UserModel
from services.features.workshop_chat import (
    channel_service, message_service, dm_service,
)
from services.features.workshop_chat_ws_manager import chat_ws_manager
from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
from services.redis.session.redis_session_manager import (
    get_session_manager as redis_get_session_manager,
)
from utils.auth import decode_access_token, is_admin

logger = logging.getLogger(__name__)

router = APIRouter()


async def _authenticate_ws(websocket: WebSocket):
    """
    Authenticate a WebSocket connection from token query param or cookie.

    Returns (user, error_reason). On failure user is None.
    """
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.cookies.get("access_token")
    if not token:
        return None, "No authentication token"

    try:
        payload = decode_access_token(token)
    except Exception:
        return None, "Invalid token"

    user_id_str = payload.get("sub")
    if not user_id_str:
        return None, "Invalid token payload"

    user_id = int(user_id_str)

    session_mgr = redis_get_session_manager()
    if session_mgr and not session_mgr.is_session_valid(user_id, token):
        return None, "Session expired"

    user = redis_user_cache.get_by_id(user_id)
    if not user:
        return None, "User not found"
    return user, None


@router.websocket("/api/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for workshop chat real-time messaging.

    Client messages:
        subscribe_channels, channel_message, topic_message, dm,
        typing_channel, typing_topic, typing_dm,
        read_channel, read_topic, ping

    Server messages:
        channel_message, topic_message, dm,
        typing_channel, typing_topic, typing_dm,
        presence, topic_updated,
        unread_channel, unread_topic, unread_dm, pong
    """
    user, error = await _authenticate_ws(websocket)
    if not user:
        await websocket.close(code=4001, reason=error or "Auth failed")
        logger.warning("[ChatWS] Auth rejected: %s", error)
        return

    if not is_admin(user):
        await websocket.close(code=4003, reason="Admin only")
        logger.warning("[ChatWS] Non-admin user %d rejected", user.id)
        return

    await websocket.accept()
    chat_ws_manager.connect(
        websocket, user.id, user.name or f"User {user.id}", user.avatar,
    )

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON"})
                )
                continue
            await _handle_message(websocket, user, data)
    except WebSocketDisconnect:
        logger.info("[ChatWS] User %d disconnected", user.id)
    except Exception:
        logger.exception("[ChatWS] Error in WS loop for user %d", user.id)
    finally:
        old_channels = chat_ws_manager.disconnect(user.id)
        await chat_ws_manager.broadcast_presence(
            user.id, "offline", channel_ids=old_channels,
        )


async def _handle_message(websocket: WebSocket, user, data: dict):
    """Route an incoming WebSocket message to the appropriate handler."""
    msg_type = data.get("type", "")
    handler = _MESSAGE_HANDLERS.get(msg_type)
    if handler:
        await handler(websocket, user, data)
    else:
        await websocket.send_text(
            json.dumps({"type": "error", "message": f"Unknown type: {msg_type}"})
        )


async def _handle_subscribe_channels(
    _websocket: WebSocket, user, data: dict,
):
    """Subscribe to channel broadcasts (only channels user is a member of).

    After subscribing, broadcasts an active presence event so other users
    in those channels see this user as online.
    """
    channel_ids = data.get("channel_ids", [])
    if not channel_ids:
        return
    db = SessionLocal()
    try:
        valid_ids = [
            cid for cid in channel_ids
            if channel_service.is_channel_member(db, cid, user.id)
        ]
    finally:
        db.close()
    chat_ws_manager.subscribe_channels(user.id, valid_ids)
    await chat_ws_manager.broadcast_presence(user.id, "active")


async def _handle_subscribe_dm(
    _websocket: WebSocket, user, data: dict,
):
    """Subscribe to DM broadcasts from specific partners."""
    partner_ids = data.get("partner_ids", [])
    chat_ws_manager.subscribe_dm(user.id, partner_ids)


async def _handle_channel_message(
    _websocket: WebSocket, user, data: dict,
):
    """Handle a channel message sent via WebSocket."""
    channel_id = data.get("channel_id")
    content = data.get("content", "")
    if not channel_id or not content:
        return

    db = SessionLocal()
    try:
        if not channel_service.is_channel_member(db, channel_id, user.id):
            return
        result = message_service.send_message(
            db, channel_id, user.id, content,
        )
        await chat_ws_manager.send_to_user(user.id, {
            "type": "channel_message", "channel_id": channel_id,
            "message": result,
        })
        await chat_ws_manager.broadcast_to_channel(channel_id, {
            "type": "channel_message", "channel_id": channel_id,
            "message": result,
        }, exclude_user=user.id)
    finally:
        db.close()


async def _handle_topic_message(
    _websocket: WebSocket, user, data: dict,
):
    """Handle a topic message sent via WebSocket."""
    channel_id = data.get("channel_id")
    topic_id = data.get("topic_id")
    content = data.get("content", "")
    if not channel_id or not topic_id or not content:
        return

    db = SessionLocal()
    try:
        if not channel_service.is_channel_member(db, channel_id, user.id):
            return
        result = message_service.send_message(
            db, channel_id, user.id, content, topic_id=topic_id,
        )
        await chat_ws_manager.send_to_user(user.id, {
            "type": "topic_message", "channel_id": channel_id,
            "topic_id": topic_id, "message": result,
        })
        await chat_ws_manager.broadcast_to_channel(channel_id, {
            "type": "topic_message", "channel_id": channel_id,
            "topic_id": topic_id, "message": result,
        }, exclude_user=user.id)
    finally:
        db.close()


async def _handle_dm(
    websocket: WebSocket, user, data: dict,
):
    """Handle a DM sent via WebSocket (same org only)."""
    recipient_id = data.get("recipient_id")
    content = data.get("content", "")
    if not recipient_id or not content:
        return

    db = SessionLocal()
    try:
        recipient = db.query(UserModel).filter(
            UserModel.id == recipient_id,
        ).first()
        if not recipient:
            await websocket.send_text(json.dumps({
                "type": "error", "message": "User not found",
            }))
            return
        sender = db.query(UserModel).filter(
            UserModel.id == user.id,
        ).first()
        if (
            not sender
            or not sender.organization_id
            or sender.organization_id != recipient.organization_id
        ):
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "Cannot message users outside your organization",
            }))
            return
        result = dm_service.send(db, user.id, recipient_id, content)
        await chat_ws_manager.send_to_user(user.id, {
            "type": "dm", "message": result,
        })
        await chat_ws_manager.send_to_user(recipient_id, {
            "type": "dm", "message": result,
        })
    finally:
        db.close()


async def _handle_typing_channel(
    _websocket: WebSocket, user, data: dict,
):
    """Broadcast typing in a channel (only if subscribed)."""
    channel_id = data.get("channel_id")
    if not channel_id:
        return
    conn = chat_ws_manager._connections.get(user.id)
    if not conn or channel_id not in conn.subscribed_channels:
        return
    await chat_ws_manager.broadcast_typing_channel(
        channel_id, user.id, user.name or f"User {user.id}",
    )


async def _handle_typing_topic(
    _websocket: WebSocket, user, data: dict,
):
    """Broadcast typing in a topic (only if subscribed)."""
    channel_id = data.get("channel_id")
    topic_id = data.get("topic_id")
    if not channel_id or not topic_id:
        return
    conn = chat_ws_manager._connections.get(user.id)
    if not conn or channel_id not in conn.subscribed_channels:
        return
    await chat_ws_manager.broadcast_typing_channel(
        channel_id, user.id, user.name or f"User {user.id}",
        topic_id=topic_id,
    )


async def _handle_typing_dm(
    _websocket: WebSocket, user, data: dict,
):
    """Broadcast typing in a DM (same org only)."""
    recipient_id = data.get("recipient_id")
    if not recipient_id:
        return
    db = SessionLocal()
    try:
        recipient = db.query(UserModel).filter(
            UserModel.id == recipient_id,
        ).first()
        sender = db.query(UserModel).filter(
            UserModel.id == user.id,
        ).first()
        if (
            not recipient
            or not sender
            or sender.organization_id != recipient.organization_id
        ):
            return
    finally:
        db.close()
    await chat_ws_manager.broadcast_typing_dm(
        user.id, recipient_id, user.name or f"User {user.id}",
    )


async def _handle_read_channel(
    _websocket: WebSocket, user, data: dict,
):
    """Update last-read position for a channel."""
    channel_id = data.get("channel_id")
    msg_id = data.get("message_id")
    if channel_id and msg_id:
        db = SessionLocal()
        try:
            message_service.update_last_read(db, channel_id, user.id, msg_id)
        finally:
            db.close()


async def _handle_presence(
    _websocket: WebSocket, user, data: dict,
):
    """Rebroadcast a client-driven presence update (active / idle)."""
    presence_status = data.get("status")
    if presence_status not in ("active", "idle"):
        return
    await chat_ws_manager.broadcast_presence(user.id, presence_status)


async def _handle_ping(websocket: WebSocket, _user, _data: dict):
    """Respond to ping."""
    await websocket.send_text(json.dumps({"type": "pong"}))


_MESSAGE_HANDLERS = {
    "subscribe_channels": _handle_subscribe_channels,
    "subscribe_dm": _handle_subscribe_dm,
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
