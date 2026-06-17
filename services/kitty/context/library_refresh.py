"""Periodically refresh Kitty voice context from the authoritative library row.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import copy
import time
from datetime import datetime, timezone
from typing import Any, Dict

from services.kitty.infra.bootstrap.kitty_context_hydrate import merge_voice_context_with_library
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.redis.kitty_session_redis import (
    load_kitty_live_context,
    schedule_persist_kitty_live_debounced,
)
from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.session.events import emit_kitty_session_event
from services.kitty.session.ops import (
    get_agent_session_id,
    get_voice_session,
    update_panel_context,
)
from services.kitty.session.runtime_state import logger
from services.redis.cache.redis_diagram_cache import get_diagram_cache

_REFRESH_MIN_INTERVAL = 1.5
_CONTEXT_FRESH_SEC = 2.0
_VOICE_MUTATION_FRESH_SEC = 30.0


def bump_voice_mutation_freshness(voice_session_id: str) -> None:
    """Mark recent voice diagram mutation so library refresh does not clobber edits."""
    sess = get_voice_session(voice_session_id)
    if sess is None:
        return
    now = time.monotonic()
    sess["_last_voice_mutation_mono"] = now
    sess["_last_context_update_mono"] = now


def _library_row_updated_ts(cached: Dict[str, Any]) -> int:
    """Library row updated ts."""
    raw = cached.get("updated_at")
    if raw is None:
        return 0
    if isinstance(raw, (int, float)):
        return int(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            return 0
    return 0


async def live_spec_newer_than_library(
    user_id: int,
    library_id: str,
    diagram_session_id: str,
) -> bool:
    """True when Redis live_spec is newer than the saved library row."""
    live = await load_kitty_live_context(diagram_session_id.strip())
    if not live:
        return False
    live_ts = int(live.get("updated_at") or 0)
    if live_ts <= 0:
        return False
    try:
        cached = await get_diagram_cache().get_diagram(user_id, library_id.strip())
    except (RuntimeError, ValueError, TypeError, OSError):
        return True
    if not cached:
        return True
    lib_ts = _library_row_updated_ts(cached)
    return live_ts > lib_ts


def should_skip_library_refresh(
    voice_session_id: str,
    *,
    force: bool = False,
) -> bool:
    """
    Skip library re-merge when voice context is fresh or recently mutated.

    Prevents ``prefer_server_diagram_nodes`` from undoing in-flight voice edits.
    """
    if force:
        return False
    sess = get_voice_session(voice_session_id)
    if sess is None:
        return True
    now = time.monotonic()
    last_mut = float(sess.get("_last_voice_mutation_mono") or 0.0)
    if last_mut > 0 and (now - last_mut) < _VOICE_MUTATION_FRESH_SEC:
        return True
    last_ctx = float(sess.get("_last_context_update_mono") or 0.0)
    if last_ctx > 0 and (now - last_ctx) < _CONTEXT_FRESH_SEC:
        return True
    return False


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
    if should_skip_library_refresh(voice_session_id, force=force):
        return
    ctx0: Dict[str, Any] = dict(sess.get("context") or {})
    lib = ctx0.get("diagram_library_id")
    if not lib or not isinstance(lib, str) or not lib.strip():
        return
    ws_scope = sess.get("diagram_session_id")
    if isinstance(ws_scope, str) and ws_scope.strip():
        user_raw = sess.get("user_id")
        try:
            uid = int(user_raw) if user_raw is not None else None
        except (TypeError, ValueError):
            uid = None
        if uid is not None and await live_spec_newer_than_library(uid, lib, ws_scope):
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
    nodes_raw = merged_ctx.get("diagram_data")
    node_count = len(nodes_raw.get("children", [])) if isinstance(nodes_raw, dict) else 0
    kitty_wf_log(
        "library_refresh_apply",
        f"type={res_dt} nodes={node_count}",
        voice_session_id=voice_session_id,
        scope=diagram_session_id,
    )
