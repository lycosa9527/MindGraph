"""Handlers for update_center / update_node voice actions."""

from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.messaging import (
    build_voice_instructions,
    parse_double_bubble_target,
    safe_websocket_send,
)
from routers.features.voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
)
from routers.features.voice.state import logger, voice_sessions


async def _handle_update_center_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    target: Optional[str],
) -> bool:
    """
    Handle update_center action to reduce complexity in execute_diagram_update.

    Returns:
        True if update was executed successfully, False otherwise
    """
    # CRITICAL: Get diagram_type directly from voice_sessions (source of truth)
    # This ensures we have the correct diagram type even if session wasn't updated yet
    diagram_type = None
    if voice_session_id in voice_sessions:
        diagram_type = voice_sessions[voice_session_id].get("diagram_type")
    if not diagram_type:
        # Fallback: try to get from context
        diagram_type = session_context.get("diagram_type")
    if not diagram_type:
        logger.warning("[VOIC] Could not determine diagram_type for update_center action, defaulting to circle_map")
        diagram_type = "circle_map"

    logger.debug(
        "[VOIC] Executing update_center for diagram_type=%s, target=%s",
        diagram_type,
        target,
    )

    # Build updates dict based on diagram type
    # CRITICAL: Check for diagram-specific fields first, then fallback to target/new_text
    updates = {}

    if diagram_type == "double_bubble_map":
        # Double bubble map: use left/right from command if available
        left = command.get("left")
        right = command.get("right")
        if left and right:
            updates = {"left": left, "right": right}
            logger.info("Updating double bubble map: left=%s, right=%s", left, right)
        elif target:
            # CRITICAL: Parse target text to extract left/right for double bubble maps
            # Common patterns: "A和B", "A vs B", "A and B", "A/B", "A与B"
            parsed = parse_double_bubble_target(target)
            if parsed and parsed.get("left") and parsed.get("right"):
                updates = {"left": parsed["left"], "right": parsed["right"]}
                logger.info(
                    "Parsed double bubble map target '%s' -> left=%s, right=%s",
                    target,
                    parsed["left"],
                    parsed["right"],
                )
            else:
                # If parsing fails, log warning and return False (don't use invalid update)
                logger.warning(
                    "Double bubble map update_center: could not parse target '%s' "
                    "into left/right fields. Expected format: 'A和B' or 'A vs B'",
                    target,
                )
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "error",
                        "error": (
                            "Double bubble map requires two topics separated by "
                            f"'和', 'vs', or 'and'. Got: {target}"
                        ),
                    },
                )
                return False
        else:
            logger.warning("Double bubble map update_center: missing both left/right and target")
            return False
    elif diagram_type == "flow_map":
        title = command.get("title") or target or command.get("new_text")
        if title:
            updates = {"title": title}
            logger.info("Updating flow map title: %s", title)
        else:
            logger.warning("Flow map update_center: missing title/target/new_text")
            return False
    elif diagram_type == "multi_flow_map":
        event = command.get("event") or target or command.get("new_text")
        if event:
            updates = {"event": event}
            logger.info("Updating multi-flow map event: %s", event)
        else:
            logger.warning("Multi-flow map update_center: missing event/target/new_text")
            return False
    elif diagram_type == "brace_map":
        whole = command.get("whole") or target or command.get("new_text")
        if whole:
            updates = {"whole": whole}
            logger.info("Updating brace map whole: %s", whole)
        else:
            logger.warning("Brace map update_center: missing whole/target/new_text")
            return False
    elif diagram_type == "bridge_map":
        dimension = command.get("dimension") or target or command.get("new_text")
        if dimension:
            updates = {"dimension": dimension}
            logger.info("Updating bridge map dimension: %s", dimension)
        else:
            logger.warning("Bridge map update_center: missing dimension/target/new_text")
            return False
    else:
        # Default: most diagrams use new_text
        new_text = target or command.get("new_text")
        if new_text:
            updates = {"new_text": new_text}
            logger.info("Updating center to: %s", new_text)
        else:
            logger.warning(
                "Default diagram update_center: missing target/new_text for %s",
                diagram_type,
            )
            return False

    await safe_websocket_send(
        websocket,
        {"type": "diagram_update", "action": "update_center", "updates": updates},
    )

    # CRITICAL: Update session context immediately
    if "diagram_data" not in session_context:
        session_context["diagram_data"] = {}

    # Update diagram data based on diagram type
    if diagram_type == "double_bubble_map":
        if "left" in updates and "right" in updates:
            session_context["diagram_data"]["left"] = updates["left"]
            session_context["diagram_data"]["right"] = updates["right"]
    elif diagram_type == "flow_map":
        if "title" in updates:
            session_context["diagram_data"]["title"] = updates["title"]
    elif diagram_type == "multi_flow_map":
        if "event" in updates:
            session_context["diagram_data"]["event"] = updates["event"]
    elif diagram_type == "brace_map":
        if "whole" in updates:
            session_context["diagram_data"]["whole"] = updates["whole"]
    elif diagram_type == "bridge_map":
        if "dimension" in updates:
            session_context["diagram_data"]["dimension"] = updates["dimension"]
    else:
        # Default: most diagrams use center.text
        if "center" not in session_context["diagram_data"]:
            session_context["diagram_data"]["center"] = {}
        if "new_text" in updates:
            session_context["diagram_data"]["center"]["text"] = updates["new_text"]
        elif target:
            session_context["diagram_data"]["center"]["text"] = target

    # Update agent state and instructions
    # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
    agent_session_id = get_agent_session_id(voice_session_id)
    agent = voice_agent_manager.get_or_create(agent_session_id)
    diagram_data = session_context.get("diagram_data", {})
    diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
    agent.update_diagram_state(diagram_data)

    updated_context = {
        "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
        "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
        "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
        "selected_nodes": session_context.get("selected_nodes", []),
        "diagram_data": diagram_data,
    }
    new_instructions = build_voice_instructions(updated_context)
    # Only update instructions if WebSocket is still open
    try:
        omni_client = get_session_omni_client(voice_session_id)
        if omni_client:
            await omni_client.update_instructions(new_instructions)
    except (RuntimeError, ConnectionError, AttributeError) as e:
        if "close" in str(e).lower() or "closed" in str(e).lower():
            logger.debug("WebSocket closed, skipping instruction update: %s", e)
        else:
            raise

    # Log the actual updated value based on diagram type
    if diagram_type == "double_bubble_map":
        logger.debug(
            "Center updated: left=%s, right=%s",
            updates.get("left"),
            updates.get("right"),
        )
    elif diagram_type == "flow_map":
        logger.debug("Center updated: title=%s", updates.get("title"))
    elif diagram_type == "multi_flow_map":
        logger.debug("Center updated: event=%s", updates.get("event"))
    elif diagram_type == "brace_map":
        logger.debug("Center updated: whole=%s", updates.get("whole"))
    elif diagram_type == "bridge_map":
        logger.debug("Center updated: dimension=%s", updates.get("dimension"))
    else:
        logger.debug("Center updated: %s", updates.get("new_text") or target)
    return True


