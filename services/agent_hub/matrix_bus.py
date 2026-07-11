"""
Agent matrix bus — thin re-export of diagram_spine DiagramCommandBus.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.agent_hub.diagram_spine.bus import DiagramCommandBus, get_diagram_command_bus
from services.agent_hub.diagram_spine.origins import (
    DiagramCommandOrigin,
    register_channel_adapter,
)

__all__ = [
    "DiagramCommandBus",
    "DiagramCommandOrigin",
    "get_diagram_command_bus",
    "register_channel_adapter",
]
