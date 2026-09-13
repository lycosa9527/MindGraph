"""Resolve lesson-frame focus to mind-map node ids for canvas sync."""

from __future__ import annotations

from typing import Any

from services.mind_classroom.outline import MindMapOutline


def resolve_frame_focus_node_ids(
    outline: MindMapOutline,
    *,
    slide_index: int,
    batch_role: str = "",
    focus_branch: Any = None,
) -> list[str]:
    """
    Map a planner frame to canvas focus node ids.

    - Slide 0 (topic overview) always returns ``[]`` → fit whole diagram.
    - Empty / open-overview frames also return ``[]``.
    - Branch frames return the matched first-level branch id (FE expands children).
    """
    if slide_index <= 0:
        return []

    hint = str(focus_branch or "").strip()
    role = (batch_role or "").strip().lower()
    if not hint:
        # No branch cue — keep whole-map framing (open/close or ambiguous).
        return []

    hint_lower = hint.lower()
    for branch in outline.branches:
        branch_id = (branch.id or "").strip()
        text = (branch.text or "").strip()
        if branch_id and (branch_id == hint or branch_id.lower() == hint_lower):
            return [branch_id]
        if text and (text == hint or text.lower() == hint_lower):
            return [branch_id] if branch_id else []

    for branch in outline.branches:
        branch_id = (branch.id or "").strip()
        text = (branch.text or "").strip()
        if not text:
            continue
        text_lower = text.lower()
        if hint_lower in text_lower or text_lower in hint_lower:
            return [branch_id] if branch_id else []

    # Leave raw hint for frontend text→node resolution.
    if role == "open":
        return []
    return [hint]


def _topic_node_id(spec: dict[str, Any]) -> str:
    nodes = spec.get("nodes")
    if not isinstance(nodes, list):
        return ""
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "").strip()
        node_type = str(node.get("type") or "").lower()
        if node_id and (node_type == "topic" or node_id == "topic"):
            return node_id
    return ""


def _first_level_branch_ids(spec: dict[str, Any], topic_id: str) -> list[str]:
    if not topic_id:
        return []
    known: set[str] = set()
    nodes = spec.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = str(node.get("id") or "").strip()
            if node_id:
                known.add(node_id)
    connections = spec.get("connections")
    if not isinstance(connections, list):
        return []
    branch_ids: list[str] = []
    seen: set[str] = set()
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        if str(conn.get("edgeType") or "") == "association":
            continue
        if str(conn.get("source") or "") != topic_id:
            continue
        target = str(conn.get("target") or "").strip()
        if not target or target == topic_id or target in seen:
            continue
        if known and target not in known:
            continue
        seen.add(target)
        branch_ids.append(target)
    return branch_ids


def resolve_whole_map_focus_node_ids(spec: dict[str, Any]) -> list[str]:
    """
    Topic plus first-level main branches for overview / closing canvas framing.

    Jobs often persist only the topic id; the camera should still show the
    whole-map trunk, not a tight zoom on the center node.
    """
    topic_id = _topic_node_id(spec)
    branch_ids = _first_level_branch_ids(spec, topic_id)
    if topic_id:
        return [topic_id, *branch_ids]
    return branch_ids
