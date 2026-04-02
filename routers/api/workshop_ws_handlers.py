"""Message handlers for canvas collaboration WebSocket (reduces router complexity)."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.workshop_ws_connection_state import (
    ACTIVE_EDITORS as active_editors,
)
from services.infrastructure.monitoring.ws_metrics import record_ws_rate_limit_hit
from services.workshop.canvas_collab_locks import (
    filter_granular_connections_for_locks,
    filter_granular_nodes_for_locks,
)
from services.redis.redis_client import get_redis
from services.workshop.workshop_live_flush import schedule_live_spec_db_flush
from services.workshop.workshop_live_spec_ops import mutate_live_spec_after_ws_update
from services.workshop.workshop_redis_ttl import get_workshop_redis_ttl_seconds
from services.workshop.workshop_service import workshop_service
from services.workshop.workshop_ws_editor_redis import load_editors, save_editors

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

from routers.api.workshop_ws_broadcast import broadcast_to_all, broadcast_to_others
from utils.ws_limits import (
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
)

logger = logging.getLogger(__name__)


async def build_participants_with_names(participant_ids: List[int]) -> List[Dict[str, Any]]:
    """Build ``{user_id, username}`` entries for a list of participant ids."""
    out: List[Dict[str, Any]] = []
    for pid in participant_ids:
        if redis_user_cache:
            participant_user = await redis_user_cache.get_by_id(pid)
            if participant_user:
                p_username = (
                    getattr(
                        participant_user,
                        "username",
                        None,
                    )
                    or f"User {pid}"
                )
                out.append({"user_id": pid, "username": p_username})
            else:
                out.append({"user_id": pid, "username": f"User {pid}"})
        else:
            out.append({"user_id": pid, "username": f"User {pid}"})
    return out


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


async def _handle_ping(ctx: CollabWsContext, _message: Dict[str, Any]) -> None:
    await ctx.websocket.send_json({"type": "pong"})


async def _handle_join_repeat(ctx: CollabWsContext, _message: Dict[str, Any]) -> None:
    participant_ids = await workshop_service.get_participants(ctx.code)
    current_username = getattr(ctx.user, "username", None) or f"User {ctx.user.id}"
    names = await build_participants_with_names(participant_ids)
    join_repeat: Dict[str, Any] = {
        "type": "joined",
        "user_id": ctx.user.id,
        "username": current_username,
        "diagram_id": ctx.diagram_id,
        "participants": participant_ids,
        "participants_with_names": names,
    }
    if ctx.owner_id is not None:
        join_repeat["owner_id"] = ctx.owner_id
    await ctx.websocket.send_json(join_repeat)


async def _handle_node_editing(ctx: CollabWsContext, message: Dict[str, Any]) -> None:
    node_id = message.get("node_id")
    editing = message.get("editing", False)
    username = getattr(ctx.user, "username", None) or f"User {ctx.user.id}"
    if not node_id or not isinstance(node_id, str) or len(node_id) > 200:
        await ctx.websocket.send_json(
            {
                "type": "error",
                "message": "Invalid node_id",
            }
        )
        return
    if not node_id:
        await ctx.websocket.send_json(
            {
                "type": "error",
                "message": "Missing node_id in node_editing",
            }
        )
        return

    if ctx.code not in active_editors:
        active_editors[ctx.code] = {}
    if node_id not in active_editors[ctx.code]:
        active_editors[ctx.code][node_id] = {}

    if editing:
        active_editors[ctx.code][node_id][ctx.user.id] = username
        color = ctx.user_colors[ctx.user.id % len(ctx.user_colors)]
        emoji = ctx.user_emojis[ctx.user.id % len(ctx.user_emojis)]
    else:
        active_editors[ctx.code][node_id].pop(ctx.user.id, None)
        if not active_editors[ctx.code][node_id]:
            del active_editors[ctx.code][node_id]
        color = None
        emoji = None

    if is_ws_fanout_enabled():
        save_editors(ctx.code, active_editors[ctx.code])

    await broadcast_to_all(
        ctx.code,
        {
            "type": "node_editing",
            "node_id": node_id,
            "user_id": ctx.user.id,
            "username": username,
            "editing": editing,
            "color": color,
            "emoji": emoji,
        },
    )


async def _handle_node_selected(ctx: CollabWsContext, message: Dict[str, Any]) -> None:
    node_sel = message.get("node_id")
    selected = bool(message.get("selected", True))
    sel_username = getattr(ctx.user, "username", None) or f"User {ctx.user.id}"
    if not node_sel or not isinstance(node_sel, str) or len(node_sel) > 200:
        await ctx.websocket.send_json(
            {
                "type": "error",
                "message": "Invalid node_id",
            }
        )
        return
    sel_color = ctx.user_colors[ctx.user.id % len(ctx.user_colors)]
    await broadcast_to_others(
        ctx.code,
        ctx.user.id,
        {
            "type": "node_selected",
            "node_id": node_sel,
            "selected": selected,
            "user_id": ctx.user.id,
            "username": sel_username,
            "color": sel_color,
        },
    )


def _diagram_update_validation_error(
    diagram_id: str,
    message: Dict[str, Any],
) -> Optional[str]:
    """Return an error message string if the update is invalid, else None."""
    errors: List[str] = []
    if message.get("diagram_id") != diagram_id:
        errors.append("Diagram ID mismatch")
    spec = message.get("spec")
    nodes = message.get("nodes")
    connections = message.get("connections")
    if not spec and not nodes and not connections:
        errors.append("Missing spec, nodes, or connections in update")
    if nodes is not None:
        if not isinstance(nodes, list):
            errors.append("Invalid nodes format (must be array)")
        elif len(nodes) > 100:
            errors.append("Too many nodes in update (max 100)")
    if connections is not None:
        if not isinstance(connections, list):
            errors.append("Invalid connections format (must be array)")
        elif len(connections) > 200:
            errors.append("Too many connections in update (max 200)")
    return errors[0] if errors else None


async def _handle_update(ctx: CollabWsContext, message: Dict[str, Any]) -> None:
    verr = _diagram_update_validation_error(ctx.diagram_id, message)
    if verr:
        await ctx.websocket.send_json({"type": "error", "message": verr})
        return

    spec = message.get("spec")
    nodes = message.get("nodes")
    connections = message.get("connections")

    await workshop_service.refresh_participant_ttl(ctx.code, ctx.user.id)
    await workshop_service.refresh_mutation_idle_for_update(
        ctx.code,
        ctx.user.id,
    )

    redis = get_redis()
    if redis:
        try:
            ttl_sec = await get_workshop_redis_ttl_seconds(ctx.diagram_id)
            await mutate_live_spec_after_ws_update(
                redis,
                ctx.code,
                ctx.diagram_id,
                ttl_sec,
                spec,
                nodes,
                connections,
            )
            await schedule_live_spec_db_flush(ctx.code, ctx.diagram_id)
        except Exception as exc:
            logger.warning(
                "[LiveSpec] merge or flush schedule failed: %s",
                exc,
                exc_info=True,
            )

    update_message: Dict[str, Any] = {
        "type": "update",
        "diagram_id": ctx.diagram_id,
        "user_id": ctx.user.id,
        "timestamp": message.get("timestamp") or datetime.now(UTC).isoformat(),
    }

    if nodes is not None or connections is not None:
        editors_redis = load_editors(ctx.code) if is_ws_fanout_enabled() else None
        has_payload = False
        if nodes is not None:
            filtered_nodes = filter_granular_nodes_for_locks(
                ctx.code,
                ctx.user.id,
                nodes,
                active_editors,
                editors_redis,
            )
            if filtered_nodes:
                update_message["nodes"] = filtered_nodes
                has_payload = True
        if connections is not None:
            filtered_connections = filter_granular_connections_for_locks(
                ctx.code,
                ctx.user.id,
                connections,
                active_editors,
                editors_redis,
            )
            if filtered_connections:
                update_message["connections"] = filtered_connections
                has_payload = True
        if not has_payload:
            return
    else:
        update_message["spec"] = spec

    await broadcast_to_others(ctx.code, ctx.user.id, update_message)

    logger.debug(
        "[CanvasCollabWS] User %s updated diagram %s in workshop %s (granular: %s)",
        ctx.user.id,
        ctx.diagram_id,
        ctx.code,
        nodes is not None or connections is not None,
    )


_MSG_HANDLERS = {
    "ping": _handle_ping,
    "join": _handle_join_repeat,
    "node_editing": _handle_node_editing,
    "node_selected": _handle_node_selected,
    "update": _handle_update,
}


async def run_canvas_collab_receive_loop(ctx: CollabWsContext) -> None:
    """Main receive loop until disconnect or error."""
    while True:
        data = await ctx.websocket.receive_text()
        if inbound_text_exceeds_limit(data, DEFAULT_MAX_WS_TEXT_BYTES):
            await ctx.websocket.send_json(
                {
                    "type": "error",
                    "message": "Message too large",
                }
            )
            continue
        if not ctx.rate_limiter.allow():
            try:
                record_ws_rate_limit_hit()
            except Exception as exc:
                logger.debug("Failed to record rate limit metric: %s", exc)
            await ctx.websocket.send_json(
                {
                    "type": "error",
                    "message": "Rate limit exceeded",
                }
            )
            continue

        try:
            message = json.loads(data)
        except json.JSONDecodeError:
            await ctx.websocket.send_json(
                {
                    "type": "error",
                    "message": "Invalid JSON",
                }
            )
            continue

        msg_type = message.get("type")
        handler = _MSG_HANDLERS.get(msg_type)
        if handler:
            await handler(ctx, message)
            continue

        await ctx.websocket.send_json(
            {
                "type": "error",
                "message": f"Unknown message type: {msg_type}",
            }
        )
