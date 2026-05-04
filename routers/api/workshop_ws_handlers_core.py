"""Core dispatch and session handlers for canvas collaboration WebSocket."""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS,
    AnyHandle,
    ViewerHandle,
    enqueue,
)
from services.features.workshop_ws_role_change import handle_role_change
from services.redis.redis_async_client import get_async_redis
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_collab_resync,
    record_ws_rate_limit_hit,
    record_ws_resync_rate_limit_check_failure,
)
from services.online_collab.participant.online_collab_snapshots import (
    websocket_send_live_spec_snapshot,
)
from services.online_collab.redis.redis8_features import tdigest_record_latency
from services.online_collab.redis.online_collab_redis_keys import resync_rate_limit_key
from services.online_collab.participant.collab_display_name import (
    workshop_collab_member_display_name,
)
from services.online_collab.core.online_collab_manager import get_online_collab_manager
from services.online_collab.core.online_collab_status import (
    diagram_title_for_active_workshop,
    online_collab_visibility_for_diagram_id,
)
from services.online_collab.participant.workshop_join_resume_tokens import (
    mint_join_resume_token_async,
)
from utils.auth_ws import authenticate_websocket_user
from routers.api.workshop_ws_handlers_presence import (
    build_participants_with_names,
    _handle_claim_node_edit,
    _handle_node_editing,
    _handle_node_editing_batch,
    _handle_node_selected,
)
from routers.api.workshop_ws_handlers_update import handle_update as _handle_update
from utils.ws_limits import (
    MAX_COLLAB_INBOUND_JSON_DEPTH,
    WORKSHOP_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    collab_json_exceeds_depth,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)


def _collab_jwt_revalidate_interval_sec() -> float:
    raw = os.environ.get("COLLAB_WS_JWT_REVALIDATE_SEC", "180")
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return 180.0
    return parsed if parsed > 0 else 0.0

@dataclass
class CollabWsContext:
    """Fixed state for one canvas-collab WebSocket session."""

    code: str
    diagram_id: str
    owner_id: Optional[int]
    user: Any
    rate_limiter: WebsocketMessageRateLimiter
    websocket: WebSocket
    user_colors: List[str]
    user_emojis: List[str]
    handle: Optional[AnyHandle] = None
    jwt_last_revalidated_monotonic: float = 0.0
    authz_last_checked_monotonic: float = 0.0

    @property
    def role(self) -> str:
        """Return the role of this connection ("host", "editor", or "viewer")."""
        if self.handle is not None:
            return self.handle.role
        return "editor"


async def _ctx_send(
    ctx: "CollabWsContext", payload: dict, msg_type: str = "error"
) -> None:
    """Route an outbound frame through handle.enqueue or ws.send_json fallback."""
    if ctx.handle is not None:
        await enqueue(ctx.handle, payload, msg_type)
    else:
        await ctx.websocket.send_json(payload)


def _refresh_ctx_handle(ctx: "CollabWsContext") -> None:
    """Pick up in-place role changes made by the room registry."""
    current = ACTIVE_CONNECTIONS.get(ctx.code, {}).get(int(ctx.user.id))
    if current is not None and current is not ctx.handle:
        ctx.handle = current


async def _handle_ping(ctx: CollabWsContext, _message: Dict[str, Any]) -> None:
    try:
        await get_online_collab_manager().refresh_participant_ttl(
            ctx.code, ctx.user.id,
        )
    except Exception as exc:
        logger.debug("[CanvasCollabWS] ping participant TTL refresh skipped: %s", exc)
    try:
        await get_online_collab_manager().touch_activity(ctx.code)
    except Exception as exc:
        logger.debug("[CanvasCollabWS] ping touch_activity skipped: %s", exc)
    await _ctx_send(ctx, {"type": "pong"}, "pong")


