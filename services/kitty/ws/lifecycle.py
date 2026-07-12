"""Kitty WebSocket lifecycle helpers — auth, session start, client loop, cleanup.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import copy
import time
from dataclasses import dataclass
from typing import Any, Optional

from fastapi import WebSocket, WebSocketDisconnect

from config.settings import config
from models.domain.auth import User
from services.agent_hub import get_mind_graph_agent_hub
from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo
from services.infrastructure.monitoring.ws_metrics import (
    record_kitty_ws_idle_timeout_close,
    record_kitty_ws_inbound_reject,
    record_kitty_ws_rate_limit_close,
)
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.desktop.kitty_mobile_active import clear_kitty_mobile_scope
from services.kitty.infra.redis.kitty_session_redis import persist_kitty_live_for_ws
from services.kitty.infra.scope.kitty_scope_access import user_may_access_kitty_scope
from services.kitty.infra.scope.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.session.ops import (
    cleanup_voice_sessions_for_diagram_lane,
    create_voice_session,
    end_voice_session_async,
    get_voice_session,
)
from services.kitty.session.canvas_owner import agent_session_id_for_scope
from services.kitty.session.one_sentence_memory_hydrate import (
    hydrate_one_sentence_session_memory,
)
from services.kitty.session.runtime_state import active_websockets, logger, voice_sessions
from services.kitty.session.voice_lock import (
    diagram_session_voice_lock,
    release_diagram_session_voice_lock_if_idle,
)
from services.kitty.ws.inbound import (
    KittyWsInboundContext,
    build_kitty_inbound_context,
    dispatch_kitty_ws_inbound_message,
)
from utils.auth import user_has_feature_access
from utils.auth_ws import authenticate_websocket_user
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    kitty_ws_idle_timeout_seconds,
    kitty_ws_max_json_depth,
    receive_websocket_json_object_bounded,
)


@dataclass(slots=True)
class KittyWsAuthResult:
    """KittyWsAuthResult helper."""

    current_user: User
    diagram_session_id: str
    hub: Any
    hub_session_id: str


async def authenticate_kitty_websocket(
    websocket: WebSocket,
    diagram_session_id: str,
) -> Optional[KittyWsAuthResult]:
    """Auth, feature gate, accept WS, and open hub session. Returns None when rejected."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        logger.warning("Kitty Agent WebSocket connection rejected: feature disabled")
        await websocket.close(code=4003, reason="Kitty Agent feature is disabled")
        return None

    current_user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or current_user is None:
        logger.warning("WebSocket auth failed: %s", auth_error)
        await websocket.close(code=4001, reason=auth_error or "Authentication failed")
        return None

    if not await user_has_feature_access(current_user, "feature_kitty_agent"):
        logger.warning(
            "Kitty Agent WebSocket connection rejected: access denied user_id=%s",
            getattr(current_user, "id", None),
        )
        await websocket.close(code=4003, reason="Kitty Agent access denied")
        return None

    if await maybe_close_websocket_for_vpn_cn_geo(websocket):
        logger.warning("WebSocket VPN/CN policy closed connection for user_id=%s", current_user.id)
        return None

    diagram_session_id_norm = normalize_kitty_diagram_session_id(diagram_session_id)
    if diagram_session_id_norm is None:
        logger.warning("Kitty WS rejected: invalid diagram_session_id")
        await websocket.close(code=4400, reason="Invalid diagram session id")
        return None

    if not await user_may_access_kitty_scope(int(current_user.id), diagram_session_id_norm):
        logger.warning(
            "Kitty WS rejected: scope access denied user_id=%s scope=%s",
            current_user.id,
            diagram_session_id_norm[:16],
        )
        await websocket.close(code=4403, reason="Diagram scope access denied")
        return None

    await websocket.accept()
    logger.info("WebSocket connection accepted user_id=%s", current_user.id)

    hub = get_mind_graph_agent_hub()
    hub_session_id = await hub.open_session(
        int(current_user.id),
        client_lane=None,
        source_module="kitty_ws",
    )
    await hub.preempt_handshake(diagram_session_id_norm, int(current_user.id))

    return KittyWsAuthResult(
        current_user=current_user,
        diagram_session_id=diagram_session_id_norm,
        hub=hub,
        hub_session_id=hub_session_id,
    )


async def clear_mobile_lane_if_start_aborted(
    user_id: int,
    scope: str,
    client_lane: str | None,
) -> None:
    """Drop user-level mobile_active when mobile start fails after Redis persist."""
    if client_lane == "mobile":
        await clear_kitty_mobile_scope(int(user_id), scope)


