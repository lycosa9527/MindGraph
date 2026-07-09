"""Kitty REST endpoint logic; :mod:`routers.features.kitty.kitty_routes` wires FastAPI routes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import HTTPException

from config.settings import config
from models.domain.auth import User
from services.agent_hub import get_mind_graph_agent_hub
from services.kitty.infra.desktop.kitty_desktop_action_queue import (
    consume_kitty_desktop_action_explicit_drain,
    enqueue_kitty_desktop_action,
    mark_kitty_desktop_action_explicit_drain,
    pop_kitty_desktop_action_wait,
)
from services.kitty.infra.desktop.kitty_desktop_focus import (
    get_kitty_desktop_focus_diagram,
    set_kitty_desktop_focus_diagram,
)
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_desktop_action_pending,
)
from services.kitty.infra.desktop.kitty_mobile_active import read_kitty_mobile_active
from services.kitty.infra.guards.http_guards import (
    KITTY_MOBILE_BOOTSTRAP_DISABLED_BODY,
    kitty_http_allowed,
)
from services.kitty.infra.redis.kitty_session_redis import (
    kitty_mobile_indicator_armed_for_user,
    kitty_sessionmeta_active_for_user,
    load_kitty_live_context,
)
from services.kitty.infra.scope.kitty_scope_access import user_may_access_kitty_scope
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.session.one_sentence_session_pg import (
    get_one_sentence_session,
    list_one_sentence_sessions,
)
from services.kitty.session.one_sentence_turns import (
    append_one_sentence_turn,
    append_one_sentence_turns_batch,
    list_one_sentence_turns,
    migrate_one_sentence_scope,
)

_INACTIVE_MOBILE_ACTIVE: Dict[str, Any] = {
    "active": False,
    "scopes": [],
    "primary_scope": None,
}


async def _pop_desktop_action_for_poll(
    user_id: int,
    *,
    mobile_active: bool,
    wait_sec: float,
) -> Optional[Dict[str, Any]]:
    """Pop queued desktop navigation.

    Long-poll BLPOP requires ``mobile_active`` (live mobile Kitty WS). Inactive instant
    LPOP runs only after mobile REST enqueue sets the one-shot explicit-drain flag.
    Stale queue items are discarded so passive desktop polling does not replay old jumps.
    """
    discard_stale = True
    if mobile_active:
        return await pop_kitty_desktop_action_wait(
            user_id,
            wait_sec,
            discard_stale=discard_stale,
        )
    if wait_sec <= 0:
        if not await consume_kitty_desktop_action_explicit_drain(user_id):
            return None
        return await pop_kitty_desktop_action_wait(
            user_id,
            0,
            discard_stale=discard_stale,
        )
    return None


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
    mobile_active = mobile.get("active") is True
    data = await _pop_desktop_action_for_poll(
        int(current_user.id),
        mobile_active=mobile_active,
        wait_sec=wait_sec,
    )
    return {"action": data}


async def kitty_rest_desktop_pairing(
    current_user: User,
    *,
    wait_sec: float = 0,
) -> Dict[str, Any]:
    """
    Combined desktop poll: ``mobile_active`` gate plus optional long-poll action pop.

    When ``active`` is false, instant pop (``wait_sec=0``) drains only after mobile REST
    enqueue (library diagram pick). Long-poll BLPOP requires live mobile Kitty.
    """
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {**_INACTIVE_MOBILE_ACTIVE, "action": None}
    if not await kitty_http_allowed(current_user):
        return {**_INACTIVE_MOBILE_ACTIVE, "action": None}
    mobile = await read_kitty_mobile_active(int(current_user.id))
    mobile_active = mobile.get("active") is True
    action = await _pop_desktop_action_for_poll(
        int(current_user.id),
        mobile_active=mobile_active,
        wait_sec=wait_sec,
    )
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


async def kitty_rest_one_sentence_turns_get(
    current_user: User,
    diagram_session_id: str,
    *,
    limit: int = 100,
) -> Dict[str, Any]:
    """Return persisted one-sentence panel turns for session restore and analytics."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled", "turns": []}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied", "turns": []}
    scope = normalize_kitty_diagram_session_id(diagram_session_id)
    if scope is None:
        raise HTTPException(status_code=400, detail="Invalid diagram session id")
    return await list_one_sentence_turns(scope, int(current_user.id), limit=limit, include_meta=True)