async def _handle_join_repeat(
    ctx: CollabWsContext, message: Dict[str, Any],
) -> None:
    join_diagram_id = message.get("diagram_id")
    if (
        isinstance(join_diagram_id, str)
        and join_diagram_id
        and join_diagram_id != ctx.diagram_id
    ):
        logger.warning(
            "[CanvasCollabWS] join_repeat diagram mismatch user=%s code=%s"
            " got=%s expected=%s",
            ctx.user.id, ctx.code, join_diagram_id, ctx.diagram_id,
        )
        await _ctx_send(ctx, {"type": "error", "message": "Diagram ID mismatch"})
        return

    participant_ids = await get_online_collab_manager().get_participants(ctx.code)
    current_username = workshop_collab_member_display_name(ctx.user)
    names = await build_participants_with_names(participant_ids)

    join_repeat: Dict[str, Any] = {
        "type": "joined",
        "user_id": ctx.user.id,
        "username": current_username,
        "diagram_id": ctx.diagram_id,
        "participants": participant_ids,
        "participants_with_names": names,
        "workshop_visibility": await online_collab_visibility_for_diagram_id(
            ctx.diagram_id, code=ctx.code,
        ),
    }
    diag_title = await diagram_title_for_active_workshop(str(ctx.diagram_id))
    if diag_title:
        join_repeat["diagram_title"] = diag_title
    if ctx.owner_id is not None:
        join_repeat["owner_id"] = ctx.owner_id

    resume_tok = await mint_join_resume_token_async(
        user_id=int(ctx.user.id),
        workshop_code_upper=ctx.code.strip().upper(),
        diagram_id=str(ctx.diagram_id),
    )
    if resume_tok:
        join_repeat["resume_token"] = resume_tok

    await _ctx_send(ctx, join_repeat, "joined")
    logger.debug(
        "[CanvasCollabWS] join_repeat_ok user=%s code=%s participants=%d",
        ctx.user.id, ctx.code, len(participant_ids),
    )


_RESYNC_RATE_LIMIT_PER_MIN = 5
_RESYNC_RATE_LIMIT_TTL_SEC = 60


async def _handle_resync(ctx: CollabWsContext, message: Dict[str, Any]) -> None:
    """Send authoritative live spec snapshot (version-gap recovery path)."""
    diag = message.get("diagram_id")
    if diag != ctx.diagram_id:
        logger.warning(
            "[CanvasCollabWS] resync diagram mismatch user=%s code=%s got=%s expected=%s",
            ctx.user.id, ctx.code, diag, ctx.diagram_id,
        )
        await _ctx_send(ctx, {"type": "error", "message": "Diagram ID mismatch"})
        return
    logger.debug(
        "[CanvasCollabWS] resync_start user=%s code=%s diagram=%s role=%s",
        ctx.user.id, ctx.code, ctx.diagram_id, ctx.role,
    )
    redis_rl = get_async_redis()
    if redis_rl:
        rl_key = resync_rate_limit_key(ctx.code.strip().upper(), int(ctx.user.id))
        try:
            count = await redis_rl.incr(rl_key)
            if count == 1:
                await redis_rl.expire(rl_key, _RESYNC_RATE_LIMIT_TTL_SEC)
            if count > _RESYNC_RATE_LIMIT_PER_MIN:
                logger.info(
                    "[CanvasCollabWS] resync rate limited user=%s code=%s count=%s",
                    ctx.user.id, ctx.code, count,
                )
                await _ctx_send(
                    ctx,
                    {
                        "type": "error",
                        "message": "Too many resync requests — wait a moment.",
                    },
                )
                return
        except Exception as exc:
            logger.warning("[CanvasCollabWS] resync rate limit check failed (allowing): %s", exc)
            try:
                record_ws_resync_rate_limit_check_failure()
            except Exception:  # pylint: disable=broad-except
                pass
    try:
        record_ws_collab_resync()
    except Exception as exc:
        logger.debug("record_ws_collab_resync skipped: %s", exc)
    if isinstance(ctx.handle, ViewerHandle):
        try:
            from services.infrastructure.monitoring.ws_metrics import (
                record_ws_viewer_resync,
            )
            record_ws_viewer_resync()
        except Exception:
            pass
    await websocket_send_live_spec_snapshot(ctx.handle, ctx.code, ctx.diagram_id)
_EDITOR_HANDLERS = {
    "ping": _handle_ping,
    "join": _handle_join_repeat,
    "resync": _handle_resync,
    "node_editing": _handle_node_editing,
    "node_editing_batch": _handle_node_editing_batch,
    "node_selected": _handle_node_selected,
    "claim_node_edit": _handle_claim_node_edit,
    "update": _handle_update,
    "role_change": handle_role_change,
}

_VIEWER_HANDLERS = {
    "ping": _handle_ping,
    "resync": _handle_resync,
}

_MSG_HANDLERS = _EDITOR_HANDLERS


