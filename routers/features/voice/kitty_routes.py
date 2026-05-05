"""Kitty Agent WebSocket route and REST cleanup endpoint."""

import asyncio
import base64
import binascii
import copy
import os
import random
import time

from fastapi import Body, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect

from config.settings import config
from models.domain.auth import User
from services.features.voice_agent import kitty_agent_manager
from services.features.websocket_llm_middleware import omni_middleware

from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo

_close_ws_if_vpn_cn_geo = maybe_close_websocket_for_vpn_cn_geo
from utils.auth import get_current_user
from utils.auth_ws import authenticate_websocket_user
from utils.ws_limits import (
    DEFAULT_MAX_WS_MESSAGES_PER_SECOND,
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    kitty_ws_idle_timeout_seconds,
    kitty_ws_max_json_depth,
    receive_websocket_json_object_bounded,
)
from utils.ws_session_registry import _registry as _ws_registry
from services.infrastructure.monitoring.ws_metrics import (
    redis_increment_active_total,
    record_kitty_ws_idle_timeout_close,
    record_kitty_ws_inbound_reject,
    record_kitty_ws_rate_limit_close,
)

from services.agent_hub import (
    build_desktop_pairing_snapshot,
    get_mind_graph_agent_hub,
)
from services.kitty.kitty_control_fanout import KITTY_CONTROL_REASON_HTTP_CLEANUP
from services.kitty.kitty_context_hydrate import merge_voice_context_with_library
from services.kitty.kitty_desktop_focus import (
    get_kitty_desktop_focus_diagram,
    set_kitty_desktop_focus_diagram,
)
from services.kitty.kitty_ws_scope import normalize_kitty_diagram_session_id
from services.kitty.kitty_scope_refcount import (
    kitty_scope_force_teardown_redis,
    kitty_scope_refcount_read,
)
from services.kitty.kitty_session_redis import (
    kitty_mobile_indicator_armed_for_user,
    persist_kitty_live_for_ws,
)

from routers.features.voice.kitty_library_context_refresh import (
    throttled_refresh_voice_context_from_library,
)

from routers.features.voice.commands import process_voice_command
from routers.features.voice.paragraph import process_paragraph_with_qwen_plus
from routers.features.voice.messaging import (
    build_greeting_message,
    build_voice_instructions,
    resolve_voice_interaction_language,
    safe_websocket_send,
)
from routers.features.voice.diagram_session_voice_lock import diagram_session_voice_lock
from routers.features.voice.session_ops import (
    cleanup_voice_by_diagram_session,
    create_voice_session,
    end_voice_session_async,
    get_agent_session_id,
    get_session_omni_client,
    get_voice_session,
    update_panel_context,
)
from routers.features.voice.state import (
    active_websockets,
    logger,
    router,
    voice_sessions,
)

# Inbound guards (DoS / memory). Audio = one PCM worklet frame; image ~ frontend 500 KiB cap.
_KITTY_WS_MAX_TEXT_CHARS = max(1024, int(os.getenv("KITTY_WS_MAX_TEXT_CHARS", "12000")))
_KITTY_WS_MAX_AUDIO_B64_CHARS = max(4096, int(os.getenv("KITTY_WS_MAX_AUDIO_B64_CHARS", "65536")))
_KITTY_WS_IMAGE_B64_MAX_CHARS = max(50_000, int(os.getenv("KITTY_WS_IMAGE_B64_MAX_CHARS", "900000")))
_KITTY_WS_IMAGE_RAW_MAX_BYTES = max(50_000, int(os.getenv("KITTY_WS_IMAGE_RAW_MAX_BYTES", "524288")))


def _pcm16_silence_base64(duration_ms: int = 200, sample_rate: int = 24000) -> str:
    """Short silence chunk so image append satisfies prior-audio requirement (Omni realtime)."""
    samples = max(1, int(sample_rate * duration_ms / 1000))
    return base64.b64encode(bytes(samples * 2)).decode("ascii")


