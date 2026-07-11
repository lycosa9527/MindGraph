"""Legacy command ↔ DiagramEditCommand conversion.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.diagram_edit.schema import diagram_edit_function_call_to_legacy_command
from services.diagram_edit.types import LEGACY_ACTION_TO_TOOL, DiagramEditCommand


def legacy_command_to_diagram_edit(
    legacy: Dict[str, Any],
    *,
    scope: str,
    diagram_type: str,
    expected_revision: Optional[int] = None,
    idempotency_key: Optional[str] = None,
    source_agent: str = "kitty",
) -> Optional[DiagramEditCommand]:
    """Convert legacy Kitty command dict to DiagramEditCommand."""
    action = legacy.get("action")
    if not isinstance(action, str):
        return None
    tool = LEGACY_ACTION_TO_TOOL.get(action)
    if tool is None:
        return None

    args: Dict[str, Any] = {}
    if tool == "diagram.update_center":
        target = legacy.get("target") or legacy.get("new_text")
        if isinstance(target, str):
            args["new_text"] = target.strip()
    elif tool == "diagram.add_node":
        target = legacy.get("target")
        if isinstance(target, str):
            args["text"] = target.strip()
        for key in ("parent_ref", "side", "branch_index", "child_index", "node_index"):
            if key in legacy:
                args[key] = legacy[key]
    elif tool == "diagram.update_node":
        ident = legacy.get("node_identifier")
        new_text = legacy.get("target") or legacy.get("new_text")
        if isinstance(ident, str):
            args["node_identifier"] = ident.strip()
        if isinstance(new_text, str):
            args["new_text"] = new_text.strip()
    elif tool == "diagram.delete_node":
        ident = legacy.get("node_identifier") or legacy.get("target")
        if isinstance(ident, str):
            args["node_identifier"] = ident.strip()
        if isinstance(legacy.get("node_index"), int):
            args["node_index"] = legacy["node_index"]

    return DiagramEditCommand(
        tool=tool,
        args=args,
        scope=scope,
        diagram_type=diagram_type,
        expected_revision=expected_revision,
        idempotency_key=idempotency_key,
        source_agent=source_agent,
        legacy_action=action,
        legacy_command=dict(legacy),
    )


def diagram_edit_tool_from_function_call(name: str, arguments_json: str) -> Optional[DiagramEditCommand]:
    """Build DiagramEditCommand from OpenAI function call (partial; scope filled later)."""
    legacy = diagram_edit_function_call_to_legacy_command(name, arguments_json)
    action = legacy.get("action")
    if not isinstance(action, str) or action == "none":
        return None
    return legacy_command_to_diagram_edit(
        legacy,
        scope="",
        diagram_type="mindmap",
        source_agent="kitty",
    )
