"""Periodically refresh Kitty voice context from the authoritative library row."""

from __future__ import annotations

import copy
import time
from typing import Any, Dict

from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.infra.bootstrap.kitty_context_hydrate import merge_voice_context_with_library
from services.kitty.infra.redis.kitty_session_redis import schedule_persist_kitty_live_debounced

from services.kitty.session.events import emit_kitty_session_event
from services.kitty.session.runtime_state import logger
from services.kitty.session.ops import (
    get_agent_session_id,
    get_voice_session,
    update_panel_context,
)

_REFRESH_MIN_INTERVAL = 1.5


async def throttled_refresh_voice_context_from_library(
    *,
    user_id: int,
    voice_session_id: str,
    diagram_session_id: str,
    force: bool = False,
) -> None:
    """
    Re-merge in-memory voice context with the saved diagram so desktop-only edits
    reach Kitty without waiting for a mobile ``context_update``.
    """
    sess = get_voice_session(voice_session_id)
    if sess is None:
        return
    ctx0: Dict[str, Any] = dict(sess.get("context") or {})
    lib = ctx0.get("diagram_library_id")
    if not lib or not isinstance(lib, str) or not lib.strip():
        return
    now = time.monotonic()
    last = float(sess.get("_kitty_library_refresh_mono") or 0.0)
    if not force and (now - last) < _REFRESH_MIN_INTERVAL:
        return
    sess["_kitty_library_refresh_mono"] = now

    panel = sess.get("active_panel") or ctx0.get("active_panel") or "none"
    d_type = sess.get("diagram_type") or ctx0.get("diagram_type") or "circle_map"

    merged_ctx, res_dt, res_panel = await merge_voice_context_with_library(
        user_id,
        ctx0,
        diagram_type=str(d_type),
        active_panel=str(panel),
        prefer_server_diagram_nodes=True,
    )

    old_dt = sess.get("diagram_type")
    sess["diagram_type"] = res_dt
    if old_dt != res_dt:
        logger.info(
            "VOIC | Diagram type refreshed from library: %s -> %s for session %s",
            old_dt,
            res_dt,
            voice_session_id,
        )

    update_panel_context(voice_session_id, res_panel)
    sess["context"] = copy.deepcopy(merged_ctx)
    sess["context"]["diagram_type"] = res_dt

    agent = kitty_agent_manager.get_or_create(get_agent_session_id(voice_session_id))
    diagram_data = dict(merged_ctx.get("diagram_data") or {})
    diagram_data["diagram_type"] = res_dt
    agent.update_diagram_state(diagram_data)
    agent.update_panel_state(res_panel, merged_ctx.get("panels", {}))

    await emit_kitty_session_event(
        voice_session_id,
        "context_update",
        {"reason": "library_refresh"},
    )

    await schedule_persist_kitty_live_debounced(
        diagram_session_id,
        user_id,
        merged_ctx,
        res_dt,
        res_panel,
        voice_session_id=voice_session_id,
    )
