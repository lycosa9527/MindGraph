"""Build ExpectedEffect from command + before snapshot.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.diagram_edit.types import DiagramEditCommand, ExpectedEffect


def _normalized_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def build_expected_effect(
    command: DiagramEditCommand,
    before_snapshot: Dict[str, Any],
) -> ExpectedEffect:
    """Derive postcondition checklist for a mindmap edit command."""
    _ = before_snapshot
    tool = command.tool
    args = command.args
    legacy = command.legacy_command or {}

    if tool == "diagram.update_center":
        text = (
            _normalized_text(args.get("new_text"))
            or _normalized_text(legacy.get("target"))
            or _normalized_text(legacy.get("new_text"))
        )
        return ExpectedEffect(
            op="update_center",
            text=text,
            parent_ref="topic",
            checks=["topic_text_matches", "single_topic"],
        )

    if tool == "diagram.add_node":
        text = _normalized_text(args.get("text")) or _normalized_text(legacy.get("target"))
        parent_ref = _normalized_text(args.get("parent_ref"))
        branch_idx = args.get("branch_index")
        if not isinstance(branch_idx, int):
            branch_idx = legacy.get("branch_index")
        child_idx = args.get("child_index")
        if not isinstance(child_idx, int):
            child_idx = legacy.get("child_index")
        side = _normalized_text(args.get("side")) or _normalized_text(legacy.get("side")) or "right"

        if branch_idx is not None and child_idx is not None:
            return ExpectedEffect(
                op="add_child",
                text=text,
                parent_ref=str(branch_idx),
                checks=[
                    "node_exists",
                    "text_matches",
                    "parent_edge_exists",
                    "delta_nodes",
                ],
            )

        # Non-topic parent_ref means child under an existing branch (label or id).
        if parent_ref and parent_ref not in ("topic", "center"):
            return ExpectedEffect(
                op="add_child",
                text=text,
                parent_ref=parent_ref,
                checks=[
                    "node_exists",
                    "text_matches",
                    "parent_edge_exists",
                    "delta_nodes",
                ],
            )

        return ExpectedEffect(
            op="add_branch",
            text=text,
            parent_ref=parent_ref or "topic",
            side=side,
            checks=[
                "node_exists",
                "text_matches",
                "parent_edge_exists",
                "delta_nodes",
                "single_topic",
            ],
        )

    if tool == "diagram.update_node":
        ident = (
            _normalized_text(args.get("node_identifier"))
            or _normalized_text(legacy.get("node_identifier"))
            or _normalized_text(legacy.get("target"))
        )
        text = _normalized_text(args.get("new_text")) or _normalized_text(legacy.get("target"))
        return ExpectedEffect(
            op="update_node",
            text=text,
            node_identifier=ident,
            checks=["node_exists", "text_matches", "node_count_unchanged"],
        )

    if tool == "diagram.delete_node":
        ident = (
            _normalized_text(args.get("node_identifier"))
            or _normalized_text(legacy.get("node_identifier"))
            or _normalized_text(legacy.get("target"))
        )
        return ExpectedEffect(
            op="delete_node",
            node_identifier=ident,
            checks=["node_absent", "no_dangling_edges", "tree_rooted_at_topic"],
        )

    return ExpectedEffect(op="unknown", checks=[])


def extract_before_fingerprint(session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Capture pre-apply nodes/connections fingerprint from session context."""
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        return {"nodes": [], "connections": []}

    nodes_raw = diagram_data.get("nodes")
    connections_raw = diagram_data.get("connections")
    nodes = nodes_raw if isinstance(nodes_raw, list) else []
    connections = connections_raw if isinstance(connections_raw, list) else []

    if nodes or connections:
        return {"nodes": list(nodes), "connections": list(connections)}

    children = diagram_data.get("children")
    center = diagram_data.get("center")
    topic_text = ""
    if isinstance(center, dict):
        topic_text = str(center.get("text") or "")
    return {
        "topic": topic_text,
        "children": list(children) if isinstance(children, list) else [],
        "format": "kitty_children",
    }


def refresh_session_diagram_data_from_evidence(
    session_context: Dict[str, Any],
    evidence: Dict[str, Any],
) -> None:
    """
    Patch session ``diagram_data`` from a verified canvas ack evidence snapshot.

    Required for sequential multi-mutation turns so the next apply's
    ``before_fingerprint`` matches the post-apply canvas.
    """
    nodes = evidence.get("nodes")
    if not isinstance(nodes, list):
        return
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        diagram_data = {}
        session_context["diagram_data"] = diagram_data
    diagram_data["nodes"] = list(nodes)
    connections = evidence.get("connections")
    if isinstance(connections, list):
        diagram_data["connections"] = list(connections)
