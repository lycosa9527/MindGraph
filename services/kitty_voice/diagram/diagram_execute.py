"""Dispatch diagram update actions from voice commands."""

from typing import Any, Dict

from fastapi import WebSocket

from services.kitty_voice.diagram.diagram_add import voice_apply_add_node_action
from services.kitty_voice.diagram.diagram_delete import voice_apply_delete_node_action
from services.kitty_voice.diagram.diagram_handlers import (
    _handle_update_center_action,
    _handle_update_node_action,
)
from services.kitty_voice.diagram_voice_hub_bridge import try_sync_voice_diagram_to_hub
from services.kitty_voice.runtime_state import logger


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
        executed = False
        if action == "update_center":
            executed = await _handle_update_center_action(
                websocket, voice_session_id, command, session_context, target
            )

        elif action == "update_node" and target:
            executed = await _handle_update_node_action(
                websocket,
                voice_session_id,
                command,
                session_context,
                target,
                node_index,
                node_identifier,
            )

        elif action == "add_node":
            executed = await voice_apply_add_node_action(websocket, voice_session_id, command, session_context)

        elif action == "delete_node":
            executed = await voice_apply_delete_node_action(
                websocket,
                voice_session_id,
                command,
                session_context,
                target,
                node_index,
                node_identifier,
            )

        else:
            return False

        palette_only = action == "add_node" and not command.get("target")
        if executed and not palette_only:
            await try_sync_voice_diagram_to_hub(voice_session_id)

        return executed

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Diagram update execution error: %s", e, exc_info=True)
        return False
