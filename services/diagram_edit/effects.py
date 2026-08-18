"""Build ExpectedEffect from command + before snapshot.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from services.diagram.mindmap_identity import is_leftover_mindmap_branch_id, is_machine_node_id
from services.diagram_edit.types import DiagramEditCommand, ExpectedEffect
from services.diagram_edit.verify import normalize_diagram_text

_INDEX_PHRASE_RE = re.compile(
    r"^(第\s*\d+\s*[个個支]|the\s+\d+(st|nd|rd|th)\b|\d+\s*$)",
    re.IGNORECASE,
)


def _normalized_text(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed if trimmed else None


def _snapshot_node_text(node: Dict[str, Any]) -> str:
    """Match verify._node_text: text, then data.label."""
    raw = node.get("text")
    if isinstance(raw, str) and raw.strip():
        return normalize_diagram_text(raw)
    data = node.get("data")
    if isinstance(data, dict):
        label = data.get("label")
        if isinstance(label, str):
            return normalize_diagram_text(label)
    return ""


def _is_index_phrase(value: str) -> bool:
    return bool(_INDEX_PHRASE_RE.match(value.strip()))


def _is_human_label_candidate(value: Optional[str]) -> bool:
    if not value:
        return False
    if is_machine_node_id(value):
        return False
    if value in ("topic", "center"):
        return False
    if _is_index_phrase(value):
        return False
    return True


def _snapshot_nodes(before_snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes_raw = before_snapshot.get("nodes")
    if not isinstance(nodes_raw, list):
        return []
    return [n for n in nodes_raw if isinstance(n, dict)]


def _label_from_snapshot_by_id(
    before_snapshot: Dict[str, Any],
    node_id: str,
) -> Optional[str]:
    wanted = node_id.strip()
    if not wanted:
        return None
    for node in _snapshot_nodes(before_snapshot):
        raw_id = node.get("id")
        if isinstance(raw_id, str) and raw_id.strip() == wanted:
            label = _snapshot_node_text(node)
            return label if label else None
    return None


def _label_match_count(before_snapshot: Dict[str, Any], label: str) -> int:
    want = normalize_diagram_text(label)
    if not want:
        return 0
    return sum(1 for node in _snapshot_nodes(before_snapshot) if _snapshot_node_text(node) == want)


def _resolve_delete_verify_label(
    args: Dict[str, Any],
    legacy: Dict[str, Any],
    before_snapshot: Dict[str, Any],
) -> Optional[str]:
    """
    Label used for delete ``node_absent`` verify.

    Prefer a stable ``node.id`` (UUID). Recycled positional ``branch-*`` ids
    are never used as the verify key — unique labels are used instead.
    """
    snapshot_nodes = _snapshot_nodes(before_snapshot)
    id_first = (
        _normalized_text(args.get("node_id")),
        _normalized_text(legacy.get("node_id")),
    )
    for raw_id in id_first:
        if raw_id and not is_leftover_mindmap_branch_id(raw_id) and _id_exists_in_snapshot(before_snapshot, raw_id):
            return raw_id

    human_candidates = (
        _normalized_text(legacy.get("target")),
        _normalized_text(legacy.get("node_label")),
        _normalized_text(args.get("target")),
        _normalized_text(args.get("node_label")),
    )
    for candidate in human_candidates:
        if not _is_human_label_candidate(candidate) or candidate is None:
            continue
        if not snapshot_nodes:
            return normalize_diagram_text(candidate)
        matches = _label_match_count(before_snapshot, candidate)
        if matches == 1:
            return normalize_diagram_text(candidate)
        if matches > 1:
            return None

    id_candidates = (
        _normalized_text(args.get("node_id")),
        _normalized_text(legacy.get("node_id")),
        _normalized_text(args.get("node_identifier")),
        _normalized_text(legacy.get("node_identifier")),
    )
    for raw_id in id_candidates:
        if not raw_id:
            continue
        if not is_leftover_mindmap_branch_id(raw_id) and _is_human_label_candidate(raw_id):
            if not snapshot_nodes:
                return normalize_diagram_text(raw_id)
            matches = _label_match_count(before_snapshot, raw_id)
            if matches == 1:
                return normalize_diagram_text(raw_id)
            if matches > 1:
                return None
            continue
        label = _label_from_snapshot_by_id(before_snapshot, raw_id)
        if not label:
            continue
        if _label_match_count(before_snapshot, label) == 1:
            return label
        return None

    return None


def _id_exists_in_snapshot(before_snapshot: Dict[str, Any], node_id: str) -> bool:
    wanted = node_id.strip()
    return any(
        isinstance(node.get("id"), str) and node.get("id") == wanted for node in _snapshot_nodes(before_snapshot)
    )


def build_expected_effect(
    command: DiagramEditCommand,
    before_snapshot: Dict[str, Any],
) -> ExpectedEffect:
    """Derive postcondition checklist for a mindmap edit command."""
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
        side = _normalized_text(args.get("side")) or _normalized_text(legacy.get("side"))

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
            _normalized_text(args.get("node_id"))
            or _normalized_text(legacy.get("node_id"))
            or _normalized_text(args.get("node_identifier"))
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
        verify_label = _resolve_delete_verify_label(args, legacy, before_snapshot)
        checks = ["no_dangling_edges", "tree_rooted_at_topic"]
        if verify_label:
            checks = ["node_absent", *checks]
        return ExpectedEffect(
            op="delete_node",
            node_identifier=verify_label,
            checks=checks,
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
