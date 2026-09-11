"""Compatibility re-exports for ``clients.omni_client`` health checks.

Prefer ``services.kitty.agent_loop.ui_tools``. Qwen-Omni duplex is not used by Kitty.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from services.kitty.agent_loop.ui_tools import (
    build_omni_diagram_tools,
    build_ui_diagram_tools,
    omni_function_call_to_command,
    parse_node_index_from_identifier,
    ui_tool_call_to_command,
)

__all__ = [
    "build_omni_diagram_tools",
    "build_ui_diagram_tools",
    "omni_function_call_to_command",
    "parse_node_index_from_identifier",
    "ui_tool_call_to_command",
]
