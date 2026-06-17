"""Kitty Agent WebSocket route registration and REST endpoints."""

from fastapi import Body, Depends, HTTPException, Query, WebSocket

from config.settings import config
from models.domain.auth import User
from routers.features.kitty.state import (
    active_websockets,
    logger,
    router,
)
from services.agent_hub import get_mind_graph_agent_hub
from services.kitty.http.handlers import (
    kitty_rest_desktop_action_enqueue,
    kitty_rest_desktop_action_pop,
    kitty_rest_desktop_focus_get,
    kitty_rest_desktop_focus_put,
    kitty_rest_desktop_pairing,
    kitty_rest_live_context_snapshot,
    kitty_rest_mobile_active_get,
    kitty_rest_mobile_lane_hint,
    kitty_rest_mobile_open_bootstrap,
)
from services.kitty.infra.control.kitty_control_fanout import KITTY_CONTROL_REASON_HTTP_CLEANUP
from services.kitty.infra.desktop.kitty_desktop_wake_stream import kitty_desktop_wake_stream_response
from services.kitty.infra.guards.http_guards import kitty_http_allowed
from services.kitty.infra.redis.kitty_scope_refcount import (
    kitty_scope_force_teardown_redis,
    kitty_scope_refcount_read,
)
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.session.ops import cleanup_voice_by_diagram_session
from services.kitty.session.voice_lock import diagram_session_voice_lock
from services.kitty.ws.realtime import kitty_realtime_websocket
from utils.auth import get_current_user


@router.websocket("/ws/kitty/{diagram_session_id}")
async def kitty_conversation(websocket: WebSocket, diagram_session_id: str):
    """Kitty Agent multimodal WebSocket (Qwen Omni realtime)."""
    await kitty_realtime_websocket(websocket, diagram_session_id)


@router.get("/api/kitty/mobile_open_bootstrap")
async def kitty_mobile_open_bootstrap(
    suggested_scope: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
):
    """
    Mobile Kitty preflight: resolve desktop_focus, prefer Redis live_spec (non-mobile desktop
    Kitty on scope), else library row. Used before ``/ws/kitty/{scope}`` to avoid ephemeral
    scope and empty context on first connect.
    """
    return await kitty_rest_mobile_open_bootstrap(current_user, suggested_scope=suggested_scope)


@router.get("/api/kitty/desktop_action/pop")
async def kitty_desktop_action_pop(
    current_user: User = Depends(get_current_user),
    wait_sec: float = Query(default=0, ge=0, le=30),
):
    """
    Pop one Kitty-queued desktop UX action for the signed-in user (FIFO).

    Optional ``wait_sec`` (1–30) long-polls via Redis BLPOP until an action arrives.
    """
    return await kitty_rest_desktop_action_pop(current_user, wait_sec=wait_sec)


@router.post("/api/kitty/desktop_action/enqueue")
async def kitty_desktop_action_enqueue(
    current_user: User = Depends(get_current_user),
    payload: dict = Body(...),
):
    """
    Enqueue a desktop UX action (``open_library_diagram``, ``open_canvas``) from mobile Kitty.
    """
    return await kitty_rest_desktop_action_enqueue(current_user, payload)


@router.get("/api/kitty/desktop_pairing")
async def kitty_desktop_pairing(
    current_user: User = Depends(get_current_user),
    wait_sec: float = Query(default=0, ge=0, le=30),
):
    """
    Combined desktop poll: ``mobile_active`` plus optional long-poll ``action`` pop.

    Desktop SPA uses ``wait_sec=0`` while watching and ``wait_sec=25`` while consuming.
    """
    return await kitty_rest_desktop_pairing(current_user, wait_sec=wait_sec)


@router.get("/api/kitty/desktop_wake/stream")
async def kitty_desktop_wake_stream(current_user: User = Depends(get_current_user)):
    """
    SSE stream: instant ``mobile_active`` wake when phone Kitty connects or disconnects.

    Desktop SPA uses EventSource (cookie auth) to enter consume mode without waiting for
    the 12s watch poll. Action delivery still uses ``desktop_pairing`` long-poll BLPOP.
    """
    return await kitty_desktop_wake_stream_response(current_user)


