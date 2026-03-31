"""Dispatch diagram update actions from voice commands."""

from typing import Any, Dict

from fastapi import WebSocket

from routers.features.voice.diagram_add import voice_apply_add_node_action
from routers.features.voice.diagram_delete import voice_apply_delete_node_action
from routers.features.voice.diagram_handlers import (
    _handle_update_center_action,
    _handle_update_node_action,
)
from routers.features.voice.state import logger


async def execute_diagram_update(
    websocket: WebSocket,
    voice_session_id: str,
    action: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
) -> bool:
    """
    Execute a diagram update action (update_center, update_node, add_node, delete_node).
    Returns True if update was executed, False otherwise.
    """
    target = command.get("target")
    node_index = command.get("node_index")
    node_identifier = command.get("node_identifier")

    try:
        if action == "update_center":
            return await _handle_update_center_action(websocket, voice_session_id, command, session_context, target)

        if action == "update_node" and target:
            return await _handle_update_node_action(
                websocket,
                voice_session_id,
                command,
                session_context,
                target,
                node_index,
                node_identifier,
            )

        if action == "add_node":
            return await voice_apply_add_node_action(websocket, voice_session_id, command, session_context)

        if action == "delete_node":
            return await voice_apply_delete_node_action(
                websocket,
                voice_session_id,
                command,
                session_context,
                target,
                node_index,
                node_identifier,
            )

        return False

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Diagram update execution error: %s", e, exc_info=True)
        return False