async def run_canvas_collab_receive_loop(ctx: CollabWsContext) -> None:
    """Main receive loop until disconnect or error.

    Dispatches to _EDITOR_HANDLERS for host/editor connections and
    _VIEWER_HANDLERS for viewer connections.  Viewer sends of editor-only
    messages (update, node_editing, etc.) are rejected with close code 4015
    without running any validation or DB/Redis logic.
    """
    while True:
        _refresh_ctx_handle(ctx)
        data = await ctx.websocket.receive_text()
        if inbound_text_exceeds_limit(data, WORKSHOP_MAX_WS_TEXT_BYTES):
            await _ctx_send(ctx, {"type": "error", "message": "Message too large"})
            continue
        if not ctx.rate_limiter.allow():
            try:
                record_ws_rate_limit_hit()
            except Exception as exc:
                logger.debug("Failed to record rate limit metric: %s", exc)
            await _ctx_send(ctx, {"type": "error", "message": "Rate limit exceeded"})
            continue

        now_loop = time.monotonic()
        if now_loop - ctx.authz_last_checked_monotonic >= 5.0:
            ctx.authz_last_checked_monotonic = now_loop
            participants_ok = True
            try:
                participant_ids = await get_online_collab_manager().get_participants(
                    ctx.code,
                )
            except Exception as exc:
                logger.warning(
                    "[CanvasCollabWS] authz participant refresh failed: %s", exc,
                )
                participants_ok = False
                participant_ids = []
            uid_loop = int(getattr(ctx.user, "id", 0))
            # Only revoke when the fetch succeeded — an empty list on Redis error
            # must NOT be treated as "participant not found" or every Redis hiccup
            # would disconnect all active users.
            if participants_ok and participant_ids and uid_loop not in participant_ids:
                await _ctx_send(
                    ctx,
                    {
                        "type": "error",
                        "message": (
                            "You are no longer in this workshop — "
                            "please reconnect."
                        ),
                    },
                )
                await ctx.websocket.close(
                    code=4002,
                    reason="participant membership revoked",
                )
                return

        reval_sec = _collab_jwt_revalidate_interval_sec()
        if reval_sec > 0:
            now_m = time.monotonic()
            if now_m - ctx.jwt_last_revalidated_monotonic >= reval_sec:
                ctx.jwt_last_revalidated_monotonic = now_m
                user_chk, err_chk = await authenticate_websocket_user(ctx.websocket)
                uid_ctx = int(getattr(ctx.user, "id", -1))
                uid_chk = int(getattr(user_chk, "id", -2)) if user_chk else -3
                if err_chk or user_chk is None or uid_chk != uid_ctx:
                    await _ctx_send(
                        ctx,
                        {
                            "type": "error",
                            "message": "Session expired — please reconnect.",
                        },
                    )
                    await ctx.websocket.close(
                        code=4001,
                        reason="Authentication expired",
                    )
                    return

        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await _ctx_send(ctx, {"type": "error", "message": "Invalid JSON"})
            continue

        if not isinstance(message, dict):
            await _ctx_send(
                ctx, {"type": "error", "message": "Message must be a JSON object"}
            )
            continue

        if collab_json_exceeds_depth(message, MAX_COLLAB_INBOUND_JSON_DEPTH):
            await _ctx_send(
                ctx,
                {
                    "type": "error",
                    "message": "JSON nesting depth exceeds server limit",
                },
            )
            continue

        msg_type = message.get("type")
        _refresh_ctx_handle(ctx)
        is_viewer = isinstance(ctx.handle, ViewerHandle)
        handlers = _VIEWER_HANDLERS if is_viewer else _EDITOR_HANDLERS
        handler = handlers.get(msg_type)
        if handler:
            _t0 = time.perf_counter()
            try:
                await handler(ctx, message)
            except Exception as exc:  # pylint: disable=broad-except
                logger.exception(
                    "[CanvasCollabWS] handler %s raised: %s", msg_type, exc
                )
                await _ctx_send(
                    ctx,
                    {
                        "type": "error",
                        "message": "Internal error processing message. Please try again.",
                    },
                )
            asyncio.create_task(
                tdigest_record_latency(
                    f"handler:{msg_type}",
                    (time.perf_counter() - _t0) * 1000.0,
                )
            )
            continue

        if is_viewer and msg_type in _EDITOR_HANDLERS:
            await ctx.websocket.close(
                code=4015,
                reason="viewer: not authorized for this message type",
            )
            return

        await _ctx_send(
            ctx, {"type": "error", "message": f"Unknown message type: {msg_type}"}
        )
