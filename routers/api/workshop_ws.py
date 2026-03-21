"""
Workshop WebSocket Router
=========================

WebSocket endpoint for real-time collaborative diagram editing.

Features:
- Real-time diagram updates broadcast to all participants
- User presence tracking
- Conflict resolution (last-write-wins with timestamps)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
    ACTIVE_EDITORS as active_editors,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_workshop_connection_delta,
    redis_increment_active_total,
)
from services.workshop.workshop_ws_mutation_idle import start_mutation_idle_monitor

from routers.api.workshop_ws_auth import authenticate_and_resolve_canvas_workshop
from routers.api.workshop_ws_connect import send_canvas_collab_join_handshake
from routers.api.workshop_ws_disconnect import finalize_canvas_collab_disconnect
from routers.api.workshop_ws_handlers import (
    CollabWsContext,
    run_canvas_collab_receive_loop,
)
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    WebsocketMessageRateLimiter,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# User colors for visual indicators (consistent per user)
USER_COLORS = [
    "#FF6B6B",  # Red
    "#4ECDC4",  # Teal
    "#45B7D1",  # Blue
    "#FFA07A",  # Light Salmon
    "#98D8C8",  # Mint
    "#F7DC6F",  # Yellow
    "#BB8FCE",  # Purple
    "#85C1E2",  # Sky Blue
]

USER_EMOJIS = ["✏️", "🖊️", "✒️", "🖋️", "📝", "✍️", "🖍️", "🖌️"]


@router.websocket("/ws/canvas-collab/{code}")
async def canvas_collab_websocket(
    websocket: WebSocket,
    code: str,
):
    """
    WebSocket endpoint for real-time canvas collaboration (diagram workshop).

    Messages:
    - Client -> Server:
      - {"type": "join", "diagram_id": "..."}
      - {"type": "update", "diagram_id": "...", "spec": {...}, "timestamp": "..."}
      - {"type": "node_editing", "node_id": "...", "editing": true/false}
      - {"type": "node_selected", "node_id": "...", "selected": true/false}
      - {"type": "ping"}

    - Server -> Client:
      - {"type": "joined", "user_id": 123, "owner_id": 123, "participants": [...]}
      - {"type": "update", ...}
      - {"type": "node_editing", ...}
      - {"type": "node_selected", ...}
      - {"type": "user_joined", ...}
      - {"type": "user_left", ...}
      - {"type": "error", "message": "..."}
      - {"type": "pong"}

    Args:
        websocket: WebSocket connection
        code: Workshop code
    """
    resolved = await authenticate_and_resolve_canvas_workshop(websocket, code)
    if not resolved:
        return
    user, code, diagram_id, owner_id = resolved

    await websocket.accept()

    rate_limiter = WebsocketMessageRateLimiter(
        DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    )

    if code not in active_connections:
        active_connections[code] = {}
    active_connections[code][user.id] = websocket

    if code not in active_editors:
        active_editors[code] = {}

    try:
        record_ws_workshop_connection_delta(1)
        redis_increment_active_total(1)
    except Exception:  # pylint: disable=broad-except
        pass

    logger.info(
        "[WorkshopWS] User %s connected to workshop %s (diagram %s)",
        user.id,
        code,
        diagram_id,
    )

    await send_canvas_collab_join_handshake(
        websocket,
        code,
        user,
        diagram_id,
        owner_id,
        USER_COLORS,
        USER_EMOJIS,
    )

    monitor_task = start_mutation_idle_monitor(websocket, code, user.id)

    collab_ctx = CollabWsContext(
        code=code,
        diagram_id=diagram_id,
        owner_id=owner_id,
        user=user,
        rate_limiter=rate_limiter,
        websocket=websocket,
        user_colors=USER_COLORS,
        user_emojis=USER_EMOJIS,
    )

    try:
        await run_canvas_collab_receive_loop(collab_ctx)

    except WebSocketDisconnect:
        logger.info(
            "[WorkshopWS] User %s disconnected from workshop %s",
            user.id,
            code,
        )
    except Exception as e:
        logger.error(
            "[WorkshopWS] Error in workshop WebSocket: %s",
            e,
            exc_info=True,
        )
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Presentation mode error: {str(e)}",
                })
        except Exception:
            pass
    finally:
        if monitor_task is not None:
            monitor_task.cancel()
        await finalize_canvas_collab_disconnect(code=code, user=user)
