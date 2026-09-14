"""Refresh training presence while an SSE or watch socket is open.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.features.training.activity_store import refresh_activity_lease
from services.features.training.session_store import (
    TrainingSessionError,
    get_instructor_pointer,
    heartbeat,
)


async def refresh_org_connection_lease(org_id: int, user_id: int) -> None:
    """Keep owner heartbeat and teacher rail rows live for this connection."""
    await _touch_owner(org_id, user_id)
    await refresh_activity_lease(org_id, user_id)


async def refresh_user_connection_lease(user_id: int) -> None:
    """Refresh the hosted room while the instructor's user-wake socket is open."""
    pointer = await get_instructor_pointer(user_id)
    if pointer is None:
        return
    try:
        org_id = int(pointer.get("org_id") or 0)
    except (TypeError, ValueError):
        return
    if org_id <= 0:
        return
    await _touch_owner(org_id, user_id)


async def _touch_owner(org_id: int, user_id: int) -> None:
    """Heartbeat when this user owns the org room; ignore everyone else."""
    try:
        await heartbeat(org_id, user_id)
    except TrainingSessionError:
        return