async def _handle_update_node_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    target: str,
    node_index: Optional[int],
    node_identifier: Optional[str],
) -> bool:
    """
    Handle update_node action to reduce complexity in execute_diagram_update.

    Returns:
        True if update was executed successfully, False otherwise
    """
    # Resolve node by index or by target text (node_identifier)
    resolved_node_id = command.get("node_id")
    resolved_node_index = node_index

    nodes = session_context.get("diagram_data", {}).get("children", [])

    # If we have node_index, use it
    if resolved_node_index is not None:
        if 0 <= resolved_node_index < len(nodes):
            node = nodes[resolved_node_index]
            resolved_node_id = node.get("id") if isinstance(node, dict) else f"context_{resolved_node_index}"
        else:
            logger.warning("Node index %d out of bounds", resolved_node_index)
            return False
    # Otherwise, try to resolve by node_identifier (target text)
    elif node_identifier and not resolved_node_id:
        for idx, node in enumerate(nodes):
            node_text = node.get("text") if isinstance(node, dict) else str(node)
            if node_text and (node_identifier in node_text or node_text in node_identifier):
                resolved_node_index = idx
                resolved_node_id = node.get("id") if isinstance(node, dict) else f"context_{idx}"
                logger.debug(
                    "Resolved update_node by identifier '%s' to node_index=%d",
                    node_identifier,
                    idx,
                )
                break

    if resolved_node_id and resolved_node_index is not None:
        logger.info(
            "Updating node %d (%s) to: %s",
            resolved_node_index,
            resolved_node_id,
            target,
        )

        # Build update payload with diagram-specific fields
        update_payload = {"node_id": resolved_node_id, "new_text": target}

        # Add category if specified (for double bubble map, multi-flow map)
        category = command.get("category")
        if category:
            update_payload["category"] = category

        # Add left/right if specified (for bridge map analogies)
        left = command.get("left")
        right = command.get("right")
        if left and right:
            update_payload["left"] = left
            update_payload["right"] = right

        await safe_websocket_send(
            websocket,
            {
                "type": "diagram_update",
                "action": "update_nodes",
                "updates": [update_payload],
            },
        )

        # CRITICAL: Update session context immediately
        if 0 <= resolved_node_index < len(nodes):
            node = nodes[resolved_node_index]
            if isinstance(node, dict):
                node["text"] = target
                if "label" in node:
                    node["label"] = target
            else:
                nodes[resolved_node_index] = target

        # Update agent state and instructions
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        agent_session_id = get_agent_session_id(voice_session_id)
        agent = voice_agent_manager.get_or_create(agent_session_id)
        diagram_data = session_context.get("diagram_data", {})
        diagram_data["diagram_type"] = voice_sessions[voice_session_id].get("diagram_type")
        agent.update_diagram_state(diagram_data)

        updated_context = {
            "diagram_type": voice_sessions[voice_session_id].get("diagram_type"),
            "active_panel": voice_sessions[voice_session_id].get("active_panel", "none"),
            "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
            "selected_nodes": session_context.get("selected_nodes", []),
            "diagram_data": diagram_data,
        }
        new_instructions = build_voice_instructions(updated_context)
        # Only update instructions if WebSocket is still open
        try:
            omni_client = get_session_omni_client(voice_session_id)
            if omni_client:
                await omni_client.update_instructions(new_instructions)
        except (RuntimeError, ConnectionError, AttributeError) as e:
            if "close" in str(e).lower() or "closed" in str(e).lower():
                logger.debug("WebSocket closed, skipping instruction update: %s", e)
            else:
                raise

        logger.debug("Node updated: %d -> %s", resolved_node_index, target)
        return True

    logger.warning(
        "Could not resolve node for update: node_identifier=%s, node_index=%s",
        node_identifier,
        node_index,
    )
    return False
