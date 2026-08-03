"""
Process-local flag: whether MindGraph MCP Streamable HTTP was mounted.

Used by the host lifespan to decide whether to enter ``session_manager.run()``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations


class _McpMountState:
    """Holder for process-wide MCP mount flag."""

    mounted: bool = False


def mark_mindgraph_mcp_mounted() -> None:
    """Record that ``mount_mindgraph_mcp`` completed successfully."""
    _McpMountState.mounted = True


def is_mindgraph_mcp_mounted() -> bool:
    """Return True when MCP Streamable HTTP was mounted in this process."""
    return _McpMountState.mounted


def reset_mindgraph_mcp_mounted_for_tests() -> None:
    """Reset mount flag (unit tests only)."""
    _McpMountState.mounted = False
