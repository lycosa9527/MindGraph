"""On-demand pairing snapshot for mobile Kitty (server truth)."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from redis.exceptions import RedisError

from services.infrastructure.monitoring.ws_metrics import record_kitty_refcount_meta_drift
from services.kitty.infra.desktop.kitty_desktop_focus import get_kitty_desktop_focus_diagram
from services.kitty.infra.redis.kitty_redis_keys import kitty_sessionmeta_key
from services.kitty.infra.redis.kitty_scope_refcount import kitty_scope_refcount_read
from services.kitty.infra.redis.kitty_session_redis import (
    kitty_mobile_indicator_armed_for_user,
    load_kitty_live_context,
)
from services.redis.redis_async_client import get_async_redis

logger = logging.getLogger(__name__)


async def _sessionmeta_subset(scope: str, user_id: int) -> Optional[Dict[str, Any]]:
    redis = get_async_redis()
    if redis is None:
        return None
    try:
        raw = await redis.get(kitty_sessionmeta_key(scope))
        if not raw:
            return None
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        meta = json.loads(text)
        if not isinstance(meta, dict):
            return None
        if int(meta.get("user_id", -1)) != int(user_id):
            return None
        return {
            "updated_at": meta.get("updated_at"),
            "client_lane": meta.get("client_lane"),
            "active_diagram_library_id": meta.get("active_diagram_library_id"),
        }
    except (RedisError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.debug("[AgentHubSnapshot] sessionmeta read failed scope=%s: %s", scope, exc)
        return None


async def _live_spec_summary(
    scope: str,
    user_id: int,
    meta_subset: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if meta_subset is None:
        meta_subset = await _sessionmeta_subset(scope, user_id)
    if meta_subset is None:
        return None
    live = await load_kitty_live_context(scope)
    if not live:
        return None
    dd = live.get("diagram_data") if isinstance(live.get("diagram_data"), dict) else {}
    children = dd.get("children")
    child_count = len(children) if isinstance(children, list) else 0
    return {
        "updated_at": live.get("updated_at"),
        "diagram_type": live.get("diagram_type"),
        "diagram_library_id": live.get("diagram_library_id"),
        "diagram_children_count": child_count,
    }


async def build_desktop_pairing_snapshot(
    user_id: int,
    voice_diagram_scope: str,
    *,
    client_lane: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Bounded JSON for the mobile agent: desktop focus, scope alignment, sanitized Redis rows, refcount.
    """
    focus_id, focus_ts = await get_kitty_desktop_focus_diagram(int(user_id))
    scope_norm = voice_diagram_scope.strip()
    meta_subset = await _sessionmeta_subset(scope_norm, int(user_id))
    live_sum = await _live_spec_summary(scope_norm, int(user_id), meta_subset)
    armed = await kitty_mobile_indicator_armed_for_user(scope_norm, int(user_id))
    refcount = await kitty_scope_refcount_read(scope_norm)
    meta_exists = meta_subset is not None
    rc_val = refcount
    drift = (meta_exists and (rc_val is None or rc_val <= 0)) or (not meta_exists and rc_val is not None and rc_val > 0)
    if drift:
        record_kitty_refcount_meta_drift()
    aligns = bool(focus_id and isinstance(focus_id, str) and focus_id.strip() == scope_norm)
    return {
        "desktop_focus": {"diagram_library_id": focus_id, "updated_at": focus_ts},
        "current_voice_scope": scope_norm,
        "scope_aligns_with_desktop_focus": aligns,
        "redis_sessionmeta": meta_subset,
        "redis_live_spec_summary": live_sum,
        "mobile_lane_hint": armed,
        "global_ws_refcount": refcount,
        "client_lane": client_lane,
    }
