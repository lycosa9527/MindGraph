"""Diagram command spine — Bus front door for agent diagram mutations."""

from services.agent_hub.diagram_spine.bus import DiagramCommandBus, get_diagram_command_bus
from services.agent_hub.diagram_spine.origins import (
    DiagramCommandOrigin,
    register_channel_adapter,
)
from services.agent_hub.diagram_spine.types import DiagramCommandRequest, DiagramCommandResult

__all__ = [
    "DiagramCommandBus",
    "DiagramCommandOrigin",
    "DiagramCommandRequest",
    "DiagramCommandResult",
    "get_diagram_command_bus",
    "register_channel_adapter",
]
