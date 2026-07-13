"""
Kitty Agent WebSocket route registration and REST endpoints.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict

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
    kitty_rest_live_context_put,
    kitty_rest_llm_model_push,
    kitty_rest_mobile_active_get,
    kitty_rest_session_get,
    kitty_rest_session_ingress,
    kitty_rest_session_promote,
    kitty_rest_mobile_lane_hint,
    kitty_rest_mobile_open_bootstrap,
    kitty_rest_one_sentence_turns_get,
    kitty_rest_one_sentence_turns_post,
    kitty_rest_one_sentence_sessions_list,
    kitty_rest_one_sentence_session_get,
    kitty_rest_one_sentence_migrate_scope,
    kitty_rest_one_sentence_diagram_activity,
    kitty_rest_selection_push,
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
    Combined desktop poll: ``mobile_active`` plus optional ``action`` pop.

    Desktop SPA uses ``wait_sec=0`` (instant LPOP) after SSE ``desktop_action_pending``
    and as SSE-down fallback. ``wait_sec>0`` BLPOP remains for API compatibility.
    """
    return await kitty_rest_desktop_pairing(current_user, wait_sec=wait_sec)


@router.get("/api/kitty/desktop_wake/stream")
async def kitty_desktop_wake_stream(current_user: User = Depends(get_current_user)):
    """
    SSE stream: instant ``mobile_active`` wake when phone Kitty connects or disconnects.

    Desktop SPA uses EventSource (cookie auth) for ``mobile_active`` and action wake.
    Action delivery: SSE ``desktop_action_pending`` then instant ``desktop_pairing`` LPOP
    (no long-poll BLPOP chain on the SPA).
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


@router.get("/api/kitty/session/{diagram_session_id}")
async def kitty_session_get(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    include_journal: bool = Query(default=False),
):
    """
    Kitty Session Manager snapshot for alignment / ingress_owner / divergence debug.

    Optional ``include_journal=true`` returns recent hot action-journal entries.
    """
    return await kitty_rest_session_get(
        current_user,
        diagram_session_id,
        include_journal=include_journal,
    )


@router.post("/api/kitty/session/{diagram_session_id}/ingress")
async def kitty_session_ingress(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    payload: Dict[str, Any] = Body(default_factory=dict),
):
    """Report non-WS ingress (ui_create) or rejected attempts for Session Manager journal."""
    return await kitty_rest_session_ingress(current_user, diagram_session_id, payload)


@router.post("/api/kitty/session/{diagram_session_id}/promote")
async def kitty_session_promote(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    payload: Dict[str, Any] = Body(default_factory=dict),
):
    """Journal ephemeral → library promote (body: ``from_scope``, optional ``lane``)."""
    return await kitty_rest_session_promote(current_user, diagram_session_id, payload)


@router.put("/api/kitty/llm_model/{diagram_session_id}")
async def kitty_llm_model_push(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    selected_llm_model: str | None = Body(default=None, embed=True),
):
    """
    Desktop canvas LLM selection → paired mobile Kitty WebSocket.

    Body: ``{"selected_llm_model": "qwen"|"deepseek"|"doubao"|null}``.
    """
    return await kitty_rest_llm_model_push(current_user, diagram_session_id, selected_llm_model)


@router.put("/api/kitty/selection/{diagram_session_id}")
async def kitty_selection_push(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    selected_nodes: list[str] | None = Body(default=None, embed=True),
):
    """
    Desktop canvas node selection → paired mobile Kitty WebSocket.

    Body: ``{"selected_nodes": ["node-id", ...]}`` (empty list clears).
    """
    return await kitty_rest_selection_push(
        current_user,
        diagram_session_id,
        selected_nodes if selected_nodes is not None else [],
    )


@router.get("/api/kitty/live_context/{diagram_session_id}")
async def kitty_live_context_snapshot(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    Return the current Redis ``kitty:live_spec`` for this library scope when the caller
    may access that scope.

    Desktop and mobile use this to apply hub-grounded diagram state without relying
    solely on WebSocket frames.
    """
    return await kitty_rest_live_context_snapshot(current_user, diagram_session_id)


@router.put("/api/kitty/live_context/{diagram_session_id}")
async def kitty_live_context_put(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    body: Dict[str, Any] = Body(...),
):
    """
    Desktop canvas publishes diagram snapshot into ``live_spec`` for linked mobile hydrate.

    Body: ``diagram_type``, ``diagram_data``, optional ``selected_nodes``, ``active_panel``,
    ``selected_llm_model``.
    """
    return await kitty_rest_live_context_put(current_user, diagram_session_id, body)


@router.get("/api/kitty/mobile_lane/{diagram_session_id}")
async def kitty_mobile_lane_hint(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    True when this user has an active Kitty WebSocket session on this library scope that
    declared ``client_lane: mobile`` in its ``start`` frame (phone mic), so desktop can
    show the pairing indicator without opening a WebSocket.
    """
    return await kitty_rest_mobile_lane_hint(current_user, diagram_session_id)


@router.get("/api/kitty/one_sentence/diagrams/{diagram_id}/activity")
async def kitty_one_sentence_diagram_activity(
    diagram_id: str,
    current_user: User = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=200),
    actions_only: bool = Query(True),
):
    """Diagram-scoped one-sentence activity tracker (node actions + Bus proof)."""
    return await kitty_rest_one_sentence_diagram_activity(
        current_user,
        diagram_id,
        limit=limit,
        actions_only=actions_only,
    )


@router.get("/api/kitty/one_sentence/{diagram_session_id}/turns")
async def kitty_one_sentence_turns_get(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
):
    """
    Load persisted 一句话生成 chat turns for this diagram scope.

    Used to restore the panel after reopen and for teacher follow-up command analytics.
    """
    return await kitty_rest_one_sentence_turns_get(current_user, diagram_session_id, limit=limit)


@router.post("/api/kitty/one_sentence/{diagram_session_id}/turns")
async def kitty_one_sentence_turns_post(
    diagram_session_id: str,
    current_user: User = Depends(get_current_user),
    body: dict = Body(...),
):
    """
    Append create-phase turns (first auto-complete message) from the one-sentence panel.

    Edit-phase turns are recorded server-side via Kitty WS when ``active_panel`` is
    ``one_sentence``.
    """
    return await kitty_rest_one_sentence_turns_post(current_user, diagram_session_id, body)


@router.get("/api/kitty/one_sentence/sessions")
async def kitty_one_sentence_sessions_list(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=100),
    before_id: str | None = Query(default=None),
):
    """
    List trackable 一句话生成 sessions for the signed-in user (newest first).

    Each session has a stable ``session_id`` plus diagram scope, turn counts, and previews.
    Intended for teacher analytics; frontend UI can adopt later.
    """
    return await kitty_rest_one_sentence_sessions_list(
        current_user,
        limit=limit,
        before_id=before_id,
    )


@router.get("/api/kitty/one_sentence/sessions/{session_id}")
async def kitty_one_sentence_session_get(
    session_id: str,
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=100, ge=1, le=200),
):
    """Return one session summary and its full turn history."""
    return await kitty_rest_one_sentence_session_get(current_user, session_id, limit=limit)


@router.post("/api/kitty/one_sentence/migrate_scope")
async def kitty_one_sentence_migrate_scope(
    body: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Re-key one-sentence chat history when an ephemeral diagram is saved to the library."""
    return await kitty_rest_one_sentence_migrate_scope(current_user, body)


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