@router.get("/api/kitty/mobile_active")
async def kitty_mobile_active(current_user: User = Depends(get_current_user)):
    """
    True when this user has any Kitty WebSocket session started from mobile (``client_lane: mobile``).

    Desktop SPA watches this before polling ``desktop_action/pop``.
    """
    return await kitty_rest_mobile_active_get(current_user)


@router.get("/api/kitty/desktop_focus")
async def kitty_desktop_focus_get(current_user: User = Depends(get_current_user)):
    """
    Library diagram id the user last had open on desktop MindGraph, for mobile Kitty pairing.

    Mobile polls this when the local Pinia store has no ``activeDiagramId`` so
    ``/ws/kitty/{scope}`` can align with the computer.
    """
    return await kitty_rest_desktop_focus_get(current_user)


@router.put("/api/kitty/desktop_focus")
async def kitty_desktop_focus_put(
    current_user: User = Depends(get_current_user),
    diagram_library_id: str | None = Body(default=None, embed=True),
):
    """Publish or clear desktop MindGraph library focus for the authenticated user."""
    return await kitty_rest_desktop_focus_put(current_user, diagram_library_id)


@router.get("/api/kitty/live_context/{diagram_session_id}")
async def kitty_live_context_snapshot(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    Return the current Redis ``kitty:live_spec`` for this library scope when the caller
    owns an active Kitty session on that scope (sessionmeta gate).

    Desktop uses this to apply hub-grounded diagram state (voice / context_update /
    ``apply_diagram_spec_mutation`` writes) without relying on phone-only WebSocket frames.
    """
    return await kitty_rest_live_context_snapshot(current_user, diagram_session_id)


@router.get("/api/kitty/mobile_lane/{diagram_session_id}")
async def kitty_mobile_lane_hint(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    True when this user has an active Kitty WebSocket session on this library scope that
    declared ``client_lane: mobile`` in its ``start`` frame (phone mic), so desktop can
    show the pairing indicator without opening a WebSocket.
    """
    return await kitty_rest_mobile_lane_hint(current_user, diagram_session_id)


@router.post("/api/kitty/cleanup/{diagram_session_id}")
async def cleanup_kitty_session(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    Clean up Kitty WebSocket state when a diagram session ends.

    Called by the session manager on session end or navigation to gallery. Closes WebSocket
    registrations and clears in-memory / Redis-backed state for the diagram scope so the next
    diagram starts fresh.
    """
    # Feature gate
    if not config.FEATURE_KITTY_WS_ENABLED:
        logger.debug("Kitty Agent cleanup skipped: feature disabled")
        return {"success": True, "message": "Kitty Agent feature is disabled"}
    if not await kitty_http_allowed(current_user):
        logger.debug("Kitty Agent cleanup skipped: access denied")
        return {"success": True, "message": "Kitty Agent access denied"}

    scope = normalize_kitty_diagram_session_id(diagram_session_id)
    if scope is None:
        raise HTTPException(status_code=400, detail="Invalid diagram session id")

    hub_http = get_mind_graph_agent_hub()
    try:
        await hub_http.preempt_scope(scope, int(current_user.id), KITTY_CONTROL_REASON_HTTP_CLEANUP)
        async with diagram_session_voice_lock(scope):
            had_local_ws = scope in active_websockets
            cleaned = await cleanup_voice_by_diagram_session(scope)
            if not had_local_ws and not cleaned:
                rc = await kitty_scope_refcount_read(scope)
                if rc is None or rc <= 0:
                    await kitty_scope_force_teardown_redis(scope, int(current_user.id))

        if cleaned:
            logger.info(
                "Voice session and WebSocket connections cleaned up for diagram %s by user %d",
                scope,
                current_user.id,
            )
            message = f"Voice session and WebSocket connections cleaned up for diagram {scope}"
            return {"success": True, "message": message}
        logger.debug("No active voice session found for diagram %s", scope)
        return {"success": True, "message": "No active voice session found"}

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("Cleanup error: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