async def receive_kitty_start_message(websocket: WebSocket) -> Optional[dict[str, Any]]:
    """Read and validate the initial ``start`` frame."""
    try:
        start_msg = await receive_websocket_json_object_bounded(
            websocket,
            DEFAULT_MAX_WS_TEXT_BYTES,
            kitty_ws_max_json_depth(),
        )
    except WebSocketDisconnect:
        return None
    except ValueError:
        record_kitty_ws_inbound_reject()
        await websocket.close(code=4409, reason="Invalid start frame")
        return None

    if start_msg.get("type") != "start":
        logger.warning("Invalid start message type: %s", start_msg.get("type"))
        await safe_websocket_send(websocket, {"type": "error", "error": "Expected start message"})
        await websocket.close()
        return None
    return start_msg


async def prepare_diagram_voice_lock(
    websocket: WebSocket,
    diagram_session_id: str,
    agent_session_id: str,
    *,
    client_lane: str | None = None,
) -> None:
    """
    Register this socket for the diagram scope.

    Mobile and desktop canvas-owner may coexist on the same scope. Same-lane
    reconnects still replace the prior peer (e.g. second desktop tab).
    """
    is_mobile = client_lane == "mobile"
    lane_agent_id = agent_session_id_for_scope(diagram_session_id, client_lane=client_lane)
    del agent_session_id  # callers may still pass legacy id; use lane-suffixed

    async with diagram_session_voice_lock(diagram_session_id):
        existing_ws_list = list(active_websockets.get(diagram_session_id, []))
        peers_to_close: list[WebSocket] = []
        for existing_ws in existing_ws_list:
            if existing_ws is websocket:
                continue
            peer_is_mobile = False
            for _sid, sess in list(voice_sessions.items()):
                if not isinstance(sess, dict):
                    continue
                if sess.get("_client_websocket") is existing_ws:
                    peer_is_mobile = sess.get("_kitty_client_lane") == "mobile"
                    break
            if peer_is_mobile == is_mobile:
                peers_to_close.append(existing_ws)

        if peers_to_close:
            logger.debug(
                "Closing %d same-lane WebSocket connection(s) for diagram %s lane=%s",
                len(peers_to_close),
                diagram_session_id,
                "mobile" if is_mobile else "desktop",
            )
            for existing_ws in peers_to_close:
                try:
                    await existing_ws.close(code=1001, reason="Diagram session ended")
                except (RuntimeError, ConnectionError, AttributeError) as exc:
                    logger.debug("Error closing existing WebSocket: %s", exc)
                try:
                    if diagram_session_id in active_websockets:
                        active_websockets[diagram_session_id].remove(existing_ws)
                except ValueError:
                    pass

        existing_cleaned = await cleanup_voice_sessions_for_diagram_lane(
            diagram_session_id,
            client_lane=client_lane,
        )
        if existing_cleaned:
            logger.debug(
                "Cleaned up same-lane voice session for diagram %s lane=%s",
                diagram_session_id,
                "mobile" if is_mobile else "desktop",
            )

        if kitty_agent_manager.get(lane_agent_id) is not None:
            logger.debug("Removing existing agent %s", lane_agent_id)
            kitty_agent_manager.remove(lane_agent_id)

        if diagram_session_id not in active_websockets:
            active_websockets[diagram_session_id] = []
        if websocket not in active_websockets[diagram_session_id]:
            active_websockets[diagram_session_id].append(websocket)
        logger.debug(
            "Registered WebSocket for diagram %s (total: %d)",
            diagram_session_id,
            len(active_websockets[diagram_session_id]),
        )


@dataclass(slots=True)
class KittySessionStartResult:
    """KittySessionStartResult helper."""

    voice_session_id: str
    agent_session_id: str
    omni_generator: Any | None
    start_client_lane: str | None
    inbound_ctx: KittyWsInboundContext


