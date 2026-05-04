"""
In-place viewer ↔ editor role change without WebSocket reconnect (Phase 8.6).

Only the workshop host (role="host") can promote a viewer to editor or demote
an editor to viewer.  The existing WebSocket, writer Task, and send_queue are
preserved; only the handle type and dispatch table change.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS,
    AnyHandle,
    ConnectionHandle,
    ViewerHandle,
    _get_room_lock,
    enqueue,
)

logger = logging.getLogger(__name__)


async def promote_to_editor(
    code: str,
    target_user_id: int,
    promoted_by: int,
    *,
    diagram_owner_id: Optional[int] = None,
) -> bool:
    """
    Upgrade a ViewerHandle to a ConnectionHandle in place.

    The writer task and send_queue are inherited (no interruption).
    A new coalesce_buffer / coalesce_lock / flush_task are allocated.
    Returns True on success, False if target is not a viewer or not found.
    """
    room_lock = await _get_room_lock(code)
    async with room_lock:
        room = ACTIVE_CONNECTIONS.get(code)
        if room is None:
            return False
        handle = room.get(target_user_id)
        if not isinstance(handle, ViewerHandle):
            return False

        new_role = (
            "host"
            if (
                diagram_owner_id is not None
                and target_user_id == diagram_owner_id
            )
            else "editor"
        )
        new_handle = ConnectionHandle(
            websocket=handle.websocket,
            code=code,
            user_id=target_user_id,
            send_queue=handle.send_queue,
            role=new_role,
            writer_task=handle.writer_task,
        )
        room[target_user_id] = new_handle

    role_changed = {
        "type": "role_changed",
        "user_id": target_user_id,
        "role": new_role,
        "promoted_by": promoted_by,
    }
    await enqueue(new_handle, role_changed, "joined")
    from routers.api.workshop_ws_broadcast import broadcast_to_others as _broadcast_others_promo

    await _broadcast_others_promo(code, target_user_id, role_changed)
    logger.info(
        "[RoleChange] user=%s promoted to %s in room=%s by user=%s",
        target_user_id, new_role, code, promoted_by,
    )
    return True


async def demote_to_viewer(
    code: str,
    target_user_id: int,
    demoted_by: int,
) -> bool:
    """
    Downgrade a ConnectionHandle (editor) to a ViewerHandle in place.

    The flush_task (if running) is cancelled; coalesce_buffer is dropped.
    Returns True on success, False if target is already viewer or not found.
    """
    room_lock = await _get_room_lock(code)
    async with room_lock:
        room = ACTIVE_CONNECTIONS.get(code)
        if room is None:
            return False
        handle = room.get(target_user_id)
        if not isinstance(handle, ConnectionHandle):
            return False
        if handle.role == "host":
            return False

        flush_task = handle.flush_task
        if flush_task is not None and not flush_task.done():
            flush_task.cancel()

        new_handle = ViewerHandle(
            websocket=handle.websocket,
            code=code,
            user_id=target_user_id,
            send_queue=handle.send_queue,
            role="viewer",
            writer_task=handle.writer_task,
            last_seen_seq=0,
        )
        room[target_user_id] = new_handle

    role_changed = {
        "type": "role_changed",
        "user_id": target_user_id,
        "role": "viewer",
        "demoted_by": demoted_by,
    }
    await enqueue(new_handle, role_changed, "joined")
    from routers.api.workshop_ws_broadcast import broadcast_to_others as _broadcast_others_demo

    await _broadcast_others_demo(code, target_user_id, role_changed)
    logger.info(
        "[RoleChange] user=%s demoted to viewer in room=%s by user=%s",
        target_user_id, code, demoted_by,
    )
    return True


async def handle_role_change(ctx: Any, message: dict) -> None:
    """
    Process a role_change control frame from the room host.

    Only ConnectionHandle with role="host" may issue this command.
    Message shape: {"type": "role_change", "user_id": <int>, "to": "editor"|"viewer"}
    """
    requester_handle: AnyHandle | None = ctx.handle
    if requester_handle is None:
        return
    if not isinstance(requester_handle, ConnectionHandle):
        await enqueue(
            requester_handle,
            {"type": "error", "message": "Only the host may change roles"},
            "error",
        )
        return
    if requester_handle.role != "host":
        await enqueue(
            requester_handle,
            {"type": "error", "message": "Only the host may change roles"},
            "error",
        )
        return

    raw_uid = message.get("user_id")
    if not isinstance(raw_uid, int):
        await enqueue(
            requester_handle,
            {"type": "error", "message": "role_change: user_id must be an integer"},
            "error",
        )
        return
    target_uid: int = raw_uid
    to_role: str = str(message.get("to", ""))
    if to_role not in ("editor", "viewer"):
        await enqueue(
            requester_handle,
            {"type": "error", "message": "role_change: to must be 'editor' or 'viewer'"},
            "error",
        )
        return

    if to_role == "editor":
        success = await promote_to_editor(
            ctx.code,
            target_uid,
            ctx.user.id,
            diagram_owner_id=ctx.owner_id,
        )
    else:
        success = await demote_to_viewer(ctx.code, target_uid, ctx.user.id)

    if not success:
        err_reason = ""
        room_h = ACTIVE_CONNECTIONS.get(ctx.code, {}).get(target_uid)
        if (
            to_role == "viewer"
            and isinstance(room_h, ConnectionHandle)
            and room_h.role == "host"
        ):
            err_reason = "; cannot demote the room host"

        await enqueue(
            requester_handle,
            {
                "type": "error",
                "message": (
                    f"role_change: user {target_uid} not found "
                    f"or already {to_role}{err_reason}"
                ),
            },
            "error",
        )
        return

    try:
        from services.infrastructure.monitoring.ws_metrics import (
            record_ws_role_promotion,
            record_ws_role_demotion,
        )
        if to_role == "editor":
            record_ws_role_promotion()
        else:
            record_ws_role_demotion()
    except Exception:
        pass

    await enqueue(
        requester_handle,
        {
            "type": "role_change_ack",
            "user_id": target_uid,
            "to": to_role,
        },
        "joined",
    )
