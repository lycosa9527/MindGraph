"""Mindmap dispatch handlers behind diagram_edit registry.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import WebSocket

from services.diagram_edit.registry import register_handler
from services.diagram_edit.types import DiagramEditCommand
from services.kitty.diagram.diagram_execute import execute_diagram_update


async def dispatch_mindmap_legacy(
    websocket: WebSocket,
    voice_session_id: str,
    command: DiagramEditCommand,
    session_context: Dict[str, Any],
) -> bool:
    """Delegate to legacy Kitty diagram_execute (WS extras stashed on voice session)."""
    legacy = command.legacy_command
    if not isinstance(legacy, dict):
        return False
    action = legacy.get("action")
    if not isinstance(action, str):
        return False

    return await execute_diagram_update(
        websocket,
        voice_session_id,
        action,
        legacy,
        session_context,
    )


def register_mindmap_handlers() -> None:
    """Register mindmap handlers for all v1 structural tools."""

    async def _handler(
        websocket: WebSocket,
        voice_session_id: str,
        command: DiagramEditCommand,
        session_context: Dict[str, Any],
    ) -> bool:
        return await dispatch_mindmap_legacy(
            websocket,
            voice_session_id,
            command,
            session_context,
        )

    for tool in (
        "diagram.update_center",
        "diagram.add_node",
        "diagram.update_node",
        "diagram.delete_node",
    ):
        register_handler(tool, _handler)