async def kitty_rest_one_sentence_turns_post(
    current_user: User,
    diagram_session_id: str,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Append create-phase turns from the one-sentence panel (first message uses REST auto-complete)."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled", "stored": []}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied", "stored": []}
    scope = normalize_kitty_diagram_session_id(diagram_session_id)
    if scope is None:
        raise HTTPException(status_code=400, detail="Invalid diagram session id")
    if not await user_may_access_kitty_scope(int(current_user.id), scope):
        return {"ok": False, "reason": "access_denied", "stored": []}

    turns_in = body.get("turns")
    org_id = getattr(current_user, "organization_id", None)
    if isinstance(turns_in, list) and len(turns_in) > 0:
        stored = await append_one_sentence_turns_batch(
            scope,
            int(current_user.id),
            turns_in,
            organization_id=org_id,
        )
        return {"ok": True, "stored": stored}

    single = body.get("turn")
    if isinstance(single, dict):
        row = await append_one_sentence_turn(
            scope,
            int(current_user.id),
            single,
            organization_id=org_id,
        )
        if row is None:
            return {"ok": False, "reason": "invalid_turn", "stored": []}
        return {"ok": True, "stored": [row]}

    raise HTTPException(status_code=400, detail="Expected turn or turns payload")


async def kitty_rest_one_sentence_sessions_list(
    current_user: User,
    *,
    limit: int = 50,
    before_id: Optional[str] = None,
) -> Dict[str, Any]:
    """List trackable one-sentence sessions for the authenticated user (analytics-ready)."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled", "sessions": []}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied", "sessions": []}
    sessions = await list_one_sentence_sessions(
        user_id=int(current_user.id),
        limit=limit,
        before_id=before_id,
    )
    return {"ok": True, "sessions": sessions}


async def kitty_rest_one_sentence_session_get(
    current_user: User,
    session_id: str,
    *,
    limit: int = 100,
) -> Dict[str, Any]:
    """Return one session summary plus its turns (backend analytics / future UI)."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled"}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied"}
    summary = await get_one_sentence_session(session_id=session_id, user_id=int(current_user.id))
    if summary is None:
        return {"ok": False, "reason": "not_found"}
    turns_payload = await list_one_sentence_turns(
        summary["diagram_scope"],
        int(current_user.id),
        limit=limit,
        include_meta=False,
        session_id=session_id,
    )
    return {
        "ok": True,
        "session": summary,
        "turns": turns_payload.get("turns", []),
        "storage": turns_payload.get("storage"),
    }


async def kitty_rest_one_sentence_migrate_scope(
    current_user: User,
    body: Dict[str, Any],
) -> Dict[str, Any]:
    """Move one-sentence history from ephemeral Kitty scope to saved diagram id."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled"}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied"}

    from_scope = normalize_kitty_diagram_session_id(str(body.get("from_scope") or ""))
    to_scope = normalize_kitty_diagram_session_id(str(body.get("to_scope") or ""))
    if from_scope is None or to_scope is None:
        raise HTTPException(status_code=400, detail="Invalid from_scope or to_scope")

    return await migrate_one_sentence_scope(
        user_id=int(current_user.id),
        from_scope=from_scope,
        to_scope=to_scope,
    )


async def kitty_rest_desktop_action_enqueue(
    current_user: User,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Queue a desktop navigation action from mobile Kitty (library pick, etc.)."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": False, "reason": "feature_disabled"}
    if not await kitty_http_allowed(current_user):
        return {"ok": False, "reason": "access_denied"}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload")
    ok = await enqueue_kitty_desktop_action(int(current_user.id), payload)
    if not ok:
        return {"ok": False, "reason": "rejected"}
    await mark_kitty_desktop_action_explicit_drain(int(current_user.id))
    await publish_kitty_desktop_action_pending(int(current_user.id))
    return {"ok": True}
