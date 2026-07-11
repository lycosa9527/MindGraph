"""MindGraph Agent Hub — orchestration for multi-channel agents (P0: Kitty voice scope).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Import scope_lifecycle before matrix_bus / diagram_spine so callers that reach
# get_mind_graph_agent_hub via this package during bus bootstrap do not hit a
# partially-initialized circular import.
from services.agent_hub.scope_lifecycle import (
    MindGraphAgentHub,
    configure_kitty_control_state,
    configure_kitty_scope_cleanup,
    get_mind_graph_agent_hub,
)
from services.agent_hub.matrix_bus import (
    DiagramCommandBus,
    DiagramCommandOrigin,
    get_diagram_command_bus,
)
from services.agent_hub.diagram_spine.origins import register_channel_adapter
from services.kitty.infra.control.kitty_control_fanout import handle_kitty_control_dispatch
from services.agent_hub.snapshot import build_desktop_pairing_snapshot

register_channel_adapter("mindmate")

__all__ = [
    "DiagramCommandBus",
    "DiagramCommandOrigin",
    "MindGraphAgentHub",
    "build_desktop_pairing_snapshot",
    "configure_kitty_control_state",
    "configure_kitty_scope_cleanup",
    "get_diagram_command_bus",
    "get_mind_graph_agent_hub",
    "handle_kitty_control_dispatch",
    "register_channel_adapter",
]