async def start_kitty_session(
    *,
    websocket: WebSocket,
    auth: KittyWsAuthResult,
    start_msg: dict[str, Any],
) -> Optional[KittySessionStartResult]:
    """Create voice session, agent mirror, Omni generator, and hub registration."""
    user_id = str(auth.current_user.id)
    diagram_session_id = auth.diagram_session_id
    hub = auth.hub
    hub_session_id = auth.hub_session_id

    logger.debug("Starting voice conversation for user %s", user_id)

    initial_context_in = start_msg.get("context", {}) or {}
    raw_start_lane = start_msg.get("client_lane")
    start_client_lane: str | None = "mobile" if raw_start_lane == "mobile" else None
    agent_session_id = agent_session_id_for_scope(
        diagram_session_id, client_lane=start_client_lane
    )
    start_diagram_type = start_msg.get("diagram_type") or "circle_map"
    start_active_panel = start_msg.get("active_panel", "none")
    start_resolved = await hub.prepare_kitty_start_context(
        user_id=int(auth.current_user.id),
        hub_session_id=hub_session_id,
        diagram_scope=diagram_session_id,
        start_context=initial_context_in,
        start_diagram_type=str(start_diagram_type),
        start_active_panel=str(start_active_panel),
        start_client_lane=start_client_lane,
        source_module="kitty_ws",
    )
    merged_ctx = start_resolved["context"]
    start_diagram_type = str(start_resolved["diagram_type"])
    start_active_panel = str(start_resolved["active_panel"])

    voice_session_id = create_voice_session(
        user_id=user_id,
        diagram_session_id=diagram_session_id,
        diagram_type=start_diagram_type,
        active_panel=start_active_panel,
    )

    voice_sessions[voice_session_id]["context"] = copy.deepcopy(merged_ctx)
    voice_sessions[voice_session_id]["_kitty_client_lane"] = start_client_lane
    voice_sessions[voice_session_id]["_kitty_canvas_owner"] = start_client_lane != "mobile"
    voice_sessions[voice_session_id]["_client_websocket"] = websocket
    # Explicit start flag (desktop one-sentence / canvas owner agent).
    if start_msg.get("canvas_owner") is True:
        voice_sessions[voice_session_id]["_kitty_canvas_owner"] = True
    # Text-first Kitty: commands always use client_mode text (no Omni duplex).
    start_client_mode = "text"
    voice_sessions[voice_session_id]["_kitty_client_mode"] = start_client_mode
    voice_sessions[voice_session_id]["_hub_session_id"] = hub_session_id
    voice_sessions[voice_session_id]["_hub_scope_revision"] = 0
    await hub.set_kitty_runtime(
        hub_session_id,
        voice_session_id=voice_session_id,
        agent_session_id=agent_session_id,
        connected=False,
    )

    initial_context = merged_ctx
    agent = kitty_agent_manager.get_or_create(agent_session_id)
    agent.clear_history()
    diagram_data = dict(initial_context.get("diagram_data", {}))
    diagram_data["diagram_type"] = start_diagram_type
    agent.update_diagram_state(diagram_data)
    agent.update_panel_state(start_active_panel, initial_context.get("panels", {}))

    start_ts = await persist_kitty_live_for_ws(
        diagram_session_id,
        auth.current_user.id,
        merged_ctx,
        start_diagram_type,
        start_active_panel,
        client_lane=start_client_lane,
        preserve_mobile_lane=start_client_lane == "mobile",
    )
    # Desktop canvas_owner coexists with mobile ingress — do not clear mobile_active.

    session = get_voice_session(voice_session_id)
    if not session:
        await clear_mobile_lane_if_start_aborted(
            int(auth.current_user.id),
            diagram_session_id,
            start_client_lane,
        )
        await websocket.close(code=1008, reason="Session not found")
        return None
    if start_ts is not None:
        session["_kitty_redis_seen_ts"] = start_ts

    logger.debug(
        "Text-first Kitty session %s — skipping Omni realtime",
        voice_session_id,
    )
    omni_generator = None

    refcount_ok = await hub.register_kitty_connection(diagram_session_id, int(auth.current_user.id))
    if not getattr(config, "DEBUG", True) and not refcount_ok:
        await clear_mobile_lane_if_start_aborted(
            int(auth.current_user.id),
            diagram_session_id,
            start_client_lane,
        )
        await websocket.close(code=1013, reason="Kitty session coordination unavailable")
        return None

    await hub.set_kitty_runtime(
        hub_session_id,
        voice_session_id=voice_session_id,
        agent_session_id=agent_session_id,
        connected=True,
    )

    await safe_websocket_send(websocket, {"type": "connected", "session_id": voice_session_id})

    if start_active_panel == "one_sentence":
        await hydrate_one_sentence_session_memory(
            voice_session_id=voice_session_id,
            user_id=int(auth.current_user.id),
            diagram_scope=diagram_session_id,
        )

    inbound_ctx = build_kitty_inbound_context(
        websocket=websocket,
        current_user=auth.current_user,
        diagram_session_id=diagram_session_id,
        voice_session_id=voice_session_id,
        hub_session_id=hub_session_id,
        hub=hub,
        agent_session_id=agent_session_id,
        user_id=user_id,
    )

    return KittySessionStartResult(
        voice_session_id=voice_session_id,
        agent_session_id=agent_session_id,
        omni_generator=omni_generator,
        start_client_lane=start_client_lane,
        inbound_ctx=inbound_ctx,
    )


