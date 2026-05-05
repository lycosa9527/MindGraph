"""MindGraph Agent Hub — orchestration for multi-channel agents (P0: Kitty voice scope)."""

from services.agent_hub.matrix_bus import (
    DiagramCommandBus,
    DiagramCommandOrigin,
    get_diagram_command_bus,
)
from services.agent_hub.scope_lifecycle import (
    MindGraphAgentHub,
    configure_kitty_control_state,
    configure_kitty_voice_cleanup,
    get_mind_graph_agent_hub,
    handle_kitty_control_dispatch,
)
from services.agent_hub.snapshot import build_desktop_pairing_snapshot

__all__ = [
    "DiagramCommandBus",
    "DiagramCommandOrigin",
    "MindGraphAgentHub",
    "build_desktop_pairing_snapshot",
    "configure_kitty_control_state",
    "configure_kitty_voice_cleanup",
    "get_diagram_command_bus",
    "get_mind_graph_agent_hub",
    "handle_kitty_control_dispatch",
]
