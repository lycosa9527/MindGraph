"""Shared finalize path for paragraph batch diagram node adds."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from fastapi import WebSocket

from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.diagram.diagram_spec_sync import sync_diagram_data_to_spec_shape
from services.kitty.diagram.hub_bridge import try_sync_voice_diagram_to_hub
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.session.runtime_state import logger, voice_sessions
from services.kitty.session.events import emit_diagram_mutated
from services.kitty.session.ops import get_agent_session_id, persist_voice_session_context


async def apply_paragraph_batch_add_nodes(
    websocket: WebSocket,
    voice_session_id: str,
    session_context: Dict[str, Any],
    nodes_to_add: List[Dict[str, Any]],
    *,
    log_label: str,
) -> bool:
    """
    Send batch ``add_nodes`` to the client, persist session context, sync hub, refresh Omni.

    Returns True when nodes were applied.
    """
    if not nodes_to_add:
        return False

    await safe_websocket_send(
        websocket,
        {
            "type": "diagram_update",
            "action": "add_nodes",
            "updates": nodes_to_add,
        },
    )

    if "diagram_data" not in session_context:
        session_context["diagram_data"] = {}
    diagram_data = session_context["diagram_data"]
    if not isinstance(diagram_data, dict):
        diagram_data = {}
        session_context["diagram_data"] = diagram_data

    children = diagram_data.get("children")
    if not isinstance(children, list):
        children = []
        diagram_data["children"] = children

    for node in nodes_to_add:
        if not isinstance(node, dict):
            continue
        entry: Dict[str, Any] = {"text": str(node.get("text") or "").strip()}
        category = node.get("category")
        if isinstance(category, str) and category.strip():
            entry["category"] = category.strip()
        left = node.get("left")
        right = node.get("right")
        if isinstance(left, str) and left.strip() and isinstance(right, str) and right.strip():
            entry["left"] = left.strip()
            entry["right"] = right.strip()
        if entry.get("text"):
            children.append(entry)

    session = voice_sessions.get(voice_session_id)
    diagram_type = "circle_map"
    if session is not None:
        diagram_type = str(session.get("diagram_type") or diagram_type)
    diagram_data["diagram_type"] = diagram_type
    sync_diagram_data_to_spec_shape(diagram_type, diagram_data)

    persist_voice_session_context(voice_session_id, session_context)

    agent = kitty_agent_manager.get_or_create(get_agent_session_id(voice_session_id))
    agent.update_diagram_state(copy.deepcopy(diagram_data))

    await emit_diagram_mutated(voice_session_id, action="paragraph_batch", delta=log_label)
    await try_sync_voice_diagram_to_hub(voice_session_id)

    logger.debug("Paragraph batch added %d nodes (%s)", len(nodes_to_add), log_label)
    return True
