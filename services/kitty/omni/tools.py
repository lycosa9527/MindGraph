"""Omni realtime tool schemas for diagram voice intents.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.diagram_edit.schema import diagram_edit_function_call_to_legacy_command
from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import (
    normalize_voice_desktop_canvas_diagram_type,
)


def build_omni_diagram_tools() -> List[Dict[str, Any]]:
    """OpenAI-compatible tool definitions for Omni ``session.update``."""

    def fn(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
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

    return [
        fn(
            "update_center",
            "Update the diagram center/topic/title.",
            {
                "new_text": {"type": "string", "description": "New center text"},
                "left": {"type": "string", "description": "Left topic for double bubble map"},
                "right": {"type": "string", "description": "Right topic for double bubble map"},
            },
            [],
        ),
        fn(
            "add_node",
            "Add or insert a node on the diagram.",
            {
                "text": {"type": "string", "description": "Node text"},
                "position": {"type": "integer", "description": "0-based insert index"},
            },
            ["text"],
        ),
        fn(
            "update_node",
            "Update an existing node's text.",
            {
                "node_identifier": {"type": "string", "description": "Node text or index label"},
                "new_text": {"type": "string", "description": "New node text"},
            },
            ["node_identifier", "new_text"],
        ),
        fn(
            "delete_node",
            "Delete a node by text or index.",
            {
                "node_identifier": {"type": "string", "description": "Node text or index label"},
            },
            ["node_identifier"],
        ),
        fn(
            "select_node",
            "Select/highlight a node.",
            {"node_identifier": {"type": "string", "description": "Node text or index"}},
            ["node_identifier"],
        ),
        fn(
            "auto_complete",
            "Trigger AI auto-complete for the entire diagram (fill branches/attributes/steps).",
            {},
            [],
        ),
        fn(
            "start_inline_recommendations",
            (
                "Show Tab-style inline AI suggestions for one node. Use when the user asks for "
                "ideas, suggestions, or recommendations for a node (联想, 推荐, 建议). "
                "Omit node_identifier when they mean the currently selected node."
            ),
            {
                "node_identifier": {
                    "type": "string",
                    "description": "Node text, spoken index (第一个), or id; omit for selection",
                },
            },
            [],
        ),
        fn(
            "add_node_with_recommendations",
            (
                "Add ONE new node on the canvas, then show inline AI suggestions so the user can "
                "pick the best label (e.g. 增加一个节点并给出一些建议, add a node with suggestions). "
                "Optional text seeds the placeholder; omit text to use a blank/new-node placeholder."
            ),
            {
                "text": {
                    "type": "string",
                    "description": "Optional placeholder label for the new node",
                },
            },
            [],
        ),
        fn(
            "explain_node",
            (
                "Explain a diagram node's concept via MindMate (解释/讲解). "
                "Provide node_identifier unless the selected node is meant."
            ),
            {
                "node_identifier": {
                    "type": "string",
                    "description": "Node text, spoken index, or id; omit for selection",
                },
            },
            [],
        ),
        fn(
            "ask_mindmate",
            "Send a free-form question to the MindMate assistant panel.",
            {
                "message": {"type": "string", "description": "Question for MindMate"},
            },
            ["message"],
        ),
        fn(
            "open_panel",
            "Open a UI panel (mindmate or node_palette).",
            {"panel_name": {"type": "string", "description": "mindmate or node_palette"}},
            ["panel_name"],
        ),
        fn(
            "close_panel",
            "Close a panel or all panels.",
            {"panel_name": {"type": "string", "description": "Panel name or all"}},
            ["panel_name"],
        ),
        fn(
            "open_desktop_canvas",
            (
                "Open a new blank diagram on the paired desktop browser. Use when the user "
                "asks to create or open a diagram on the computer/desktop/PC, or from mobile "
                "Kitty to start a new canvas (e.g. 新建思维导图, 在电脑打开气泡图)."
            ),
            {
                "diagram_type": {
                    "type": "string",
                    "description": (
                        "Diagram slug (mindmap, bubble_map, circle_map, …) or Chinese label (思维导图, 气泡图, …)"
                    ),
                },
                "target": {
                    "type": "string",
                    "description": "Optional center/title for single-topic diagrams",
                },
                "left": {
                    "type": "string",
                    "description": "Left topic for double_bubble_map comparisons",
                },
                "right": {
                    "type": "string",
                    "description": "Right topic for double_bubble_map comparisons",
                },
            },
            ["diagram_type"],
        ),
    ]


def omni_function_call_to_command(name: str, arguments_json: str) -> Dict[str, Any]:
    """Map Omni function call to legacy command dict used by diagram_execute."""
    diagram_tool = name if name.startswith("diagram.") else f"diagram.{name}"
    if name in ("update_center", "add_node", "update_node", "delete_node") or name.startswith("diagram."):
        mapped = diagram_edit_function_call_to_legacy_command(diagram_tool, arguments_json)
        act = mapped.get("action")
        if act == "add_node" and mapped.get("target"):
            return mapped
        if act == "update_node" and mapped.get("target"):
            return mapped
        if act == "delete_node" and (mapped.get("target") or mapped.get("node_index") is not None):
            return mapped
        if act == "update_center" and mapped.get("target"):
            return mapped

    try:
        args = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}

    if name == "update_center":
        left = args.get("left")
        right = args.get("right")
        new_text = args.get("new_text") or args.get("target")
        cmd: Dict[str, Any] = {"action": "update_center", "confidence": 0.95}
        if isinstance(left, str) and isinstance(right, str) and left.strip() and right.strip():
            cmd["left"] = left.strip()
            cmd["right"] = right.strip()
            cmd["target"] = f"{left.strip()} vs {right.strip()}"
        elif isinstance(new_text, str) and new_text.strip():
            cmd["target"] = new_text.strip()
        return cmd

    if name == "add_node":
        text = args.get("text") or args.get("target")
        cmd = {"action": "add_node", "confidence": 0.95}
        if isinstance(text, str):
            cmd["target"] = text.strip()
        pos = args.get("position")
        if isinstance(pos, int):
            cmd["node_index"] = pos
        return cmd

    if name == "update_node":
        return {
            "action": "update_node",
            "node_identifier": args.get("node_identifier"),
            "target": args.get("new_text") or args.get("target"),
            "confidence": 0.95,
        }

    if name == "delete_node":
        ident = args.get("node_identifier") or args.get("target")
        cmd = {"action": "delete_node", "confidence": 0.95}
        if isinstance(ident, str):
            cmd["target"] = ident.strip()
        if isinstance(ident, int):
            cmd["node_index"] = ident
        return cmd

    if name == "select_node":
        ident = args.get("node_identifier") or args.get("target")
        return {"action": "select_node", "target": ident, "confidence": 0.95}

    if name == "auto_complete":
        return {"action": "auto_complete", "confidence": 0.95}

    if name == "start_inline_recommendations":
        ident = args.get("node_identifier") or args.get("target")
        cmd = {"action": "start_inline_recommendations", "confidence": 0.95}
        if isinstance(ident, str) and ident.strip():
            cmd["node_identifier"] = ident.strip()
        return cmd

    if name == "add_node_with_recommendations":
        text = args.get("text") or args.get("target")
        cmd = {"action": "add_node_with_recommendations", "confidence": 0.95}
        if isinstance(text, str) and text.strip():
            cmd["target"] = text.strip()
        return cmd

    if name == "explain_node":
        ident = args.get("node_identifier") or args.get("target")
        cmd = {"action": "explain_node", "confidence": 0.95}
        if isinstance(ident, str) and ident.strip():
            cmd["node_identifier"] = ident.strip()
        return cmd

    if name == "ask_mindmate":
        message = args.get("message") or args.get("target")
        cmd = {"action": "ask_mindmate", "confidence": 0.95}
        if isinstance(message, str) and message.strip():
            cmd["target"] = message.strip()
        return cmd

    if name == "open_panel":
        panel = args.get("panel_name") or args.get("panel")
        return {"action": "open_panel", "target": panel, "confidence": 0.95}

    if name == "close_panel":
        panel = args.get("panel_name") or args.get("panel") or "all"
        if str(panel).lower() == "all":
            return {"action": "close_all_panels", "confidence": 0.95}
        return {"action": "close_panel", "target": panel, "confidence": 0.95}

    if name == "open_desktop_canvas":
        raw_dt = args.get("diagram_type")
        slug = normalize_voice_desktop_canvas_diagram_type(raw_dt if isinstance(raw_dt, str) else None)
        cmd = {"action": "open_desktop_canvas", "confidence": 0.95}
        if slug is not None:
            cmd["diagram_type"] = slug
        elif isinstance(raw_dt, str) and raw_dt.strip():
            cmd["diagram_type"] = raw_dt.strip()
        target = args.get("target")
        if isinstance(target, str) and target.strip():
            cmd["target"] = target.strip()
        left = args.get("left")
        if isinstance(left, str) and left.strip():
            cmd["left"] = left.strip()
        right = args.get("right")
        if isinstance(right, str) and right.strip():
            cmd["right"] = right.strip()
        return cmd

    return {"action": "none", "confidence": 0.0}


def parse_node_index_from_identifier(raw: Optional[str]) -> Optional[int]:
    """Parse node index from identifier."""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text.isdigit():
        idx = int(text)
        return idx - 1 if idx >= 1 else idx
    mapping = {
        "first": 0,
        "second": 1,
        "third": 2,
        "fourth": 3,
        "第一个": 0,
        "第二个": 1,
        "第三个": 2,
        "第一": 0,
        "第二": 1,
        "第三": 2,
    }
    for key, idx in mapping.items():
        if key in text:
            return idx
    return None
