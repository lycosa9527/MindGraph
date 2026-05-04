"""Disconnect / cleanup path for canvas collaboration WebSocket."""

import asyncio
import logging
from typing import Optional

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
    ACTIVE_EDITORS as active_editors,
    AnyHandle,
    unregister_connection,
)
from services.online_collab.core.online_collab_manager import (
    get_online_collab_manager,
)
from services.online_collab.participant.online_collab_ws_editor_redis import (
    load_editors,
    purge_user_from_all_nodes_redis_watched,
)

from routers.api.workshop_ws_broadcast import broadcast_to_all, broadcast_to_others
from services.online_collab.participant.collab_display_name import (
    workshop_collab_member_display_name,
)

logger = logging.getLogger(__name__)


async def _finalize_editors_fanout_disconnect(code: str, user: object) -> None:
    """Clear editor state when multi-worker Redis fan-out is enabled."""
    um_leave = workshop_collab_member_display_name(user)
    nodes_cleared, atomic_ok = await purge_user_from_all_nodes_redis_watched(
        code,
        user.id,
    )
    if not atomic_ok:
        logger.warning(
            "[WorkshopWS] Redis editor atomic purge failed; log-and-drop save "
            "to avoid clobbering concurrent writes (locks self-heal via TTL) "
            "code=%s user_id=%s",
            code,
            user.id,
        )
        editors_map = await load_editors(code)
        nodes_cleared = [
            nid for nid, ed in editors_map.items() if user.id in ed
        ]

    if nodes_cleared:
        events = [
            {
                "type": "node_editing",
                "node_id": nid,
                "user_id": user.id,
                "username": um_leave,
                "editing": False,
                "color": None,
                "emoji": None,
            }
            for nid in nodes_cleared
        ]
        logger.debug(
            "[WorkshopWS] editor_purge_fanout code=%s user=%s cleared_nodes=%d",
            code, user.id, len(nodes_cleared),
        )
        await broadcast_to_others(
            code,
            user.id,
            {"type": "node_editing_batch_ws", "events": events},
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
    um_leave = workshop_collab_member_display_name(user)
    if code not in active_editors:
        return
    events = []
    nodes_to_remove = []
    for node_id, editors in active_editors[code].items():
        if user.id in editors:
            editors.pop(user.id, None)
            events.append(
                {
                    "type": "node_editing",
                    "node_id": node_id,
                    "user_id": user.id,
                    "username": um_leave,
                    "editing": False,
                    "color": None,
                    "emoji": None,
                }
            )
            if not editors:
                nodes_to_remove.append(node_id)

    if events:
        logger.debug(
            "[WorkshopWS] editor_purge_local code=%s user=%s cleared_nodes=%d",
            code, user.id, len(events),
        )
        await broadcast_to_others(
            code,
            user.id,
            {"type": "node_editing_batch_ws", "events": events},
        )

    for node_id in nodes_to_remove:
        del active_editors[code][node_id]
    if not active_editors[code]:
        del active_editors[code]


async def clear_editor_state_for_superseded_session(code: str, user: object) -> None:
    """
    When the same user opens a new tab, clear editing locks for the prior
    in-process / Redis state and notify peers (before the new handle registers).
    """
    if is_ws_fanout_enabled():
        await _finalize_editors_fanout_disconnect(code, user)
    else:
        await _finalize_editors_local_disconnect(code, user)


async def _protected_disconnect_cleanup(
    *,
    code: str,
    user: object,
    handle: AnyHandle,
    workshop_owner_id: Optional[int],
) -> None:
    """Inner body of disconnect cleanup — called via asyncio.shield."""
    current_handle = active_connections.get(code, {}).get(user.id)
    mismatched_owner = current_handle is not handle

    if is_ws_fanout_enabled():
        await _finalize_editors_fanout_disconnect(code, user)
    else:
        await _finalize_editors_local_disconnect(code, user)

    if mismatched_owner:
        logger.info(
            "[CanvasCollabWS] Deferred participant cleanup (socket superseded) "
            "user=%s code=%s",
            user.id, code,
        )
        return

    await unregister_connection(code, user.id)
    await get_online_collab_manager().remove_participant(code, user.id)

    logger.info(
        "[WorkshopWS] disconnect_cleanup user=%s code=%s is_owner=%s",
        user.id, code,
        workshop_owner_id is not None and int(getattr(user, "id", -1)) == int(workshop_owner_id),
    )

    await broadcast_to_others(
        code,
        user.id,
        {
            "type": "user_left",
            "user_id": user.id,
        },
    )

    if (
        workshop_owner_id is not None
        and int(getattr(user, "id", -1)) == int(workshop_owner_id)
    ):
        logger.debug(
            "[WorkshopWS] owner_disconnected broadcast code=%s user=%s",
            code, user.id,
        )
        await broadcast_to_all(
            code,
            {
                "type": "owner_disconnected",
                "user_id": user.id,
                "workshop_continues": True,
            },
        )


async def finalize_canvas_collab_disconnect(
    *,
    code: str,
    user: object,
    handle: AnyHandle,
    workshop_owner_id: Optional[int] = None,
) -> None:
    """
    Editor cleanup, connection maps (owner socket only), participant removal.

    Wraps the critical cleanup in ``asyncio.shield`` so that cancellation of
    the parent WebSocket task (e.g. client disconnect mid-cleanup) does not
    leave editor locks, connection map entries, or participant sets in a
    half-cleaned state. Without the shield, a racing cancel between the
    editor-purge and participant-remove steps would orphan locks and
    permanently show the user as "still editing" until TTL expiry.
    """
    cleanup_coro = _protected_disconnect_cleanup(
        code=code,
        user=user,
        handle=handle,
        workshop_owner_id=workshop_owner_id,
    )
    try:
        await asyncio.shield(cleanup_coro)
    except asyncio.CancelledError:
        logger.warning(
            "[CanvasCollabWS] disconnect cleanup cancelled but shielded; "
            "cleanup continues in background user=%s code=%s",
            getattr(user, "id", None),
            code,
        )
        raise
    except Exception as exc:
        logger.warning(
            "[CanvasCollabWS] disconnect cleanup failed user=%s code=%s: %s",
            getattr(user, "id", None),
            code,
            exc,
        )
