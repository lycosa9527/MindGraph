"""Diagram command spine request/result envelopes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.agent_hub.diagram_spine.origins import DiagramCommandOrigin
from services.diagram_edit.types import ToolResult


@dataclass(slots=True)
class DiagramCommandRequest:
    """Front-door mutation request from any channel adapter."""

    voice_session_id: str
    legacy_command: Dict[str, Any]
    session_context: Dict[str, Any]
    scope: str
    diagram_type: str
    user_id: Optional[int] = None
    idempotency_key: Optional[str] = None
    source_agent: str = "kitty"
    origin: DiagramCommandOrigin = DiagramCommandOrigin.KITTY_MOBILE
    verify_required: bool = True


@dataclass(slots=True)
class DiagramCommandResult:
    """Bus result wrapping executor ToolResult and hub trace fields."""

    tool_result: ToolResult
    hub_revision: Optional[int] = None
    origin: DiagramCommandOrigin = DiagramCommandOrigin.KITTY_MOBILE

    @property
    def edit_mutation_id(self) -> str:
        """Mutation id from the diagram edit tool."""
        return self.tool_result.mutation_id

    @property
    def applied(self) -> bool:
        """True when canvas verification (and hub persist when required) succeeded."""
        return self.tool_result.status == "applied"
