"""
Workshop WebSocket Router
=========================

WebSocket endpoint for real-time collaborative diagram editing.

Features:
- Real-time diagram updates broadcast to all participants
- User presence (join/leave via Redis participant sets)
- Server-authoritative Redis live diagram spec with optimistic merge (PATCH ``v``)
- Duplicate tab handling: superseded sockets close with 4003 ``replaced_by_new_session``
- Per-connection writer Task (sole owner of ws.send_*); bounded asyncio.Queue
  with backpressure / slow-consumer eviction (Phase 0 pattern)

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
    ACTIVE_EDITORS as active_editors,
    AnyHandle,
    activate_connection,
    create_connection_handle,
    enqueue,
    finalize_handle_writer_shutdown,
    teardown_superseded_connection,
)
from utils.collab_ws_origin import (
    canvas_collab_websocket_origin_is_allowed,
    load_collab_ws_allowed_origins_env,
)
from utils.ws_context import ws_managed_session
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)
from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo

_close_ws_if_vpn_cn_geo = maybe_close_websocket_for_vpn_cn_geo
from routers.api.workshop_ws_auth import (
    authenticate_canvas_collab_user,
    normalize_canvas_collab_code,
    resolve_canvas_collab_join,
)
from routers.api.workshop_ws_connect import send_canvas_collab_join_handshake
from routers.api.workshop_ws_disconnect import (
    clear_editor_state_for_superseded_session,
    finalize_canvas_collab_disconnect,
)
from routers.api.workshop_ws_handlers import (
    CollabWsContext,
    run_canvas_collab_receive_loop,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_collab_origin_reject,
    record_ws_editor_connection_delta,
    record_ws_viewer_connection_delta,
)
from services.online_collab.common.collab_palette import USER_COLORS, USER_EMOJIS
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    WebsocketMessageRateLimiter,
)

logger = logging.getLogger(__name__)

_COLLAB_WS_GENERIC_ERROR = (
    "Collaboration session encountered an error. Please reconnect if the problem persists."
)

router = APIRouter()


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


_COLLAB_WS_MAX_PER_USER_ENDPOINT = _parse_positive_int_env(
    "COLLAB_WS_MAX_PER_USER_ENDPOINT", 5
)
_COLLAB_WS_MAX_PER_USER_GLOBAL = _parse_positive_int_env(
    "COLLAB_WS_MAX_PER_USER_GLOBAL", 20
)


def _collaboration_disabled_by_env() -> bool:
    raw = os.environ.get("COLLAB_DISABLED", "0")
    return raw.lower() in ("1", "true", "yes")


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
      - {"type": "resync", "diagram_id": "..."}  # authoritative snapshot replay
      - {"type": "update", "diagram_id": "...", "spec": {...}, "timestamp": "..."}
      - {"type": "node_editing", "node_id": "...", "editing": true/false}
      - {"type": "node_selected", "node_id": "...", "selected": true/false}
      - {"type": "ping"}

    - Server -> Client:
      - {"type": "joined", "user_id": 123, "owner_id": 123, "participants": [...]}
      - {"type": "snapshot", "diagram_id": "...", "spec": {...}, "version": n}
      - {"type": "update", ...}
      - {"type": "node_editing", ...}
      - {"type": "node_editing_batch_ws", "events": [...]}  # Phase 0 batch frame
      - {"type": "node_selected", ...}
      - {"type": "user_joined", ...}
      - {"type": "user_left", ...}
      - {"type": "error", "message": "..."}
      - {"type": "pong"}

    Args:
        websocket: WebSocket connection
        code: Workshop code
    """
    if _collaboration_disabled_by_env():
        try:
            await websocket.close(
                code=1013,
                reason="Collaboration temporarily disabled",
            )
        except Exception as exc:
            logger.debug("[WorkshopWS] Close on collab-disabled: %s", exc)
        return

    user, auth_err = await authenticate_canvas_collab_user(websocket)
    if auth_err or user is None:
        return

    norm_code = normalize_canvas_collab_code(code)
    if norm_code is None:
        await websocket.close(
            code=1008,
            reason="Invalid presentation code format",
        )
        logger.warning(
            "[WorkshopWS] Invalid presentation code format: %s",
            code.strip().upper(),
        )
        return

    allowed_origins = load_collab_ws_allowed_origins_env()
    if not canvas_collab_websocket_origin_is_allowed(
            websocket.headers, allowed_origins,
    ):
        try:
            record_ws_collab_origin_reject()
        except Exception as exc:
            logger.debug("[WorkshopWS] origin metric skipped: %s", exc)
        logger.warning("[WorkshopWS] Origin rejected for user_id=%s", user.id)
        await websocket.close(
            code=1008,
            reason="Cross-origin collaboration is not allowed",
        )
        return

    if await _close_ws_if_vpn_cn_geo(websocket):
        logger.warning("[WorkshopWS] VPN/CN policy closed connection for user_id=%s", user.id)
        return

    # Accept the upgrade now so that any subsequent rejection (e.g. session
    # invalid / rate-limited) is delivered as a proper WebSocket close frame
    # (code 1008) instead of an HTTP 403.  Without this, Starlette closes the
    # unaccepted socket via HTTP 403, the browser sees code 1006 (abnormal
    # closure), and the frontend reconnect loop fires even for terminal
    # "session ended" states.
    await websocket.accept()

    resolved = await resolve_canvas_collab_join(websocket, user, norm_code)
    if not resolved:
        return
    user, code, diagram_id, owner_id = resolved

    rate_limiter = WebsocketMessageRateLimiter(
        DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    )

    active_editors.setdefault(code, {})

    role = "host" if (owner_id is not None and user.id == owner_id) else "editor"
    handle = create_connection_handle(code, user.id, websocket, role=role)

    logger.info(
        "[WorkshopWS] User %s connected to workshop %s (diagram %s)",
        user.id, code, diagram_id,
    )

    collab_ctx = CollabWsContext(
        code=code,
        diagram_id=diagram_id,
        owner_id=owner_id,
        user=user,
        rate_limiter=rate_limiter,
        websocket=websocket,
        user_colors=USER_COLORS,
        user_emojis=USER_EMOJIS,
        handle=handle,
        jwt_last_revalidated_monotonic=time.monotonic(),
    )

    join_committed = False
    try:

        await get_online_collab_manager().on_join(code, user.id)

        async with ws_managed_session(
            websocket,
            user_id=user.id,
            endpoint="collab",
            code=code,
            diagram_id=diagram_id,
            max_per_user_endpoint=_COLLAB_WS_MAX_PER_USER_ENDPOINT,
            max_per_user_global=_COLLAB_WS_MAX_PER_USER_GLOBAL,
            redis_collab_cap=True,
        ):
            room = active_connections.get(code, {})
            previous_handle: AnyHandle | None = room.get(user.id)
            if previous_handle is not None and previous_handle.websocket is not websocket:
                try:
                    await previous_handle.websocket.close(
                        code=4003, reason="replaced_by_new_session"
                    )
                except Exception as exc:
                    logger.debug("[WorkshopWS] Close superseded socket failed: %s", exc)
                await teardown_superseded_connection(code, user.id, previous_handle)
                await clear_editor_state_for_superseded_session(code, user)

            try:
                await send_canvas_collab_join_handshake(
                    handle,
                    code,
                    user,
                    diagram_id,
                    owner_id,
                    USER_COLORS,
                    USER_EMOJIS,
                )
            except Exception as hs_exc:
                logger.error(
                    "[WorkshopWS] Handshake failed user=%s code=%s: %s",
                    user.id, code, hs_exc,
                )
                try:
                    await websocket.close(code=4011, reason="handshake_failed")
                except Exception:
                    pass
                raise

            await activate_connection(code, user.id, handle)
            if handle.role == "viewer":
                record_ws_viewer_connection_delta(1)
            else:
                record_ws_editor_connection_delta(1)
            join_committed = True

            try:
                await run_canvas_collab_receive_loop(collab_ctx)

            except WebSocketDisconnect:
                logger.info(
                    "[WorkshopWS] User %s disconnected from workshop %s",
                    user.id, code,
                )
            except Exception as exc:
                logger.error(
                    "[WorkshopWS] Error in workshop WebSocket: %s",
                    exc,
                    exc_info=True,
                )
                try:
                    await enqueue(
                        handle,
                        {"type": "error", "message": _COLLAB_WS_GENERIC_ERROR},
                        "error",
                    )
                except Exception as send_exc:
                    logger.debug("Failed to send WebSocket error message: %s", send_exc)
            finally:
                if handle.role == "viewer":
                    record_ws_viewer_connection_delta(-1)
                else:
                    record_ws_editor_connection_delta(-1)
                await get_online_collab_manager().on_leave(code, user.id)
                await finalize_canvas_collab_disconnect(
                    code=code,
                    user=user,
                    handle=handle,
                    workshop_owner_id=owner_id,
                )
    except BaseException:
        if not join_committed:
            try:
                await get_online_collab_manager().remove_participant(code, user.id)
            except Exception as cleanup_exc:
                logger.warning(
                    "[WorkshopWS] remove_participant after failed join user=%s code=%s: %s",
                    user.id, code, cleanup_exc,
                )
        raise
    finally:
        # Ensure the writer task is stopped even when ws_managed_session raised
        # on entry (cap hit) or the handshake failed before activate_connection.
        # finalize_handle_writer_shutdown is idempotent: safe to call twice.
        await finalize_handle_writer_shutdown(handle)
