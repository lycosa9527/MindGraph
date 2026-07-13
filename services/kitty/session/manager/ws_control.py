"""Kitty Session Manager — WS attach/detach hooks via Redis SoT.

Full rebond orchestration stays coordinated with lifecycle/ops; these helpers
are the single write path for pairing leases.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.session.manager.action_journal import append_journal_simple
from services.kitty.session.manager.redis_sot import (
    sot_clear_canvas_owner_present,
    sot_clear_mobile_scope,
    sot_mark_canvas_owner_present,
    sot_mark_mobile_active,
)


async def attach_lane(
    *,
    user_id: int,
    scope: str,
    lane: str,
    voice_session_id: Optional[str] = None,
    canvas_owner: bool = False,
) -> None:
    """Record Redis pairing state after a Kitty WS start succeeds."""
    normalized = normalize_kitty_diagram_session_id(scope)
    if normalized is None:
        return
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return
    if uid <= 0:
        return

    if lane == "mobile":
        await sot_mark_mobile_active(uid, normalized)
    if canvas_owner or lane == "desktop":
        if canvas_owner:
            await sot_mark_canvas_owner_present(uid, normalized)

    await append_journal_simple(
        kind="attach",
        user_id=uid,
        diagram_scope=normalized,
        lane=lane,
        voice_session_id=voice_session_id,
        detail={"canvas_owner": bool(canvas_owner)},
    )


async def detach_lane(
    *,
    user_id: int,
    scope: str,
    lane: str,
    voice_session_id: Optional[str] = None,
    canvas_owner: bool = False,
) -> None:
    """Clear Redis pairing state when a Kitty WS session ends."""
    normalized = normalize_kitty_diagram_session_id(scope)
    if normalized is None:
        return
    try:
        uid = int(user_id)
    except (TypeError, ValueError):
        return
    if uid <= 0:
        return

    if lane == "mobile":
        await sot_clear_mobile_scope(uid, normalized)
    if canvas_owner:
        await sot_clear_canvas_owner_present(uid, normalized)

    await append_journal_simple(
        kind="detach",
        user_id=uid,
        diagram_scope=normalized,
        lane=lane,
        voice_session_id=voice_session_id,
        detail={"canvas_owner": bool(canvas_owner)},
    )
