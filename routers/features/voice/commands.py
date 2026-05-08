"""Voice command parsing and UI actions (non-Omni)."""

from typing import Any, Dict

from fastapi import WebSocket

from services.features.kitty_diagram_review_annotate import compute_kitty_diagram_review_annotations
from services.features.voice_agent import kitty_agent_manager

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

from services.kitty.kitty_desktop_action_queue import enqueue_kitty_desktop_action
from services.kitty.kitty_diagram_vocabulary import normalize_voice_desktop_canvas_diagram_type
from services.kitty.kitty_session_redis import (
    apply_redis_live_to_voice_session,
    load_kitty_live_context,
)
from routers.features.voice.diagram_execute import execute_diagram_update
from routers.features.voice.diagram_utils import (
    get_diagram_prefix_map,
    is_paragraph_text,
)
from routers.features.voice.kitty_library_context_refresh import (
    throttled_refresh_voice_context_from_library,
)
from routers.features.voice.messaging import (
    hydrate_omni_for_diagram_pedagogical_review,
    safe_websocket_send,
    user_requests_diagram_pedagogical_review,
)
from routers.features.voice.paragraph import process_paragraph_with_qwen_plus
from routers.features.voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
    get_voice_session,
)
from routers.features.voice.state import logger, voice_sessions


