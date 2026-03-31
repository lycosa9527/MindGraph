"""Post-accept join handshake (participants, editors, user_joined)."""

import asyncio
import logging
from typing import Any, Dict, List

from fastapi import WebSocket

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.workshop_ws_connection_state import (
    ACTIVE_EDITORS as active_editors,
)
from services.redis.redis_client import get_redis
from services.workshop.workshop_live_spec import spec_for_snapshot
from services.workshop.workshop_live_spec_ops import ensure_live_spec_seeded
from services.workshop.workshop_redis_ttl import get_workshop_redis_ttl_seconds
from services.workshop.workshop_service import workshop_service
from services.workshop.workshop_ws_editor_redis import load_editors

from routers.api.workshop_ws_broadcast import broadcast_to_others
from routers.api.workshop_ws_handlers import build_participants_with_names

logger = logging.getLogger(__name__)


async def _send_live_spec_snapshot(
    websocket: WebSocket,
    code: str,
    diagram_id: str,
) -> None:
    """Push authoritative diagram JSON after ``joined`` (Phase 2)."""
    redis = get_redis()
    if not redis:
        return
    try:
        ttl_sec = await asyncio.to_thread(
            get_workshop_redis_ttl_seconds,
            diagram_id,
        )
        doc = await asyncio.to_thread(
            ensure_live_spec_seeded,
            redis,
            code,
            diagram_id,
            ttl_sec,
        )
        snap = spec_for_snapshot(doc) if doc else {}
        ver = int(doc.get("v", 1)) if doc else 1
        await websocket.send_json(
            {
                "type": "snapshot",
                "diagram_id": diagram_id,
                "spec": snap,
                "version": ver,
            }
        )
    except Exception as exc:
        logger.debug("Failed to send snapshot to client: %s", exc)


async def _replay_remote_node_editing_states(
    websocket: WebSocket,
    user: object,
    editor_map: Dict[str, Dict[int, str]],
    user_colors: List[str],
    user_emojis: List[str],
) -> None:
    """Send node_editing snapshots for peers already editing when this user joins."""
    for node_id, editors in editor_map.items():
        for editor_user_id, editor_username in editors.items():
            if editor_user_id != user.id:
                color = user_colors[editor_user_id % len(user_colors)]
                emoji = user_emojis[editor_user_id % len(user_emojis)]
                await websocket.send_json(
                    {
                        "type": "node_editing",
                        "node_id": node_id,
                        "user_id": editor_user_id,
                        "username": editor_username,
                        "editing": True,
                        "color": color,
                        "emoji": emoji,
                    }
                )


async def send_canvas_collab_join_handshake(
    websocket: WebSocket,
    code: str,
    user: object,
    diagram_id: str,
    owner_id: Any,
    user_colors: List[str],
    user_emojis: List[str],
) -> None:
    """Send joined payload, replay remote editors, broadcast user_joined."""
    participant_ids = await workshop_service.get_participants(code)
    username = getattr(user, "username", None) or f"User {user.id}"
    participants_with_names = build_participants_with_names(participant_ids)

    joined_payload: Dict[str, Any] = {
        "type": "joined",
        "user_id": user.id,
        "username": username,
        "diagram_id": diagram_id,
        "participants": participant_ids,
        "participants_with_names": participants_with_names,
    }
    if owner_id is not None:
        joined_payload["owner_id"] = owner_id
    await websocket.send_json(joined_payload)

    await _send_live_spec_snapshot(websocket, code, diagram_id)

    editor_map = load_editors(code) if is_ws_fanout_enabled() else active_editors.get(code, {})
    await _replay_remote_node_editing_states(
        websocket,
        user,
        editor_map,
        user_colors,
        user_emojis,
    )

    await broadcast_to_others(
        code,
        user.id,
        {
            "type": "user_joined",
            "user_id": user.id,
            "username": username,
        },
    )
