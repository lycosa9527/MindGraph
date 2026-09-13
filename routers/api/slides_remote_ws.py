"""Desktop WebSocket for 演讲模式 command wakes (event push, no poll).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.features.slides_remote.session_store import (
    get_session,
    public_snapshot,
    touch_session,
)
from services.features.slides_remote.wake_fanout import slides_snapshot_frame
from services.features.slides_remote.ws_manager import slides_remote_ws_manager
from services.features.slides_remote.ws_ttl import run_desktop_session_touch
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
_WATCH_CLIENT = "esp32-watch"


def _is_watch_client(websocket: WebSocket) -> bool:
    """1.85C firmware sets ``X-MG-Client: esp32-watch``."""
    label = (websocket.headers.get("X-MG-Client") or "").strip().lower()
    return label == _WATCH_CLIENT


@router.websocket("/ws/slides-remote")
async def slides_remote_websocket(websocket: WebSocket) -> None:
    """Hold a desktop or watch socket; Redis pub/sub delivers event frames."""
    if await close_ws_if_origin_disallowed(websocket, "SlideRemote"):
        return

    user, auth_err = await authenticate_websocket_user(websocket)
    if auth_err or not user:
        try:
            await websocket.close(code=1008, reason=auth_err or "Unauthorized")
        except (RuntimeError, OSError):
            pass
        return

    await websocket.accept()
    user_id = int(user.id)
    watch = _is_watch_client(websocket)
    slides_remote_ws_manager.connect(user_id, websocket, watch=watch)
    await websocket.send_text(
        slides_snapshot_frame(public_snapshot(await get_session(user_id))),
    )
    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND)
    touch_stop: asyncio.Event | None = None
    touch_task: asyncio.Task[None] | None = None
    if not watch:
        touch_stop = asyncio.Event()
        touch_task = asyncio.create_task(
            run_desktop_session_touch(user_id, touch_stop),
            name=f"slides-remote-ttl-{user_id}",
        )

    async with ws_managed_session(websocket, user_id=user_id, endpoint="slides-remote"):
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
                    if not watch:
                        await touch_session(user_id)
                    await websocket.send_text(_PONG)
        except WebSocketDisconnect:
            logger.debug("[SlideRemote] ws disconnected user=%s", user_id)
        finally:
            slides_remote_ws_manager.disconnect(user_id, websocket)
            if touch_stop is not None:
                touch_stop.set()
            if touch_task is not None:
                touch_task.cancel()
                try:
                    await touch_task
                except asyncio.CancelledError:
                    pass