async def process_voice_command(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
    is_text_message: bool = False,
) -> bool:
    """
    Process a voice command (from transcription or text message).

    Handles two cases:
    1. Paragraph processing: Long text inputs are processed with Qwen Plus to extract diagram content
    2. Command processing: Short commands are parsed with Qwen Turbo for intention checking

    Returns True if command was executed, False if it should be sent to Omni for conversational response.

    Args:
        websocket: WebSocket connection
        voice_session_id: Voice session ID
        command_text: Command text from user
        session_context: Current session context
        is_text_message: True if this is from text input (lower confidence threshold)

    Note:
        - Paragraphs (long text) are processed with Qwen Plus for content extraction
        - Commands (short text) are parsed with Qwen Turbo (classification model) for intention checking
        - No keyword detection - all parsing is done by LLM
    """
    try:
        live_session = get_voice_session(voice_session_id)
        if live_session:
            ws_diagram_id = live_session.get("diagram_session_id")
            if isinstance(ws_diagram_id, str) and ws_diagram_id.strip():
                live_payload = await load_kitty_live_context(ws_diagram_id.strip())
                if live_payload:
                    apply_redis_live_to_voice_session(live_session, live_payload)
            session_context = dict(live_session.get("context") or session_context)

            refresh_uid = None
            uid_raw = live_session.get("user_id")
            if uid_raw is not None:
                try:
                    refresh_uid = int(uid_raw) if isinstance(uid_raw, str) else int(uid_raw)
                except (ValueError, TypeError):
                    refresh_uid = None
            ws_scope = live_session.get("diagram_session_id")
            if refresh_uid is not None and isinstance(ws_scope, str) and ws_scope.strip():
                await throttled_refresh_voice_context_from_library(
                    user_id=refresh_uid,
                    voice_session_id=voice_session_id,
                    diagram_session_id=ws_scope.strip(),
                    force=True,
                )
                session_context = dict(live_session.get("context") or session_context)

        if user_requests_diagram_pedagogical_review(command_text):
            try:
                await hydrate_omni_for_diagram_pedagogical_review(
                    voice_session_id,
                    session_context,
                )
            except (RuntimeError, ConnectionError, AttributeError, ValueError) as hydrate_exc:
                logger.debug("[Kitty] diagram review instruction hydrate skipped: %s", hydrate_exc)

        # CRITICAL: Check if input is a paragraph (long text for processing)
        # Common case: Teachers paste whole paragraphs expecting diagram generation
        if is_paragraph_text(command_text):
            logger.info(
                "Detected paragraph input (length: %d), processing with Qwen Plus",
                len(command_text),
            )
            return await process_paragraph_with_qwen_plus(websocket, voice_session_id, command_text, session_context)

        # Otherwise, process as a command
        # Get the persistent agent for this session
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        # This ensures the agent is scoped to the diagram session, not the WebSocket connection
        agent_session_id = get_agent_session_id(voice_session_id)
        agent = kitty_agent_manager.get_or_create(agent_session_id)

        # Get user info from session for token tracking
        session = live_session or get_voice_session(voice_session_id)
        user_id = None
        organization_id = None
        if session:
            user_id_str = session.get("user_id")
            # Convert user_id to int if it's a string (voice_sessions stores as string)
            if user_id_str:
                try:
                    user_id = int(user_id_str) if isinstance(user_id_str, str) else user_id_str
                    # Get organization_id from user if available (use cache)
                    if redis_user_cache:
                        try:
                            user = await redis_user_cache.get_by_id(user_id)
                            if user:
                                organization_id = user.organization_id
                        except (AttributeError, KeyError) as e:
                            logger.debug(
                                "Error getting organization_id for token tracking: %s",
                                e,
                            )
                except (ValueError, TypeError) as e:
                    logger.debug("Error converting user_id for token tracking: %s", e)

        # CRITICAL: Get diagram_type directly from voice_sessions (source of truth)
        # session_context may be stale when diagram type changes
        # Always check voice_sessions first, then fallback to session_context
        diagram_type = None
        if voice_session_id in voice_sessions:
            diagram_type = voice_sessions[voice_session_id].get("diagram_type")
        if not diagram_type and session:
            diagram_type = session.get("diagram_type")
        if not diagram_type:
            diagram_type = session_context.get("diagram_type")

        if not diagram_type:
            logger.warning("VOIC | Could not determine diagram_type for voice command, defaulting to circle_map")
            diagram_type = "circle_map"

        logger.debug("VOIC | Using diagram_type=%s for voice command processing", diagram_type)

        if user_requests_diagram_pedagogical_review(command_text):
            try:
                annotations = await compute_kitty_diagram_review_annotations(
                    command_text,
                    diagram_type=str(diagram_type),
                    diagram_data=dict(session_context.get("diagram_data") or {}),
                    user_id=user_id,
                    organization_id=organization_id,
                    voice_session_id=voice_session_id,
                )
                if annotations.get("items") or str(annotations.get("summary") or "").strip():
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "diagram_review_annotation",
                            "summary": annotations.get("summary", ""),
                            "items": annotations.get("items", []),
                        },
                    )
            except (RuntimeError, ConnectionError, AttributeError, ValueError, TypeError) as ann_exc:
                logger.debug("[Kitty] diagram review annotations skipped: %s", ann_exc)

        # Process command through LLM (Qwen Turbo) for intention checking
        # LLM parses the command and returns structured action JSON (no keyword detection)
        # Pass user tracking info for token tracking
        command = await agent.process_command(
            command_text,
            user_id=user_id,
            organization_id=organization_id,
            voice_session_id=voice_session_id,
            diagram_type=diagram_type,
        )

        action = command["action"]
        target = command.get("target")
        node_index = command.get("node_index")
        confidence = command.get("confidence", 0.0)

        logger.debug(
            "Command processed: action=%s, target=%s, node_index=%s, confidence=%s, is_text=%s",
            action,
            target,
            node_index,
            confidence,
            is_text_message,
        )

        # Only proceed if confidence is high enough (except for UI actions)
        ui_actions = [
            "open_thinkguide",
            "close_thinkguide",
            "open_node_palette",
            "close_node_palette",
            "open_mindmate",
            "close_mindmate",
            "close_all_panels",
            "select_node",
            "explain_node",
            "ask_thinkguide",
            "ask_mindmate",
            "auto_complete",
            "start_inline_recommendations",
            "help",
            "open_desktop_canvas",
        ]

        # For text messages, use lower confidence threshold (0.5) since they're more explicit
        # This allows conversational requests like "can you change..." to be executed
        confidence_threshold = 0.5 if is_text_message else 0.7

        # Check if this is a diagram update action
        diagram_update_actions = [
            "update_center",
            "update_node",
            "add_node",
            "delete_node",
        ]
        if action in diagram_update_actions:
            # For diagram updates, execute if confidence meets threshold
            if confidence >= confidence_threshold:
                return await execute_diagram_update(websocket, voice_session_id, action, command, session_context)
            else:
                logger.debug(
                    "Low confidence (%s) for diagram update '%s', threshold=%s",
                    confidence,
                    action,
                    confidence_threshold,
                )
                return False

        # For non-diagram-update actions, check confidence
        if action not in ui_actions and confidence < confidence_threshold:
            logger.debug(
                "Low confidence (%s), should send to Omni for conversational response",
                confidence,
            )
            return False

        # Handle UI actions first
        if action == "open_thinkguide":
            # Redirect to MindMate
            logger.debug("Opening MindMate panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "open_mindmate", "params": {}})
            return True

        elif action == "close_thinkguide":
            # Redirect to MindMate
            logger.debug("Closing MindMate panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "close_mindmate", "params": {}})
            return True

        elif action == "open_node_palette":
            logger.debug("Opening Node Palette")
            await safe_websocket_send(
                websocket,
                {"type": "action", "action": "open_node_palette", "params": {}},
            )
            return True

        elif action == "close_node_palette":
            logger.debug("Closing Node Palette")
            await safe_websocket_send(
                websocket,
                {"type": "action", "action": "close_node_palette", "params": {}},
            )
            return True

        elif action == "open_mindmate":
            logger.debug("Opening MindMate AI panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "open_mindmate", "params": {}})
            return True

        elif action == "close_mindmate":
            logger.debug("Closing MindMate AI panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "close_mindmate", "params": {}})
            return True

        elif action == "close_all_panels":
            logger.debug("Closing all panels")
            await safe_websocket_send(
                websocket,
                {"type": "action", "action": "close_all_panels", "params": {}},
            )
            return True

        # Interaction control
        elif action == "auto_complete":
            logger.info("Triggering AI auto-complete from text/voice command")
            await safe_websocket_send(websocket, {"type": "action", "action": "auto_complete", "params": {}})
            # Send acknowledgment message to user via Omni
            try:
                # Create a response acknowledging the action
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.create_response(instructions="收到，正在自动补全。")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Could not send acknowledgment to Omni: %s", e)
            return True

        elif action == "start_inline_recommendations":
            logger.info("Kitty: start inline recommendations action")
            resolved_node_id = command.get("node_id")
            if node_index is not None and not resolved_node_id:
                diagram_type = voice_sessions[voice_session_id].get("diagram_type", "circle_map")
                prefix_map = get_diagram_prefix_map()
                prefix = prefix_map.get(diagram_type, "node")
                resolved_node_id = f"{prefix}_{node_index}"
            params: Dict[str, Any] = {}
            if resolved_node_id:
                params["node_id"] = resolved_node_id
            if node_index is not None:
                params["node_index"] = node_index
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "start_inline_recommendations",
                    "params": params,
                },
            )
            try:
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.create_response(instructions="好，打开联想建议。")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Could not send acknowledgment to Omni: %s", e)
            return True

        elif action == "ask_thinkguide" and target:
            # Redirect to MindMate
            logger.debug("Sending question to MindMate: %s", target)
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "ask_mindmate",
                    "params": {"message": target},
                },
            )
            return True

        elif action == "ask_mindmate" and target:
            logger.debug("Sending question to MindMate: %s", target)
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "ask_mindmate",
                    "params": {"message": target},
                },
            )
            return True

        elif action == "select_node":
            node_id = command.get("node_id")
            resolved_node_id = node_id

            # Resolve node_id from index if needed
            if node_index is not None and not resolved_node_id:
                diagram_type = voice_sessions[voice_session_id].get("diagram_type", "circle_map")
                prefix_map = get_diagram_prefix_map()
                prefix = prefix_map.get(diagram_type, "node")
                resolved_node_id = f"{prefix}_{node_index}"

            if resolved_node_id:
                logger.debug("Selecting node: %s", resolved_node_id)
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "action",
                        "action": "select_node",
                        "params": {
                            "node_id": resolved_node_id,
                            "node_index": node_index,
                        },
                    },
                )
            return True

        elif action == "explain_node":
            node_id = command.get("node_id")
            node_label = target
            if (node_id or node_index is not None) and node_label:
                resolved_node_id = node_id
                if node_index is not None and not resolved_node_id:
                    nodes = session_context.get("diagram_data", {}).get("children", [])
                    if 0 <= node_index < len(nodes):
                        node = nodes[node_index]
                        resolved_node_id = node.get("id") if isinstance(node, dict) else f"context_{node_index}"
                        if not node_label:
                            node_label = node.get("text", node.get("label", ""))

                if resolved_node_id and node_label:
                    logger.debug("Explaining node: %s (%s)", resolved_node_id, node_label)
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "action",
                            "action": "explain_node",
                            "params": {
                                "node_id": resolved_node_id,
                                "node_label": node_label,
                                "prompt": f'请解释一下"{node_label}"这个概念，用简单的语言，适合K12学生理解。',
                            },
                        },
                    )
            return True

        elif action == "open_desktop_canvas":
            if user_id is None:
                logger.warning("Kitty open_desktop_canvas: missing user_id")
                return False
            raw_slug = command.get("diagram_type")
            slug = normalize_voice_desktop_canvas_diagram_type(
                raw_slug if isinstance(raw_slug, str) else None
            )
            if slug is None:
                logger.info("Kitty open_desktop_canvas: rejected diagram_type=%s", raw_slug)
                return False

            payload: Dict[str, Any] = {
                "kind": "open_canvas",
                "diagram_type": slug,
            }
            targ = command.get("target")
            if isinstance(targ, str) and targ.strip():
                payload["topic"] = targ.strip()
            left_val = command.get("left")
            if isinstance(left_val, str) and left_val.strip():
                payload["left"] = left_val.strip()
            right_val = command.get("right")
            if isinstance(right_val, str) and right_val.strip():
                payload["right"] = right_val.strip()

            ok = await enqueue_kitty_desktop_action(user_id, payload)
            try:
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    ack = "好，已在电脑端打开画布。" if ok else "电脑端暂时打不开画布，请稍后重试。"
                    await omni_client.create_response(instructions=ack)
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("open_desktop_canvas Omni ack skipped: %s", e)
            return True

        elif action == "help":
            logger.debug("User requested help - opening MindMate")
            await safe_websocket_send(websocket, {"type": "action", "action": "open_mindmate", "params": {}})
            return True

        elif action == "none":
            logger.debug("No command detected - should send to Omni for conversational response")
            return False

        # Unknown action - send to Omni
        return False

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Command processing error: %s", e, exc_info=True)
        return False  # Send to Omni on error
