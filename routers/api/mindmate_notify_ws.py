"""
MindMate notify WebSocket — org presence and collab poke (no workshop chat gate).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from models.domain.auth import User
from routers.features.workshop_chat.dependencies import get_effective_org_id
from services.features.mindmate_notify_ws_manager import mindmate_notify_ws_manager
from utils.auth import user_has_feature_access
from utils.auth.school_tier import TIER_FEATURE_ONLINE_COLLAB, user_has_school_tier_feature
from utils.auth_ws import authenticate_websocket_user
from utils.collab_ws_origin import close_ws_if_origin_disallowed
from utils.db.session_open import actor_rls_session
from utils.ws_context import ws_managed_session
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _tier_allowed(user: User) -> bool:
    async with actor_rls_session(user) as db:
        return await user_has_school_tier_feature(db, user, TIER_FEATURE_ONLINE_COLLAB)


@router.websocket("/ws/mindmate-notify")
async def mindmate_notify_websocket(websocket: WebSocket) -> None:
    """Lightweight notify socket for MindMate org presence and collab poke toasts."""
    if await close_ws_if_origin_disallowed(websocket, "MindmateNotify"):
        return

    user, auth_err = await authenticate_websocket_user(websocket)
    if auth_err or not user:
        try:
            await websocket.close(code=1008, reason=auth_err or "Unauthorized")
        except (RuntimeError, OSError):
            pass
        return

    if not await user_has_feature_access(user, "feature_mindmate_collab"):
        try:
            await websocket.close(code=1008, reason="Feature disabled")
        except (RuntimeError, OSError):
            pass
        return

    if not await _tier_allowed(user):
        try:
            await websocket.close(code=1008, reason="Feature unavailable")
        except (RuntimeError, OSError):
            pass
        return

    await websocket.accept()
    user_id = int(user.id)
    await mindmate_notify_ws_manager.connect(user_id, websocket)

    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)

    async with ws_managed_session(websocket, user_id=user_id, endpoint="mindmate-notify"):
        try:
            while True:
                raw = await websocket.receive_text()
                if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": "Message too large"}),
                    )
                    continue
                if not rate_limiter.allow():
                    await websocket.send_text(
                        json.dumps({"type": "error", "message": "Rate limit exceeded"}),
                    )
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))
                    continue
                msg_type = str(data.get("type", ""))
                if msg_type == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                    continue
                if msg_type == "subscribe_presence":
                    await _handle_subscribe_presence(websocket, user, data)
                    continue
                if msg_type == "presence":
                    await _handle_presence(user_id, data)
                    continue
        except WebSocketDisconnect:
            logger.debug("[MindmateNotifyWS] user %s disconnected", user_id)
        finally:
            org_id = await mindmate_notify_ws_manager.disconnect(user_id)
            if org_id is not None:
                await mindmate_notify_ws_manager.broadcast_org_presence(
                    user_id,
                    "offline",
                    org_id,
                    exclude_user=user_id,
                )


async def _handle_subscribe_presence(websocket: WebSocket, user: User, data: dict) -> None:
    raw = data.get("org_id")
    requested = int(raw) if raw is not None else None
    try:
        effective = get_effective_org_id(user, requested)
    except HTTPException:
        logger.warning("[MindmateNotifyWS] subscribe_presence rejected for user %s", user.id)
        return
    user_id = int(user.id)
    await mindmate_notify_ws_manager.set_presence_org(user_id, effective)
    online_here = await mindmate_notify_ws_manager.presence_org_online_ids(effective)
    others = [uid for uid in online_here if uid != user_id]
    await websocket.send_text(
        json.dumps(
            {
                "type": "presence_snapshot",
                "user_ids": others,
            },
        ),
    )
    await mindmate_notify_ws_manager.broadcast_org_presence(
        user_id,
        "active",
        effective,
        exclude_user=user_id,
    )


async def _handle_presence(user_id: int, data: dict) -> None:
    status = str(data.get("status", "active"))
    org_id = mindmate_notify_ws_manager.get_presence_org_id(user_id)
    if org_id is None:
        return
    if status == "offline":
        await mindmate_notify_ws_manager.broadcast_org_presence(
            user_id,
            "offline",
            org_id,
            exclude_user=user_id,
        )
        return
    await mindmate_notify_ws_manager.touch_presence(user_id)
    await mindmate_notify_ws_manager.broadcast_org_presence(
        user_id,
        status,
        org_id,
        exclude_user=user_id,
    )
