"""
MindMate collab WebSocket disconnect cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging

from services.features.mindmate_collab.manager_access import get_mindmate_collab_manager
from services.features.mindmate_collab.ws_broadcast import broadcast_to_others
from services.features.mindmate_collab.ws_registry import (
    ACTIVE_CONNECTIONS,
    MindmateCollabWsHandle,
    room_key_for_code,
    shutdown_connection_handle,
    unregister_connection,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

logger = logging.getLogger(__name__)


async def _protected_disconnect_cleanup(
    *,
    code: str,
    user_id: int,
    handle: MindmateCollabWsHandle,
) -> None:
    """Remove participant state only when this handle is still the active socket."""
    room_key = room_key_for_code(code)
    bucket = ACTIVE_CONNECTIONS.get(room_key, {})
    current_handle = bucket.get(int(user_id))
    mismatched_owner = current_handle is not handle

    await shutdown_connection_handle(handle)

    if mismatched_owner:
        logger.info(
            "[MindmateCollabWS] Deferred participant cleanup (socket superseded) user=%s code=%s",
            user_id,
            code,
        )
        return

    unregister_connection(code, user_id, handle=handle)
    mgr = get_mindmate_collab_manager()
    await mgr.remove_participant(code, user_id)
    await broadcast_to_others(
        code,
        user_id,
        {"type": "user_left", "user_id": user_id},
    )


async def finalize_mindmate_collab_disconnect(
    *,
    code: str,
    user_id: int,
    handle: MindmateCollabWsHandle,
) -> None:
    """
    Participant removal and user_left broadcast for a disconnecting socket.

    Wraps cleanup in ``asyncio.shield`` so cancellation of the parent WebSocket
    task does not leave participant sets in a half-cleaned state.
    """
    cleanup_coro = _protected_disconnect_cleanup(
        code=code,
        user_id=user_id,
        handle=handle,
    )
    try:
        await asyncio.shield(cleanup_coro)
    except asyncio.CancelledError:
        logger.warning(
            "[MindmateCollabWS] disconnect cleanup cancelled but shielded; "
            "cleanup continues in background user=%s code=%s",
            user_id,
            code,
        )
        raise
    except BACKGROUND_INFRA_ERRORS as exc:
        logger.warning(
            "[MindmateCollabWS] disconnect cleanup failed user=%s code=%s: %s",
            user_id,
            code,
            exc,
        )
