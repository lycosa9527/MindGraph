"""Voice WebSocket route and REST cleanup endpoint."""

import asyncio
import base64
import random

from fastapi import Depends, WebSocket, WebSocketDisconnect

from config.settings import config
from models.domain.auth import User
from services.features.voice_agent import voice_agent_manager
from services.features.websocket_llm_middleware import omni_middleware

from services.auth.vpn_geo_enforcement import maybe_close_websocket_for_vpn_cn_geo

_close_ws_if_vpn_cn_geo = maybe_close_websocket_for_vpn_cn_geo
from utils.auth import get_current_user
from utils.auth_ws import authenticate_websocket_user

from routers.features.voice.commands import process_voice_command
from routers.features.voice.messaging import (
    build_greeting_message,
    build_voice_instructions,
    safe_websocket_send,
)
from routers.features.voice.session_ops import (
    cleanup_voice_by_diagram_session,
    create_voice_session,
    end_voice_session,
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


@router.websocket("/ws/voice/{diagram_session_id}")
async def voice_conversation(websocket: WebSocket, diagram_session_id: str):
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
    # Accept connection first (required before we can close it or use it)
    await websocket.accept()

    # Check if voice agent feature is enabled
    if not config.FEATURE_VOICE_AGENT:
        await websocket.close(code=4003, reason="Voice agent feature is disabled")
        logger.warning("Voice agent WebSocket connection rejected: feature disabled")
        return

    current_user, auth_error = await authenticate_websocket_user(websocket)
    if auth_error or current_user is None:
        await websocket.close(
            code=4001,
            reason=auth_error or "Authentication failed",
        )
        logger.warning("WebSocket auth failed: %s", auth_error)
        return

    if await _close_ws_if_vpn_cn_geo(websocket):
        logger.warning("WebSocket VPN/CN policy closed connection for user_id=%s", current_user.id)
        return

    logger.info("WebSocket connection accepted user_id=%s", current_user.id)

    voice_session_id = None
    omni_generator = None
    user_id = str(current_user.id)

    try:
        # CRITICAL: Close any existing WebSocket connections for this diagram_session_id
        # This ensures fresh state when switching diagrams
        if diagram_session_id in active_websockets:
            existing_ws_list = active_websockets[diagram_session_id]
            logger.debug(
                "Closing %d existing WebSocket connection(s) for diagram %s",
                len(existing_ws_list),
                diagram_session_id,
            )
            for existing_ws in existing_ws_list:
                try:
                    await existing_ws.close(code=1001, reason="Diagram session ended")
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    logger.debug("Error closing existing WebSocket: %s", e)
            active_websockets[diagram_session_id] = []

        # Wait for start message
        start_msg = await websocket.receive_json()

        if start_msg.get("type") != "start":
            logger.warning("Invalid start message type: %s", start_msg.get("type"))
            await safe_websocket_send(websocket, {"type": "error", "error": "Expected start message"})
            await websocket.close()
            return

        logger.debug("Starting voice conversation for user %s", user_id)

        # CRITICAL: Voice agent session MUST be scoped to diagram_session_id
        # This ensures one agent per diagram session, proper cleanup, and no cross-contamination
        # Use diagram_session_id as the agent session identifier (not a random UUID)
        agent_session_id = f"diagram_{diagram_session_id}"

        # CRITICAL: Clean up any existing voice session for this diagram_session_id FIRST
        # This ensures old conversation history doesn't persist when switching diagrams
        # IMPORTANT: Do this BEFORE registering the new WebSocket to avoid closing it
        # We already closed existing WebSocket connections above, this cleans up session state
        existing_cleaned = await cleanup_voice_by_diagram_session(diagram_session_id)
        if existing_cleaned:
            logger.debug("Cleaned up existing voice session for diagram %s", diagram_session_id)

        # Also cleanup the agent if it exists (should be cleaned up already, but double-check)
        if agent_session_id in voice_agent_manager._agents:  # pylint: disable=protected-access
            logger.debug("Removing existing agent for diagram session %s", diagram_session_id)
            voice_agent_manager.remove(agent_session_id)

        # NOTE: No need to close existing Omni conversation here anymore
        # Each voice session now has its own OmniClient instance (created in create_voice_session)
        # This prevents cross-contamination between concurrent users

        # CRITICAL: Register this WebSocket connection for this diagram_session_id
        # Do this AFTER cleanup to ensure we don't close our own connection
        if diagram_session_id not in active_websockets:
            active_websockets[diagram_session_id] = []
        active_websockets[diagram_session_id].append(websocket)
        logger.debug(
            "Registered WebSocket for diagram %s (total: %d)",
            diagram_session_id,
            len(active_websockets[diagram_session_id]),
        )

        # Create new voice session (with fresh conversation_history: [])
        voice_session_id = create_voice_session(
            user_id=user_id,
            diagram_session_id=diagram_session_id,
            diagram_type=start_msg.get("diagram_type"),
            active_panel=start_msg.get("active_panel", "mindmate"),
        )

        logger.debug(
            "Session created: %s, diagram_type=%s, panel=%s",
            voice_session_id,
            start_msg.get("diagram_type"),
            start_msg.get("active_panel"),
        )
        logger.debug("Agent session ID: %s (scoped to diagram_session_id)", agent_session_id)

        # Store initial context
        voice_sessions[voice_session_id]["context"] = start_msg.get("context", {})

        # Initialize persistent LangGraph agent with diagram state
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        # This ensures the agent is scoped to the diagram session, not the WebSocket connection
        # If agent already exists (shouldn't happen after cleanup), clear its history
        initial_context = start_msg.get("context", {})
        agent = voice_agent_manager.get_or_create(agent_session_id)

        # CRITICAL: Clear agent's conversation history when starting a new diagram session
        # This ensures no cross-contamination between diagram sessions
        agent.clear_history()

        # Sync initial diagram state to agent
        diagram_data = initial_context.get("diagram_data", {})
        diagram_data["diagram_type"] = start_msg.get("diagram_type")
        agent.update_diagram_state(diagram_data)
        agent.update_panel_state(start_msg.get("active_panel", "none"), initial_context.get("panels", {}))

        logger.debug(
            "VoiceAgent initialized with %d nodes",
            len(diagram_data.get("children", [])),
        )

        # Build instructions with FULL context including diagram_data
        context = {
            "diagram_type": start_msg.get("diagram_type"),
            "active_panel": start_msg.get("active_panel"),
            "conversation_history": [],
            "selected_nodes": initial_context.get("selected_nodes", []),
            "diagram_data": initial_context.get("diagram_data", {}),  # Include node content!
        }
        instructions = build_voice_instructions(context)

        children_count = len(context.get("diagram_data", {}).get("children", []))
        logger.debug("Initial instructions built with %d nodes", children_count)

        logger.debug("Built instructions for context: %d chars", len(instructions))

        # CRITICAL: Use session-specific OmniClient (not singleton)
        # Each voice session has its own OmniClient instance to support concurrent users
        session = get_voice_session(voice_session_id)
        if not session:
            logger.error("Voice session %s not found", voice_session_id)
            await websocket.close(code=1008, reason="Session not found")
            return

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
            endpoint_path="/ws/voice",
        )

        # Store generator in session for cleanup
        voice_sessions[voice_session_id]["omni_generator"] = omni_generator

        # Send connected confirmation
        await safe_websocket_send(websocket, {"type": "connected", "session_id": voice_session_id})

        logger.debug("Voice session %s connected", voice_session_id)

        # Wait for SDK to initialize conversation (check via async iteration start)
        # The first event will confirm conversation is ready
        logger.debug("Waiting for Omni session to initialize...")

        # Handle messages concurrently
        async def handle_client_messages():
            """Handle messages from client"""
            try:
                while True:
                    message = await websocket.receive_json()
                    msg_type = message.get("type")

                    if msg_type == "audio":
                        # Forward audio to Omni
                        audio_data = message.get("data")
                        if audio_data:
                            # Log every 20th audio packet to avoid spam
                            if random.random() < 0.05:
                                logger.debug(
                                    "Forwarding audio to Omni: %d bytes (base64)",
                                    len(audio_data),
                                )
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                await omni_client.send_audio(audio_data)
                            else:
                                logger.warning(
                                    "Cannot send audio: OmniClient not found for session %s",
                                    voice_session_id,
                                )

                    elif msg_type == "text":
                        # Handle text message from user
                        text = message.get("text", "").strip()
                        if text:
                            logger.debug("Received text message: %s", text)

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

                    elif msg_type == "context_update":
                        # Update context and instructions with full diagram data
                        active_panel = message.get("active_panel")
                        new_context = message.get("context", {})

                        # CRITICAL: Update diagram_type from context if provided
                        # This ensures the session knows the current diagram type when switching diagrams
                        new_diagram_type = new_context.get("diagram_type")
                        if new_diagram_type:
                            old_diagram_type = voice_sessions[voice_session_id].get("diagram_type")
                            voice_sessions[voice_session_id]["diagram_type"] = new_diagram_type
                            if old_diagram_type != new_diagram_type:
                                logger.info(
                                    "VOIC | Diagram type updated: %s -> %s for session %s",
                                    old_diagram_type,
                                    new_diagram_type,
                                    voice_session_id,
                                )
                                # CRITICAL: When diagram type changes, clear old diagram data
                                # to prevent cross-contamination
                                if "diagram_data" in voice_sessions[voice_session_id].get("context", {}):
                                    voice_sessions[voice_session_id]["context"]["diagram_data"] = {}

                        update_panel_context(voice_session_id, active_panel)
                        voice_sessions[voice_session_id]["context"].update(new_context)

                        # CRITICAL: Ensure diagram_type is also in context dict for consistency
                        # This prevents issues when session_context is passed to other functions
                        if new_diagram_type:
                            voice_sessions[voice_session_id]["context"]["diagram_type"] = new_diagram_type

                        # Update persistent agent's diagram state (keeps agent in sync)
                        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
                        agent_session_id = get_agent_session_id(voice_session_id)
                        agent = voice_agent_manager.get_or_create(agent_session_id)
                        diagram_data = new_context.get("diagram_data", {})
                        # Use updated diagram_type from session (or fallback to context)
                        session_diagram_type = voice_sessions[voice_session_id].get("diagram_type")
                        diagram_data["diagram_type"] = session_diagram_type or new_diagram_type
                        agent.update_diagram_state(diagram_data)
                        agent.update_panel_state(active_panel, new_context.get("panels", {}))

                        # Rebuild and update Omni instructions with FULL context
                        updated_context = {
                            "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
                            "active_panel": active_panel,
                            "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
                            "selected_nodes": new_context.get("selected_nodes", []),
                            "diagram_data": diagram_data,
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
                            omni_client = get_session_omni_client(voice_session_id)
                            if omni_client:
                                # Decode base64 to bytes (base64 imported at top of file)
                                image_bytes = base64.b64decode(image_data)
                                await omni_client.append_image(image_bytes, image_format)
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
                logger.debug("Client disconnected: %s", voice_session_id)
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
                        greeting = build_greeting_message(diagram_type, language="zh")

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
                        session_context = voice_sessions[voice_session_id].get("context", {})

                        logger.debug("Omni transcription: '%s'", transcription_text)

                        # Send transcription to client
                        await safe_websocket_send(
                            websocket,
                            {"type": "transcription", "text": transcription_text},
                        )

                        # Store in conversation history
                        voice_sessions[voice_session_id]["conversation_history"].append(
                            {"role": "user", "content": transcription_text}
                        )

                        # Parse voice command using unified command processing
                        # Voice transcriptions use higher confidence threshold (0.7)
                        try:
                            session_context = voice_sessions[voice_session_id].get("context", {})

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
                        logger.debug("Omni text chunk: '%s'", text_chunk)
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

        # Run both handlers concurrently
        await asyncio.gather(handle_client_messages(), handle_omni_events())

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected: %s", voice_session_id)

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("WebSocket error: %s", e, exc_info=True)
        try:
            await safe_websocket_send(websocket, {"type": "error", "error": str(e)})
        except Exception as exc:
            logger.debug("Failed to send WebSocket error response: %s", exc)

    finally:
        # Cleanup
        if voice_session_id:
            end_voice_session(voice_session_id, reason="websocket_closed")

        # CRITICAL: Remove WebSocket from active connections tracking
        if diagram_session_id in active_websockets:
            try:
                active_websockets[diagram_session_id].remove(websocket)
                logger.debug(
                    "Removed WebSocket from active connections for diagram %s",
                    diagram_session_id,
                )
                # Clean up empty list
                if not active_websockets[diagram_session_id]:
                    del active_websockets[diagram_session_id]
            except ValueError:
                # WebSocket not in list (already removed)
                pass

        # CRITICAL: Close session-specific Omni client
        # Each voice session has its own OmniClient instance that must be closed
        if voice_session_id:
            session = get_voice_session(voice_session_id)
            if session and "omni_client" in session:
                omni_client = session["omni_client"]
                try:
                    close_result = omni_client.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
                    logger.debug("Closed Omni client for session %s", voice_session_id)
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    logger.debug(
                        "Error closing Omni client for session %s (may already be closed): %s",
                        voice_session_id,
                        e,
                    )


@router.post("/api/voice/cleanup/{diagram_session_id}")
async def cleanup_voice_session(diagram_session_id: str, current_user: User = Depends(get_current_user)):
    """
    Cleanup voice session and WebSocket connections when diagram session ends.
    Called by session manager on session end or navigation to gallery.

    CRITICAL: This closes all WebSocket connections and cleans up all voice agent state
    for the diagram session, ensuring fresh state when switching diagrams.

    This endpoint is controlled by the session manager and ensures proper
    cleanup of voice sessions when switching diagrams or navigating to gallery.
    """
    # Check if voice agent feature is enabled
    if not config.FEATURE_VOICE_AGENT:
        logger.debug("Voice agent cleanup skipped: feature disabled")
        return {"success": True, "message": "Voice agent feature is disabled"}

    try:
        cleaned = await cleanup_voice_by_diagram_session(diagram_session_id)

        if cleaned:
            logger.info(
                "Voice session and WebSocket connections cleaned up for diagram %s by user %d",
                diagram_session_id,
                current_user.id,
            )
            message = f"Voice session and WebSocket connections cleaned up for diagram {diagram_session_id}"
            return {"success": True, "message": message}
        else:
            logger.debug("No active voice session found for diagram %s", diagram_session_id)
            return {"success": True, "message": "No active voice session found"}

    except (RuntimeError, ConnectionError, AttributeError) as e:
        logger.error("Cleanup error: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}
