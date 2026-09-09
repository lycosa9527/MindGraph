"""Kitty adapter — legacy voice command → DiagramCommandBus."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.agent_hub.diagram_spine.bus import get_diagram_command_bus
from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.agent_hub.diagram_spine.types import DiagramCommandRequest, DiagramCommandResult
from services.diagram_edit.pending import new_mutation_id
from services.diagram_edit.types import ToolResult
from services.kitty.routing.command_grounding import UNGROUNDED_ERROR, apply_command_grounding
from services.kitty.routing.diagram_agent_context import enrich_node_action_command


async def apply_kitty_legacy_diagram_command(
    websocket: WebSocket,
    voice_session_id: str,
    legacy_command: Dict[str, Any],
    session_context: Dict[str, Any],
    *,
    scope: str,
    diagram_type: str,
    user_id: Optional[int] = None,
    idempotency_key: Optional[str] = None,
    verify_required: bool = True,
    origin: DiagramCommandOrigin = DiagramCommandOrigin.KITTY_MOBILE,
    user_text: str = "",
    grounding_source: str = "",
) -> DiagramCommandResult:
    """Enrich, ground the user turn, then map to the bus. Refuse ungrounded writes."""
    command = enrich_node_action_command(legacy_command, session_context)
    decision = apply_command_grounding(
        command,
        user_text=user_text,
        session_context=session_context,
        source=grounding_source,
    )
    if not decision.allowed:
        return DiagramCommandResult(
            tool_result=ToolResult(
                status="rejected",
                mutation_id=new_mutation_id(),
                error_code=UNGROUNDED_ERROR,
                message=decision.reason,
            ),
            origin=origin,
        )
    request = DiagramCommandRequest(
        voice_session_id=voice_session_id,
        legacy_command=command,
        session_context=session_context,
        scope=scope,
        diagram_type=diagram_type,
        user_id=user_id,
        idempotency_key=idempotency_key,
        source_agent="kitty",
        origin=origin,
        verify_required=verify_required,
    )
    bus = get_diagram_command_bus()
    return await bus.apply(websocket, request)