async def kitty_realtime_websocket(websocket: WebSocket, diagram_session_id: str):
    """
    WebSocket endpoint for real-time voice conversation.

    Protocol:
    Client -> Server:
    - {"type": "start", "diagram_type": str, "active_panel": str, "context": {...}}
    - {"type": "audio", "data": str}  # base64 PCM audio
    - {"type": "context_update", "active_panel": str, "context": {...}}
    - {"type": "stop"}

    Server -> Client:
    - {"type": "connected", "session_id": str}
    - {"type": "transcription", "text": str}
    - {"type": "text_chunk", "text": str}
    - {"type": "audio_chunk", "audio": str}  # base64
    - {"type": "speech_started", "audio_start_ms": int}
    - {"type": "speech_stopped", "audio_end_ms": int}
    - {"type": "response_done"}
    - {"type": "action", "action": str, "params": {...}}
    - {"type": "error", "error": str}
    """
    # ── Auth before accept ───────────────────────────────────────────────────
    if not config.FEATURE_KITTY_WS_ENABLED:
        logger.warning("Kitty Agent WebSocket connection rejected: feature disabled")
        await websocket.close(code=4003, reason="Kitty Agent feature is disabled")
        return

    current_user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or current_user is None:
        logger.warning("WebSocket auth failed: %s", auth_error)
        await websocket.close(code=4001, reason=auth_error or "Authentication failed")
        return

    if await _close_ws_if_vpn_cn_geo(websocket):
        logger.warning("WebSocket VPN/CN policy closed connection for user_id=%s", current_user.id)
        return

    await websocket.accept()
    logger.info("WebSocket connection accepted user_id=%s", current_user.id)

    diagram_session_id_norm = normalize_kitty_diagram_session_id(diagram_session_id)
    if diagram_session_id_norm is None:
        logger.warning("Kitty WS rejected: invalid diagram_session_id")
        await websocket.close(code=4400, reason="Invalid diagram session id")
        return

    diagram_session_id = diagram_session_id_norm
    hub = get_mind_graph_agent_hub()
    kitty_hub_registered = False
    hub_session_id = await hub.open_session(
        int(current_user.id),
        client_lane=None,
        source_module="kitty_ws",
    )

    await hub.preempt_handshake(diagram_session_id, int(current_user.id))

    # Rate limiter — audio packets arrive frequently; use a generous window.
    # The limit prevents runaway clients, not normal audio streaming.
    _rate_limiter = WebsocketMessageRateLimiter(DEFAULT_MAX_WS_MESSAGES_PER_SECOND * 5)

    voice_session_id = None
    omni_generator = None
    user_id = str(current_user.id)

    # Register in central WS registry so the session is visible to close_all / metrics.
    # register() bumps the per-endpoint counter; redis_increment_active_total
    # updates the cross-worker gauge.
    _voice_ws_session = await _ws_registry.register(
        current_user.id,
        "voice",
        websocket,
        diagram_session_id=diagram_session_id,
    )
    await redis_increment_active_total(1)
    _ws_session_started = time.monotonic()
    logger.info(
        "[WSSession] OPEN  session=%s endpoint=voice user_id=%s remote=%s",
        _voice_ws_session.session_id,
        current_user.id,
        _voice_ws_session.remote_addr,
    )

    try:
        # Wait for start message first (avoid holding diagram lock during slow clients).
        try:
            start_msg = await receive_websocket_json_object_bounded(
                websocket,
                DEFAULT_MAX_WS_TEXT_BYTES,
                kitty_ws_max_json_depth(),
            )
        except WebSocketDisconnect:
            return
        except ValueError:
            record_kitty_ws_inbound_reject()
            await websocket.close(code=4409, reason="Invalid start frame")
            return

        if start_msg.get("type") != "start":
            logger.warning("Invalid start message type: %s", start_msg.get("type"))
            await safe_websocket_send(websocket, {"type": "error", "error": "Expected start message"})
            await websocket.close()
            return

        logger.debug("Starting voice conversation for user %s", user_id)

        agent_session_id = f"diagram_{diagram_session_id}"

        async with diagram_session_voice_lock(diagram_session_id):
            if diagram_session_id in active_websockets:
                existing_ws_list = list(active_websockets[diagram_session_id])
                logger.debug(
                    "Closing %d existing WebSocket connection(s) for diagram %s",
                    len(existing_ws_list),
                    diagram_session_id,
                )
                for existing_ws in existing_ws_list:
                    if existing_ws is websocket:
                        continue
                    try:
                        await existing_ws.close(code=1001, reason="Diagram session ended")
                    except (RuntimeError, ConnectionError, AttributeError) as exc:
                        logger.debug("Error closing existing WebSocket: %s", exc)
                active_websockets[diagram_session_id] = []

            existing_cleaned = await cleanup_voice_by_diagram_session(diagram_session_id)
            if existing_cleaned:
                logger.debug("Cleaned up existing voice session for diagram %s", diagram_session_id)

            if agent_session_id in kitty_agent_manager._agents:  # pylint: disable=protected-access
                logger.debug("Removing existing agent for diagram session %s", diagram_session_id)
                kitty_agent_manager.remove(agent_session_id)

            if diagram_session_id not in active_websockets:
                active_websockets[diagram_session_id] = []
            active_websockets[diagram_session_id].append(websocket)
            logger.debug(
                "Registered WebSocket for diagram %s (total: %d)",
                diagram_session_id,
                len(active_websockets[diagram_session_id]),
            )

        # Create new voice session (with fresh conversation_history: [])
        initial_context_in = start_msg.get("context", {}) or {}
        raw_start_lane = start_msg.get("client_lane")
        start_client_lane: str | None = "mobile" if raw_start_lane == "mobile" else None
        start_diagram_type = start_msg.get("diagram_type") or "circle_map"
        start_active_panel = start_msg.get("active_panel", "none")
        start_resolved = await hub.prepare_kitty_start_context(
            user_id=int(current_user.id),
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

        logger.debug(
            "Session created: %s, diagram_type=%s, panel=%s",
            voice_session_id,
            start_diagram_type,
            start_active_panel,
        )
        logger.debug("Agent session ID: %s (scoped to diagram_session_id)", agent_session_id)

        # Store initial context (hydrated / merged with library when applicable)
        voice_sessions[voice_session_id]["context"] = copy.deepcopy(merged_ctx)
        voice_sessions[voice_session_id]["_kitty_client_lane"] = start_client_lane
        voice_sessions[voice_session_id]["_hub_session_id"] = hub_session_id
        voice_sessions[voice_session_id]["_hub_scope_revision"] = 0
        await hub.set_kitty_runtime(
            hub_session_id,
            voice_session_id=voice_session_id,
            agent_session_id=agent_session_id,
            connected=False,
        )

        # Initialize persistent LangGraph agent with diagram state
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        # This ensures the agent is scoped to the diagram session, not the WebSocket connection
        # If agent already exists (shouldn't happen after cleanup), clear its history
        initial_context = merged_ctx
        agent = kitty_agent_manager.get_or_create(agent_session_id)

        # CRITICAL: Clear agent's conversation history when starting a new diagram session
        # This ensures no cross-contamination between diagram sessions
        agent.clear_history()

        # Sync initial diagram state to agent
        diagram_data = dict(initial_context.get("diagram_data", {}))
        diagram_data["diagram_type"] = start_diagram_type
        agent.update_diagram_state(diagram_data)
        agent.update_panel_state(start_active_panel, initial_context.get("panels", {}))

        logger.debug(
            "KittyAgent initialized with %d nodes",
            len(diagram_data.get("children", [])),
        )

        # Build instructions with FULL context including diagram_data
        context = {
            "diagram_type": start_diagram_type,
            "active_panel": start_active_panel,
            "conversation_history": [],
            "selected_nodes": initial_context.get("selected_nodes", []),
            "diagram_data": initial_context.get("diagram_data", {}),  # Include node content!
            "diagram_library_id": initial_context.get("diagram_library_id"),
            "diagram_display_title": initial_context.get("diagram_display_title"),
        }
        instructions = build_voice_instructions(context)

        children_count = len(context.get("diagram_data", {}).get("children", []))
        logger.debug("Initial instructions built with %d nodes", children_count)

        logger.debug("Built instructions for context: %d chars", len(instructions))

        start_ts = await persist_kitty_live_for_ws(
            diagram_session_id,
            current_user.id,
            merged_ctx,
            start_diagram_type,
            start_active_panel,
            client_lane=start_client_lane,
        )

        # CRITICAL: Use session-specific OmniClient (not singleton)
        # Each voice session has its own OmniClient instance to support concurrent users
        session = get_voice_session(voice_session_id)
        if not session:
            logger.error("Voice session %s not found", voice_session_id)
            await websocket.close(code=1008, reason="Session not found")
            return
        if start_ts is not None:
            session["_kitty_redis_seen_ts"] = start_ts

        omni_client = session.get("omni_client")
        if not omni_client:
            logger.error("OmniClient not found for session %s", voice_session_id)
            await websocket.close(code=1008, reason="OmniClient not initialized")
            return

        # Start Omni conversation using session-specific client WITH middleware
        # This provides rate limiting, error handling, token tracking, and performance tracking
        omni_generator = omni_middleware.wrap_start_conversation(
            omni_client=omni_client,
            instructions=instructions,
            user_id=int(user_id) if user_id else None,
            organization_id=(
                getattr(current_user, "organization_id", None) if current_user and hasattr(current_user, "id") else None
            ),
            session_id=voice_session_id,
            request_type="voice_omni",
            endpoint_path="/ws/kitty",
        )

        # Store generator in session for cleanup
        voice_sessions[voice_session_id]["omni_generator"] = omni_generator

        await hub.register_kitty_connection(diagram_session_id, int(current_user.id))
        kitty_hub_registered = True
        await hub.set_kitty_runtime(
            hub_session_id,
            voice_session_id=voice_session_id,
            agent_session_id=agent_session_id,
            connected=True,
        )

        # Send connected confirmation
        await safe_websocket_send(websocket, {"type": "connected", "session_id": voice_session_id})

        logger.debug("Voice session %s connected", voice_session_id)

        # Wait for SDK to initialize conversation (check via async iteration start)
        # The first event will confirm conversation is ready
        logger.debug("Waiting for Omni session to initialize...")

        last_client_inbound: list[float] = [time.monotonic()]
        idle_timeout_sec = kitty_ws_idle_timeout_seconds()

        # Handle messages concurrently
        async def handle_client_messages():
            """Handle messages from client"""
            try:
                while True:
                    if not _rate_limiter.allow():
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
                    msg_type = message.get("type")

                    if msg_type == "audio":
                        # Forward audio to Omni
                        audio_data = message.get("data")
                        if audio_data:
                            if (
                                not isinstance(audio_data, str)
                                or len(audio_data) > _KITTY_WS_MAX_AUDIO_B64_CHARS
                            ):
                                await safe_websocket_send(
                                    websocket,
                                    {"type": "error", "error": "Audio frame too large"},
                                )
                                continue
                            # Log every 20th audio packet to avoid spam
                            if random.random() < 0.05:
                                logger.debug(
                                    "Forwarding audio to Omni: %d bytes (base64)",
                                    len(audio_data),
                                )
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                await throttled_refresh_voice_context_from_library(
                                    user_id=int(current_user.id),
                                    voice_session_id=voice_session_id,
                                    diagram_session_id=diagram_session_id,
                                )
                                await omni_client.send_audio(audio_data)
                            else:
                                logger.warning(
                                    "Cannot send audio: OmniClient not found for session %s",
                                    voice_session_id,
                                )

                    elif msg_type == "text":
                        # Handle text message from user
                        text = message.get("text", "").strip()
                        if len(text) > _KITTY_WS_MAX_TEXT_CHARS:
                            await safe_websocket_send(
                                websocket,
                                {"type": "error", "error": "Text too long"},
                            )
                            continue
                        if text:
                            logger.debug("Received text message (%d chars)", len(text))

                            # Store in conversation history
                            voice_sessions[voice_session_id]["conversation_history"].append(
                                {"role": "user", "content": text}
                            )

                            # CRITICAL: Process text message through unified command processing
                            # Uses Qwen Turbo (classification model) for intention checking via agent.process_command()
                            # Pass is_text_message=True for lower confidence threshold (0.5 vs 0.7)
                            # This allows conversational requests like "can you change..." to be executed
                            session_context = voice_sessions[voice_session_id].get("context", {})

                            # Process command through unified function (handles UI actions AND diagram updates)
                            # LLM (Qwen Turbo) parses the command and returns structured action JSON
                            command_executed = await process_voice_command(
                                websocket,
                                voice_session_id,
                                text,
                                session_context,
                                is_text_message=True,
                            )

                            # If command was executed (UI actions or diagram updates), we're done
                            if command_executed:
                                continue

                            # Otherwise, send to Omni for conversational response
                            try:
                                logger.debug("Text message is conversational, sending to Omni")
                                omni_client = get_session_omni_client(voice_session_id)
                                if omni_client:
                                    await omni_client.send_text_message(text)
                                else:
                                    logger.warning(
                                        "Cannot send text: OmniClient not found for session %s",
                                        voice_session_id,
                                    )
                                    await safe_websocket_send(
                                        websocket,
                                        {
                                            "type": "error",
                                            "error": "Voice session not initialized",
                                        },
                                    )
                            except (
                                RuntimeError,
                                ConnectionError,
                                AttributeError,
                            ) as text_error:
                                logger.error(
                                    "Text message processing error: %s",
                                    text_error,
                                    exc_info=True,
                                )
                                await safe_websocket_send(
                                    websocket,
                                    {"type": "error", "error": str(text_error)},
                                )

                    elif msg_type == "get_desktop_session_snapshot":
                        lane = voice_sessions[voice_session_id].get("_kitty_client_lane")
                        snapshot_payload = await build_desktop_pairing_snapshot(
                            int(current_user.id),
                            diagram_session_id,
                            client_lane=lane if isinstance(lane, str) else None,
                        )
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "desktop_session_snapshot",
                                "snapshot": snapshot_payload,
                            },
                        )

                    elif msg_type == "context_update":
                        # Update context and instructions with full diagram data
                        new_context_in = message.get("context", {}) or {}
                        cur_panel = voice_sessions[voice_session_id].get("active_panel", "none")
                        active_panel = (
                            message.get("active_panel")
                            or new_context_in.get("active_panel")
                            or cur_panel
                            or "none"
                        )
                        session_dt = (
                            voice_sessions[voice_session_id].get("diagram_type")
                            or new_context_in.get("diagram_type")
                            or "circle_map"
                        )
                        merged_ctx, res_dt, res_panel = await merge_voice_context_with_library(
                            current_user.id,
                            new_context_in,
                            diagram_type=session_dt,
                            active_panel=active_panel,
                        )
                        new_diagram_type = res_dt

                        old_diagram_type = voice_sessions[voice_session_id].get("diagram_type")
                        voice_sessions[voice_session_id]["diagram_type"] = new_diagram_type
                        if old_diagram_type != new_diagram_type:
                            logger.info(
                                "VOIC | Diagram type updated: %s -> %s for session %s",
                                old_diagram_type,
                                new_diagram_type,
                                voice_session_id,
                            )

                        update_panel_context(voice_session_id, res_panel)
                        voice_sessions[voice_session_id]["context"] = copy.deepcopy(merged_ctx)
                        voice_sessions[voice_session_id]["context"]["diagram_type"] = new_diagram_type

                        agent_session_id_mu = get_agent_session_id(voice_session_id)
                        agent = kitty_agent_manager.get_or_create(agent_session_id_mu)
                        diagram_data = dict(merged_ctx.get("diagram_data", {}))
                        diagram_data["diagram_type"] = new_diagram_type
                        agent.update_diagram_state(diagram_data)
                        agent.update_panel_state(res_panel, merged_ctx.get("panels", {}))

                        updated_context = {
                            "diagram_type": new_diagram_type,
                            "active_panel": res_panel,
                            "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                            "selected_nodes": merged_ctx.get("selected_nodes", []),
                            "diagram_data": diagram_data,
                            "diagram_library_id": merged_ctx.get("diagram_library_id"),
                            "diagram_display_title": merged_ctx.get("diagram_display_title"),
                        }
                        new_instructions = build_voice_instructions(updated_context)
                        try:
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                await omni_client.update_instructions(new_instructions)
                            else:
                                logger.debug(
                                    "Cannot update instructions: OmniClient not found for session %s",
                                    voice_session_id,
                                )
                        except (RuntimeError, ConnectionError, AttributeError) as e:
                            logger.debug("Error updating Omni instructions: %s", e)

                        hub_rev_raw = voice_sessions[voice_session_id].get("_hub_scope_revision")
                        hub_rev = hub_rev_raw if isinstance(hub_rev_raw, int) else None
                        idempotency_key_raw = message.get("idempotency_key")
                        idempotency_key = (
                            str(idempotency_key_raw).strip()
                            if isinstance(idempotency_key_raw, str) and idempotency_key_raw.strip()
                            else None
                        )
                        try:
                            mutation_out = await hub.apply_diagram_spec_mutation(
                                hub_session_id=hub_session_id,
                                diagram_scope=diagram_session_id,
                                mutation_cmd={
                                    "op": "patch_context",
                                    "context": merged_ctx,
                                    "diagram_type": new_diagram_type,
                                    "active_panel": res_panel,
                                },
                                source_module="kitty_ws_context_update",
                                expected_revision=hub_rev,
                                idempotency_key=idempotency_key,
                            )
                        except ValueError as mut_err:
                            logger.warning("Hub mutation rejected for %s: %s", voice_session_id, mut_err)
                            await safe_websocket_send(
                                websocket,
                                {"type": "error", "error": f"Context mutation rejected: {mut_err}"},
                            )
                            continue
                        new_rev = mutation_out.get("revision")
                        if isinstance(new_rev, int):
                            voice_sessions[voice_session_id]["_hub_scope_revision"] = new_rev

                        children_count = len(diagram_data.get("children", []))
                        logger.debug(
                            "Context updated for %s with %d nodes",
                            voice_session_id,
                            children_count,
                        )

                    elif msg_type == "stop":
                        # User wants to stop the conversation
                        break

                    elif msg_type == "cancel_response":
                        # Cancel ongoing Omni response
                        logger.debug("User requested to cancel response")
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.cancel_response()
                            await safe_websocket_send(websocket, {"type": "response_cancelled"})
                        else:
                            logger.warning(
                                "Cannot cancel response: OmniClient not found for session %s",
                                voice_session_id,
                            )

                    elif msg_type == "clear_audio_buffer":
                        # Clear audio buffer (cancel pending audio input)
                        logger.debug("User requested to clear audio buffer")
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.clear_audio_buffer()
                            await safe_websocket_send(websocket, {"type": "audio_buffer_cleared"})
                        else:
                            logger.warning(
                                "Cannot clear audio buffer: OmniClient not found for session %s",
                                voice_session_id,
                            )

                    elif msg_type == "commit_audio_buffer":
                        # Explicitly commit audio buffer
                        logger.debug("User requested to commit audio buffer")
                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.commit_audio_buffer()
                            await safe_websocket_send(websocket, {"type": "audio_buffer_committed"})
                        else:
                            logger.warning(
                                "Cannot commit audio buffer: OmniClient not found for session %s",
                                voice_session_id,
                            )

                    elif msg_type == "append_image":
                        # Append image data (for multimodal support)
                        logger.debug("User requested to append image")
                        image_data = message.get("data")  # Base64 encoded image
                        image_format = message.get("format", "jpeg")
                        if image_data:
                            if (
                                not isinstance(image_data, str)
                                or len(image_data) > _KITTY_WS_IMAGE_B64_MAX_CHARS
                            ):
                                await safe_websocket_send(
                                    websocket,
                                    {"type": "error", "error": "Image payload too large"},
                                )
                                continue
                            try:
                                image_bytes = base64.b64decode(image_data, validate=True)
                            except (binascii.Error, TypeError, ValueError):
                                await safe_websocket_send(
                                    websocket,
                                    {"type": "error", "error": "Invalid image data"},
                                )
                                continue
                            if len(image_bytes) > _KITTY_WS_IMAGE_RAW_MAX_BYTES:
                                await safe_websocket_send(
                                    websocket,
                                    {"type": "error", "error": "Image too large"},
                                )
                                continue
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                try:
                                    await omni_client.append_audio(_pcm16_silence_base64(200, 24000))
                                except (
                                    RuntimeError,
                                    ConnectionError,
                                    AttributeError,
                                    ValueError,
                                ) as pre_audio_err:
                                    logger.debug("Silence preamble before image: %s", pre_audio_err)
                                await omni_client.append_image(image_bytes, image_format)
                                try:
                                    await omni_client.commit_audio_buffer()
                                except (RuntimeError, ConnectionError, AttributeError) as commit_err:
                                    logger.debug("commit_audio_buffer after image: %s", commit_err)
                                try:
                                    await omni_client.create_response(
                                        instructions=(
                                            "请根据用户上传的图片，用简短中文概括其中的文字或可视要点，"
                                            "便于更新思维导图；若无法识别请说明。"
                                        ),
                                    )
                                except (RuntimeError, ConnectionError, AttributeError) as resp_err:
                                    logger.debug("create_response after image: %s", resp_err)
                                else:
                                    voice_sessions[voice_session_id]["pending_kitty_image_paragraph"] = True
                                    voice_sessions[voice_session_id].pop(
                                        "kitty_image_paragraph_empty_streak", None
                                    )
                                    await safe_websocket_send(
                                        websocket,
                                        {"type": "image_appended", "format": image_format},
                                    )
                            else:
                                logger.warning(
                                    "Cannot append image: OmniClient not found for session %s",
                                    voice_session_id,
                                )
                        else:
                            await safe_websocket_send(
                                websocket,
                                {"type": "error", "error": "Missing image data"},
                            )

            except WebSocketDisconnect:
                logger.info("Client disconnected: %s", voice_session_id)
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.error("Client message error: %s", e, exc_info=True)

        async def handle_omni_events():
            """Handle events from Omni"""
            greeting_sent = False  # Track if greeting was sent
            try:
                async for event in omni_generator:
                    event_type = event.get("type")

                    # Send short greeting when session is ready
                    if not greeting_sent and event_type == "session_ready":
                        # Build short, personalized greeting (avoid long intro that triggers Omni's self-intro)
                        diagram_type = voice_sessions[voice_session_id].get("diagram_type", "unknown")
                        sess_ctx = voice_sessions[voice_session_id].get("context", {})
                        greeting_lang = resolve_voice_interaction_language(
                            sess_ctx if isinstance(sess_ctx, dict) else {}
                        )
                        greeting = build_greeting_message(
                            diagram_type, language=greeting_lang
                        )

                        omni_client = get_session_omni_client(voice_session_id)
                        if omni_client:
                            await omni_client.create_greeting(greeting_text=greeting)
                        else:
                            logger.debug(
                                "Cannot create greeting: OmniClient not found for session %s",
                                voice_session_id,
                            )
                        greeting_sent = True
                        logger.debug("Greeting sent: %s...", greeting[:50])

                    if event_type == "transcription":
                        transcription_text = event.get("text", "")
                        session_mut = voice_sessions[voice_session_id]
                        session_context = session_mut.get("context", {})

                        logger.debug(
                            "Omni transcription received (%d chars)",
                            len(transcription_text),
                        )

                        # Send transcription to client
                        await safe_websocket_send(
                            websocket,
                            {"type": "transcription", "text": transcription_text},
                        )

                        image_paragraph_followup = False
                        if session_mut.get("pending_kitty_image_paragraph"):
                            if not transcription_text.strip():
                                streak = session_mut.get("kitty_image_paragraph_empty_streak", 0) + 1
                                session_mut["kitty_image_paragraph_empty_streak"] = streak
                                if streak >= 15:
                                    session_mut["pending_kitty_image_paragraph"] = False
                                    session_mut.pop("kitty_image_paragraph_empty_streak", None)
                                continue
                            image_paragraph_followup = True
                            session_mut["pending_kitty_image_paragraph"] = False
                            session_mut.pop("kitty_image_paragraph_empty_streak", None)

                        # Store in conversation history
                        session_mut["conversation_history"].append(
                            {"role": "user", "content": transcription_text}
                        )

                        # Parse voice command using unified command processing
                        # Voice transcriptions use higher confidence threshold (0.7)
                        try:
                            # Short vision summaries after a photo often fail is_paragraph_text();
                            # route the first non-empty transcript after append_image through Qwen Plus.
                            if image_paragraph_followup:
                                command_executed = await process_paragraph_with_qwen_plus(
                                    websocket,
                                    voice_session_id,
                                    transcription_text,
                                    session_context,
                                )
                                if command_executed:
                                    continue

                            # Process command through unified function (handles UI actions AND diagram updates)
                            command_executed = await process_voice_command(
                                websocket,
                                voice_session_id,
                                transcription_text,
                                session_context,
                                is_text_message=False,
                            )

                            # If command was executed (UI actions or diagram updates), we're done
                            if command_executed:
                                continue

                            # Otherwise, continue to next transcription (no action needed)
                            continue

                        except (
                            ValueError,
                            KeyError,
                            RuntimeError,
                            AttributeError,
                        ) as voice_error:
                            logger.error(
                                "Voice command processing error: %s",
                                voice_error,
                                exc_info=True,
                            )

                    elif event_type == "text_chunk":
                        text_chunk = event.get("text", "")
                        logger.debug(
                            "Omni text chunk (%d chars)",
                            len(text_chunk),
                        )
                        await safe_websocket_send(websocket, {"type": "text_chunk", "text": text_chunk})

                    elif event_type == "audio_chunk":
                        # Send base64 audio to client
                        audio_bytes = event.get("audio")
                        if audio_bytes is None:
                            logger.warning("Received audio_chunk event without audio data")
                            continue
                        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

                        # Log audio chunk (every 5th to avoid spam)
                        if random.random() < 0.2:
                            logger.debug(
                                "Omni audio chunk: %d bytes -> %d base64",
                                len(audio_bytes),
                                len(audio_b64),
                            )

                        await safe_websocket_send(websocket, {"type": "audio_chunk", "audio": audio_b64})

                    elif event_type == "speech_started":
                        logger.debug("VAD: Speech started at %sms", event.get("audio_start_ms"))
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "speech_started",
                                "audio_start_ms": event.get("audio_start_ms"),
                            },
                        )

                    elif event_type == "speech_stopped":
                        logger.debug("VAD: Speech stopped at %sms", event.get("audio_end_ms"))
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "speech_stopped",
                                "audio_end_ms": event.get("audio_end_ms"),
                            },
                        )

                    elif event_type == "response_done":
                        logger.debug("Omni response complete")
                        # NOTE: Token tracking is now handled automatically by WebSocket LLM middleware
                        # The middleware wraps the generator and tracks tokens on response_done events

                        await safe_websocket_send(websocket, {"type": "response_done"})

                    elif event_type == "error":
                        await safe_websocket_send(
                            websocket,
                            {"type": "error", "error": str(event.get("error"))},
                        )

                    # Additional informational events (forwarded for future use)
                    elif event_type == "session_created":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "session_created",
                                "session": event.get("session", {}),
                            },
                        )

                    elif event_type == "session_updated":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "session_updated",
                                "session": event.get("session", {}),
                            },
                        )

                    elif event_type == "response_created":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "response_created",
                                "response": event.get("response", {}),
                            },
                        )

                    elif event_type == "audio_buffer_committed":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "audio_buffer_committed",
                                "item_id": event.get("item_id"),
                            },
                        )

                    elif event_type == "audio_buffer_cleared":
                        await safe_websocket_send(websocket, {"type": "audio_buffer_cleared"})

                    elif event_type == "item_created":
                        await safe_websocket_send(
                            websocket,
                            {"type": "item_created", "item": event.get("item", {})},
                        )

                    elif event_type == "response_text_done":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "response_text_done",
                                "text": event.get("text", ""),
                            },
                        )

                    elif event_type == "response_audio_done":
                        await safe_websocket_send(websocket, {"type": "response_audio_done"})

                    elif event_type == "response_audio_transcript_done":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "response_audio_transcript_done",
                                "transcript": event.get("transcript", ""),
                            },
                        )

                    elif event_type == "output_item_added":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "output_item_added",
                                "item": event.get("item", {}),
                            },
                        )

                    elif event_type == "output_item_done":
                        await safe_websocket_send(
                            websocket,
                            {"type": "output_item_done", "item": event.get("item", {})},
                        )

                    elif event_type == "content_part_added":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "content_part_added",
                                "part": event.get("part", {}),
                            },
                        )

                    elif event_type == "content_part_done":
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "content_part_done",
                                "part": event.get("part", {}),
                            },
                        )

            except (RuntimeError, ConnectionError, AttributeError, ValueError) as e:
                logger.error("Omni event error: %s", e, exc_info=True)
                await safe_websocket_send(websocket, {"type": "error", "error": str(e)})

        async def kitty_idle_watchdog() -> None:
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

        client_task = asyncio.create_task(handle_client_messages())
        omni_task = asyncio.create_task(handle_omni_events())

        if idle_timeout_sec is None:
            await asyncio.gather(client_task, omni_task)
        else:
            idle_task = asyncio.create_task(kitty_idle_watchdog())
            done, _pending = await asyncio.wait(
                {client_task, omni_task, idle_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if idle_task in done:
                if not client_task.done():
                    client_task.cancel()
                if not omni_task.done():
                    omni_task.cancel()
            else:
                idle_task.cancel()
            await asyncio.gather(client_task, omni_task, idle_task, return_exceptions=True)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", voice_session_id)

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await safe_websocket_send(websocket, {"type": "error", "error": str(e)})
        except Exception as exc:
            logger.debug("Failed to send WebSocket error response: %s", exc)

    finally:
        # Unregister from central WS registry — guaranteed even on crash / SIGTERM.
        # unregister() decrements the per-endpoint counter.
        await _ws_registry.unregister(_voice_ws_session.session_id)
        await redis_increment_active_total(-1)
        logger.info(
            "[WSSession] CLOSE session=%s endpoint=kitty user_id=%s duration=%.1fs",
            _voice_ws_session.session_id,
            current_user.id,
            time.monotonic() - _ws_session_started,
        )

        async with diagram_session_voice_lock(diagram_session_id):
            if diagram_session_id in active_websockets:
                try:
                    active_websockets[diagram_session_id].remove(websocket)
                    logger.debug(
                        "Removed WebSocket from active connections for diagram %s",
                        diagram_session_id,
                    )
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
        await hub.close_session(hub_session_id, reason="websocket_closed")


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
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {
            "recommended_scope": None,
            "desktop_focus": {"diagram_library_id": None, "updated_at": None},
            "context": {
                "diagram_data": {},
                "selected_nodes": [],
                "diagram_type": "circle_map",
            },
            "diagram_type": "circle_map",
            "active_panel": "none",
            "source": "empty",
        }
    hub_bootstrap = get_mind_graph_agent_hub()
    return await hub_bootstrap.get_diagram_context(
        user_id=int(current_user.id),
        source_module="kitty_mobile_bootstrap_http",
        client_lane="mobile",
        client_suggested_scope=suggested_scope,
    )


@router.get("/api/kitty/desktop_focus")
async def kitty_desktop_focus_get(current_user: User = Depends(get_current_user)):
    """
    Library diagram id the user last had open on desktop MindGraph, for mobile Kitty pairing.

    Mobile polls this when the local Pinia store has no ``activeDiagramId`` so
    ``/ws/kitty/{scope}`` can align with the computer.
    """
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"diagram_library_id": None, "updated_at": None}
    lib_id, updated_at = await get_kitty_desktop_focus_diagram(int(current_user.id))
    return {"diagram_library_id": lib_id, "updated_at": updated_at}


@router.put("/api/kitty/desktop_focus")
async def kitty_desktop_focus_put(
    current_user: User = Depends(get_current_user),
    diagram_library_id: str | None = Body(default=None, embed=True),
):
    """Publish or clear desktop MindGraph library focus for the authenticated user."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"ok": True, "diagram_library_id": None, "updated_at": None}
    await set_kitty_desktop_focus_diagram(int(current_user.id), diagram_library_id)
    lib_id, updated_at = await get_kitty_desktop_focus_diagram(int(current_user.id))
    return {"ok": True, "diagram_library_id": lib_id, "updated_at": updated_at}


@router.get("/api/kitty/mobile_lane/{diagram_session_id}")
async def kitty_mobile_lane_hint(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    True when this user has an active Kitty WebSocket session on this library scope that
    declared ``client_lane: mobile`` in its ``start`` frame (phone mic), so desktop can
    show the pairing indicator without opening a WebSocket.
    """
    if not config.FEATURE_KITTY_WS_ENABLED:
        return {"armed": False}
    scope = normalize_kitty_diagram_session_id(diagram_session_id)
    if scope is None:
        raise HTTPException(status_code=400, detail="Invalid diagram session id")
    armed = await kitty_mobile_indicator_armed_for_user(scope, int(current_user.id))
    return {"armed": armed}


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
        else:
            logger.debug("No active voice session found for diagram %s", scope)
            return {"success": True, "message": "No active voice session found"}

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("Cleanup error: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
