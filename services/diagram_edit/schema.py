"""OpenAI-compatible tool definitions for diagram structural edits.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List


def _fn(
    name: str,
    description: str,
    properties: Dict[str, Any],
    required: List[str],
) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def get_diagram_edit_tools() -> List[Dict[str, Any]]:
    """Return v1 mindmap structural edit tools (agent-agnostic)."""
    return [
        _fn(
            "diagram.update_center",
            "Update the mind map center topic text.",
            {
                "new_text": {"type": "string", "description": "New center/topic text"},
            },
            ["new_text"],
        ),
        _fn(
            "diagram.add_node",
            "Add a branch or child node on a mind map.",
            {
                "text": {"type": "string", "description": "Node label text"},
                "parent_ref": {
                    "type": "string",
                    "description": "Parent node id or label; omit for top-level branch under topic",
                },
                "side": {
                    "type": "string",
                    "enum": ["left", "right"],
                    "description": "Branch side when adding under topic (default right)",
                },
                "branch_index": {
                    "type": "integer",
                    "description": "0-based top-level branch index for child insert",
                },
                "child_index": {
                    "type": "integer",
                    "description": "0-based child index under branch_index",
                },
            },
            ["text"],
        ),
        _fn(
            "diagram.update_node",
            "Update an existing mind map node label.",
            {
                "node_identifier": {
                    "type": "string",
                    "description": "Node id from diagram JSON (preferred) or label/index",
                },
                "new_text": {"type": "string", "description": "New node text"},
            },
            ["node_identifier", "new_text"],
        ),
        _fn(
            "diagram.delete_node",
            "Delete a mind map node by text or index.",
            {
                "node_identifier": {
                    "type": "string",
                    "description": "Node id from diagram JSON (preferred) or label/index",
                },
            },
            ["node_identifier"],
        ),
    ]


def diagram_edit_function_call_to_legacy_command(
    name: str,
    arguments_json: str,
) -> Dict[str, Any]:
    """Map diagram_edit tool call to legacy Kitty command dict."""
    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}

    if name == "diagram.update_center":
        new_text = args.get("new_text") or args.get("target")
        cmd: Dict[str, Any] = {"action": "update_center", "confidence": 0.95}
        if isinstance(new_text, str) and new_text.strip():
            cmd["target"] = new_text.strip()
        return cmd

    if name == "diagram.add_node":
        text = args.get("text") or args.get("target")
        cmd = {"action": "add_node", "confidence": 0.95}
        if isinstance(text, str):
            cmd["target"] = text.strip()
        parent = args.get("parent_ref")
        if isinstance(parent, str) and parent.strip():
            cmd["parent_ref"] = parent.strip()
        side = args.get("side")
        if isinstance(side, str) and side.strip():
            cmd["side"] = side.strip().lower()
        branch_idx = args.get("branch_index")
        if isinstance(branch_idx, int):
            cmd["branch_index"] = branch_idx
        child_idx = args.get("child_index")
        if isinstance(child_idx, int):
            cmd["child_index"] = child_idx
        pos = args.get("position") or args.get("node_index")
        if isinstance(pos, int):
            cmd["node_index"] = pos
        return cmd

    if name == "diagram.update_node":
        return {
            "action": "update_node",
            "node_identifier": args.get("node_identifier"),
            "target": args.get("new_text") or args.get("target"),
            "confidence": 0.95,
        }

    if name == "diagram.delete_node":
        ident = args.get("node_identifier") or args.get("target")
        cmd = {"action": "delete_node", "confidence": 0.95}
        if isinstance(ident, str):
            cmd["target"] = ident.strip()
        if isinstance(ident, int):
            cmd["node_index"] = ident
        return cmd

    return {"action": "none", "confidence": 0.0}