async def run_kitty_client_message_loop(
    *,
    websocket: WebSocket,
    inbound_ctx: KittyWsInboundContext,
    voice_session_id: str,
    user_id: str,
    last_client_inbound: list[float],
) -> None:
    """Handle inbound JSON from the Kitty client until disconnect or stop."""
    rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND * 5)
    try:
        while True:
            if not rate_limiter.allow():
                logger.warning(
                    "Kitty WS inbound rate limit exceeded user_id=%s voice_session=%s",
                    user_id,
                    voice_session_id,
                )
                record_kitty_ws_rate_limit_close()
                await websocket.close(code=1008, reason="Rate limit exceeded")
                return

            try:
                message = await receive_websocket_json_object_bounded(
                    websocket,
                    DEFAULT_MAX_WS_TEXT_BYTES,
                    kitty_ws_max_json_depth(),
                )
            except WebSocketDisconnect:
                break
            except ValueError:
                record_kitty_ws_inbound_reject()
                last_client_inbound[0] = time.monotonic()
                await safe_websocket_send(
                    websocket,
                    {"type": "error", "error": "Invalid or oversized message"},
                )
                continue

            last_client_inbound[0] = time.monotonic()
            if message.get("type") == "stop":
                break
            flow = await dispatch_kitty_ws_inbound_message(inbound_ctx, message)
            if flow == "stop":
                break

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", voice_session_id)
    except (RuntimeError, ConnectionError, AttributeError) as exc:
        logger.error("Client message error: %s", exc, exc_info=True)


async def run_kitty_idle_watchdog(
    *,
    websocket: WebSocket,
    hub: Any,
    diagram_session_id: str,
    current_user: User,
    voice_session_id: str,
    last_client_inbound: list[float],
) -> None:
    """Close the WS when no inbound client message arrives within the idle window."""
    idle_timeout_sec = kitty_ws_idle_timeout_seconds()
    if idle_timeout_sec is None:
        return
    check_interval = max(5.0, min(30.0, float(idle_timeout_sec) / 4.0))
    while True:
        await asyncio.sleep(check_interval)
        if time.monotonic() - last_client_inbound[0] >= idle_timeout_sec:
            logger.info(
                "Kitty WS idle timeout (no inbound client message for %.0fs) "
                "diagram_session_id=%s user_id=%s voice_session_id=%s",
                idle_timeout_sec,
                diagram_session_id,
                current_user.id,
                voice_session_id,
            )
            record_kitty_ws_idle_timeout_close()
            await hub.preempt_idle_timeout(diagram_session_id, int(current_user.id))
            try:
                await websocket.close(code=4408, reason="Idle timeout")
            except (RuntimeError, ConnectionError, AttributeError) as exc:
                logger.debug("Kitty idle timeout websocket close: %s", exc)
            return


async def cleanup_kitty_websocket_session(
    *,
    websocket: WebSocket,
    diagram_session_id: str,
    hub: Any,
    hub_session_id: str,
    voice_session_id: str | None,
    kitty_hub_registered: bool,
    current_user: User,
) -> None:
    """Unregister diagram socket, end voice session, and close hub scope."""
    async with diagram_session_voice_lock(diagram_session_id):
        if diagram_session_id in active_websockets:
            try:
                active_websockets[diagram_session_id].remove(websocket)
                if not active_websockets[diagram_session_id]:
                    del active_websockets[diagram_session_id]
            except ValueError:
                pass

        if voice_session_id:
            await hub.set_kitty_runtime(
                hub_session_id,
                voice_session_id=voice_session_id,
                agent_session_id=None,
                connected=False,
            )
            await end_voice_session_async(voice_session_id, reason="websocket_closed")

        if kitty_hub_registered:
            await hub.unregister_kitty_connection(diagram_session_id, int(current_user.id))
        release_diagram_session_voice_lock_if_idle(diagram_session_id)
    await hub.close_session(hub_session_id, reason="websocket_closed")
