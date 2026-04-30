"""Disconnect / cleanup path for canvas collaboration WebSocket."""

import logging

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
    ACTIVE_EDITORS as active_editors,
)
from services.workshop.workshop_service import workshop_service
from services.workshop.workshop_ws_editor_redis import (
    load_editors,
    remove_user_from_all_nodes,
)

from routers.api.workshop_ws_broadcast import broadcast_to_others

logger = logging.getLogger(__name__)


async def _finalize_editors_fanout_disconnect(code: str, user: object) -> None:
    """Clear editor state when multi-worker Redis fan-out is enabled."""
    um_leave = getattr(user, "username", None) or f"User {user.id}"
    editors_map = await load_editors(code)
    nodes_with_user = [nid for nid, ed in editors_map.items() if user.id in ed]
    await remove_user_from_all_nodes(code, user.id, editors_map)
    for nid in nodes_with_user:
        await broadcast_to_others(
            code,
            user.id,
            {
                "type": "node_editing",
                "node_id": nid,
                "user_id": user.id,
                "username": um_leave,
                "editing": False,
                "color": None,
                "emoji": None,
            },
        )
    if code not in active_editors:
        return
    for nid in list(active_editors[code].keys()):
        ed = active_editors[code].get(nid)
        if ed and user.id in ed:
            ed.pop(user.id, None)
            if not ed:
                del active_editors[code][nid]
    if not active_editors[code]:
        del active_editors[code]


async def _finalize_editors_local_disconnect(code: str, user: object) -> None:
    """Clear editor state for in-memory single-worker mode."""
    um_leave = getattr(user, "username", None) or f"User {user.id}"
    if code not in active_editors:
        return
    nodes_to_remove = []
    for node_id, editors in active_editors[code].items():
        if user.id in editors:
            editors.pop(user.id, None)
            await broadcast_to_others(
                code,
                user.id,
                {
                    "type": "node_editing",
                    "node_id": node_id,
                    "user_id": user.id,
                    "username": um_leave,
                    "editing": False,
                    "color": None,
                    "emoji": None,
                },
            )
            if not editors:
                nodes_to_remove.append(node_id)
    for node_id in nodes_to_remove:
        del active_editors[code][node_id]
    if not active_editors[code]:
        del active_editors[code]


async def finalize_canvas_collab_disconnect(
    *,
    code: str,
    user: object,
) -> None:
    """Editor cleanup, connection maps, participant removal, user_left fan-out."""
    if is_ws_fanout_enabled():
        await _finalize_editors_fanout_disconnect(code, user)
    else:
        await _finalize_editors_local_disconnect(code, user)

    if code in active_connections:
        active_connections[code].pop(user.id, None)
        if not active_connections[code]:
            del active_connections[code]

    await workshop_service.remove_participant(code, user.id)

    await broadcast_to_others(
        code,
        user.id,
        {
            "type": "user_left",
            "user_id": user.id,
        },
    )
