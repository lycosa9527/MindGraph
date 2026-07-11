"""Kitty adapter — legacy voice command → DiagramCommandBus."""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.agent_hub.diagram_spine.bus import get_diagram_command_bus
from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.agent_hub.diagram_spine.types import DiagramCommandRequest, DiagramCommandResult


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
) -> DiagramCommandResult:
    """Map Kitty parsed command to bus request and apply."""
    request = DiagramCommandRequest(
        voice_session_id=voice_session_id,
        legacy_command=legacy_command,
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
