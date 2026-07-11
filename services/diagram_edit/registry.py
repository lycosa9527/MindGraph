"""Tool name → dispatch handler registry.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import WebSocket

from services.diagram_edit.types import DiagramEditCommand

DispatchHandler = Callable[
    [WebSocket, str, DiagramEditCommand, Dict[str, Any]],
    Awaitable[bool],
]

_REGISTRY: Dict[str, DispatchHandler] = {}


def register_handler(tool: str, handler: DispatchHandler) -> None:
    """Register a dispatch handler for a tool name."""
    _REGISTRY[tool] = handler


def get_handler(tool: str) -> Optional[DispatchHandler]:
    """Return handler for tool or None."""
    return _REGISTRY.get(tool)


async def dispatch_tool(
    websocket: WebSocket,
    voice_session_id: str,
    command: DiagramEditCommand,
    session_context: Dict[str, Any],
) -> bool:
    """Dispatch a registered tool handler."""
    handler = get_handler(command.tool)
    if handler is None:
        return False
    return await handler(websocket, voice_session_id, command, session_context)
