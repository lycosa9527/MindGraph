"""Kitty REST endpoint logic; :mod:`routers.features.voice.kitty_routes` wires FastAPI routes."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from config.settings import config
from models.domain.auth import User

from services.agent_hub import get_mind_graph_agent_hub
from services.kitty.kitty_desktop_action_queue import pop_kitty_desktop_action_wait
from services.kitty.kitty_desktop_focus import (
    get_kitty_desktop_focus_diagram,
    set_kitty_desktop_focus_diagram,
)
from services.kitty.kitty_mobile_active import read_kitty_mobile_active
from services.kitty.kitty_session_redis import (
    kitty_mobile_indicator_armed_for_user,
    kitty_sessionmeta_active_for_user,
    load_kitty_live_context,
)
from services.kitty.kitty_ws_scope import normalize_kitty_diagram_session_id

from services.kitty_voice.ws_guards import (
    KITTY_MOBILE_BOOTSTRAP_DISABLED_BODY,
    kitty_http_allowed,
)


_INACTIVE_MOBILE_ACTIVE: Dict[str, Any] = {
    "active": False,
    "scopes": [],
    "primary_scope": None,
}


async def kitty_rest_mobile_open_bootstrap(
    current_user: User,
    *,
    suggested_scope: Optional[str] = None,
) -> Dict[str, Any]:
    """Mobile preflight before ``/ws/kitty``."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return KITTY_MOBILE_BOOTSTRAP_DISABLED_BODY
    if not await kitty_http_allowed(current_user):
        return KITTY_MOBILE_BOOTSTRAP_DISABLED_BODY
    hub = get_mind_graph_agent_hub()
    return await hub.get_diagram_context(
        user_id=int(current_user.id),
        source_module="kitty_mobile_bootstrap_http",
        client_lane="mobile",
        client_suggested_scope=suggested_scope,
    )


async def kitty_rest_desktop_action_pop(
    current_user: User,
    *,
    wait_sec: float = 0,
) -> Dict[str, Any]:
    """Pop one queued desktop action for the user (optional BLPOP long-poll)."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"action": None}
    if not await kitty_http_allowed(current_user):
        return {"action": None}
    mobile = await read_kitty_mobile_active(int(current_user.id))
    if not mobile.get("active"):
        return {"action": None}
    data = await pop_kitty_desktop_action_wait(int(current_user.id), wait_sec)
    return {"action": data}


async def kitty_rest_desktop_pairing(
    current_user: User,
    *,
    wait_sec: float = 0,
) -> Dict[str, Any]:
    """
    Combined desktop poll: ``mobile_active`` gate plus optional long-poll action pop.

    When ``active`` is false, returns immediately with ``action: null``. When active and
    ``wait_sec > 0``, blocks on Redis BLPOP for the next queued desktop action.
    """
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {**_INACTIVE_MOBILE_ACTIVE, "action": None}
    if not await kitty_http_allowed(current_user):
        return {**_INACTIVE_MOBILE_ACTIVE, "action": None}
    mobile = await read_kitty_mobile_active(int(current_user.id))
    if not mobile.get("active"):
        return {**mobile, "action": None}
    action = await pop_kitty_desktop_action_wait(int(current_user.id), wait_sec)
    return {**mobile, "action": action}


async def kitty_rest_mobile_active_get(current_user: User) -> Dict[str, Any]:
    """Whether this user has any active mobile-lane Kitty WebSocket (desktop poll gate)."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"active": False, "scopes": [], "primary_scope": None}
    if not await kitty_http_allowed(current_user):
        return {"active": False, "scopes": [], "primary_scope": None}
    return await read_kitty_mobile_active(int(current_user.id))


async def kitty_rest_desktop_focus_get(current_user: User) -> Dict[str, Any]:
    """Last desktop library diagram id for mobile pairing."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"diagram_library_id": None, "updated_at": None}
    if not await kitty_http_allowed(current_user):
        return {"diagram_library_id": None, "updated_at": None}
    lib_id, updated_at = await get_kitty_desktop_focus_diagram(int(current_user.id))
    return {"diagram_library_id": lib_id, "updated_at": updated_at}


async def kitty_rest_desktop_focus_put(
    current_user: User,
    diagram_library_id: Optional[str],
) -> Dict[str, Any]:
    """Publish or clear desktop library focus."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": True, "diagram_library_id": None, "updated_at": None}
    if not await kitty_http_allowed(current_user):
        return {"ok": True, "diagram_library_id": None, "updated_at": None}
    await set_kitty_desktop_focus_diagram(int(current_user.id), diagram_library_id)
    lib_id, updated_at = await get_kitty_desktop_focus_diagram(int(current_user.id))
    return {"ok": True, "diagram_library_id": lib_id, "updated_at": updated_at}


async def kitty_rest_live_context_snapshot(
    current_user: User,
    diagram_session_id: str,
) -> Dict[str, Any]:
    """Redis ``kitty:live_spec`` snapshot for desktop canvas sync."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled"}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied"}
    scope = normalize_kitty_diagram_session_id(diagram_session_id)
    if scope is None:
        raise HTTPException(status_code=400, detail="Invalid diagram session id")
    uid = int(current_user.id)
    if not await kitty_sessionmeta_active_for_user(scope, uid):
        return {"ok": False, "reason": "no_session"}
    live = await load_kitty_live_context(scope)
    if not live:
        return {"ok": False, "reason": "no_live"}
    return {
        "ok": True,
        "updated_at": live.get("updated_at"),
        "diagram_type": live.get("diagram_type"),
        "active_panel": live.get("active_panel"),
        "diagram_data": live.get("diagram_data") or {},
        "selected_nodes": live.get("selected_nodes") or [],
    }


async def kitty_rest_mobile_lane_hint(
    current_user: User,
    diagram_session_id: str,
) -> Dict[str, Any]:
    """Whether a mobile-lane Kitty WS is active on this scope."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"armed": False}
    if not await kitty_http_allowed(current_user):
        return {"armed": False}
    scope = normalize_kitty_diagram_session_id(diagram_session_id)
    if scope is None:
        raise HTTPException(status_code=400, detail="Invalid diagram session id")
    armed = await kitty_mobile_indicator_armed_for_user(scope, int(current_user.id))
    return {"armed": armed}
