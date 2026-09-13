"""Watch WebSocket for 校本培训 HUD snapshots (event push, no poll).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.features.training.payloads import snapshot_from_session
from services.features.training.permissions import can_lead_any_training
from services.features.training.session_store import get_instructor_pointer, get_session
from services.features.training.wake_fanout import training_snapshot_frame
from services.features.training.ws_manager import training_remote_ws_manager
from utils.auth_ws import authenticate_websocket_user
from utils.collab_ws_origin import close_ws_if_origin_disallowed
from utils.ws_context import ws_managed_session
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)

router = APIRouter()

_PONG = json.dumps({"type": "pong"})


async def _hosted_snapshot_frame(user_id: int) -> str:
    """Same hydrate as GET /training/sessions/active without org_id."""
    pointer = await get_instructor_pointer(user_id)
    if pointer is None:
        return training_snapshot_frame(snapshot_from_session(None))
    try:
        org_id = int(pointer.get("org_id") or 0)
    except (TypeError, ValueError):
        org_id = 0
    if org_id <= 0:
        return training_snapshot_frame(snapshot_from_session(None))
    session = await get_session(org_id)
    return training_snapshot_frame(snapshot_from_session(session, viewer_user_id=user_id))


@router.websocket("/ws/training-remote")
async def training_remote_websocket(websocket: WebSocket) -> None:
    """Hold a watch socket; Redis pub/sub delivers training_snapshot frames."""
    if await close_ws_if_origin_disallowed(websocket, "TrainingRemote"):
        return

    user, auth_err = await authenticate_websocket_user(websocket)
    if auth_err or not user:
        try:
            await websocket.close(code=1008, reason=auth_err or "Unauthorized")
        except (RuntimeError, OSError):
            pass
        return
    if not can_lead_any_training(user):
        try:
            await websocket.close(code=1008, reason="Training lead access required")
        except (RuntimeError, OSError):
            pass
        return

    await websocket.accept()
    user_id = int(user.id)
    training_remote_ws_manager.connect(user_id, websocket)
    await websocket.send_text(await _hosted_snapshot_frame(user_id))
    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)

    async with ws_managed_session(websocket, user_id=user_id, endpoint="training-remote"):
        try:
            while True:
                raw = await websocket.receive_text()
                if inbound_text_exceeds_limit(raw, DEFAULT_MAX_WS_TEXT_BYTES):
                    continue
                if not rate_limiter.allow():
                    continue
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if str(data.get("type", "")) == "ping":
                    await websocket.send_text(_PONG)
        except WebSocketDisconnect:
            logger.debug("[TrainingRemote] ws disconnected user=%s", user_id)
        finally:
            training_remote_ws_manager.disconnect(user_id, websocket)
