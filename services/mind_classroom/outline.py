"""Extract mind-map outline (topic + first-level branches) from diagram spec JSON."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class MindMapBranchOutline:
    """One first-level branch and its immediate children texts."""

    id: Optional[str]
    text: str
    children: list[str] = field(default_factory=list)


@dataclass
class MindMapOutline:
    """Normalized mind-map structure for lesson planning."""

    topic: str
    branches: list[MindMapBranchOutline] = field(default_factory=list)
    diagram_type: str = "mind_map"

    def to_planner_payload(self) -> dict[str, Any]:
        """JSON-serializable outline for the lesson planner LLM."""
        return {
            "topic": self.topic,
            "branch_order": "clockwise",
            "branches": [
                {
                    "id": branch.id,
                    "text": branch.text,
                    "children": list(branch.children),
                }
                for branch in self.branches
            ],
        }


def clean_node_text(value: Any) -> str:
    """Strip a node title/label to a non-empty string when possible."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _clean_text(value: Any) -> str:
    return clean_node_text(value)


def _node_coord(node: dict[str, Any], axis: str) -> Optional[float]:
    position = node.get("position")
    if not isinstance(position, dict):
        return None
    raw = position.get(axis)
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def sort_child_ids_by_y(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    *,
    reverse: bool = False,
) -> list[str]:
    """Top→bottom on canvas (ascending Y); stable via original index on ties."""
    if len(child_ids) <= 1:
        return list(child_ids)

    def sort_key(node_id: str) -> tuple[float, int]:
        node = by_id.get(node_id) or {}
        y_val = _node_coord(node, "y")
        return (y_val if y_val is not None else 0.0, child_ids.index(node_id))

    ordered = sorted(child_ids, key=sort_key, reverse=reverse)
    return ordered


def _sort_ids_by_y(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    *,
    reverse: bool = False,
) -> list[str]:
    return sort_child_ids_by_y(child_ids, by_id, reverse=reverse)


def _topic_and_children_have_positions(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> bool:
    topic = by_id.get(topic_id) or {}
    if _node_coord(topic, "x") is None or _node_coord(topic, "y") is None:
        return False
    for node_id in child_ids:
        node = by_id.get(node_id) or {}
        if _node_coord(node, "x") is None or _node_coord(node, "y") is None:
            return False
    return True


def _sort_ids_by_side_of_topic(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[str]:
    """
    Geometric clockwise helper: right of topic top→bottom, then left bottom→top.

    Side is ``x >= topic.x`` → right, else left.
    """
    topic = by_id.get(topic_id) or {}
    tx = _node_coord(topic, "x")
    if tx is None:
        return _sort_ids_by_y(child_ids, by_id)

    right: list[str] = []
    left: list[str] = []
    for node_id in child_ids:
        node = by_id.get(node_id) or {}
        x_val = _node_coord(node, "x")
        if x_val is None or x_val >= tx:
            right.append(node_id)
        else:
            left.append(node_id)

    return [
        *_sort_ids_by_y(right, by_id),
        *_sort_ids_by_y(left, by_id, reverse=True),
    ]


def _sort_ids_clockwise_from_topic(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[str]:
    """
    Clockwise from 12 o'clock around the topic using node positions.

    Angle 0 = above topic; increases through right → bottom → left.
    """
    if len(child_ids) <= 1:
        return list(child_ids)
    topic = by_id.get(topic_id) or {}
    tx = _node_coord(topic, "x")
    ty = _node_coord(topic, "y")
    if tx is None or ty is None:
        return _sort_ids_by_y(child_ids, by_id)

    def angle_key(node_id: str) -> tuple[float, int]:
        node = by_id.get(node_id) or {}
        x_val = _node_coord(node, "x")
        y_val = _node_coord(node, "y")
        if x_val is None or y_val is None:
            return (math.tau, child_ids.index(node_id))
        angle = math.atan2(x_val - tx, -(y_val - ty))
        if angle < 0:
            angle += math.tau
        return (angle, child_ids.index(node_id))

    return sorted(child_ids, key=angle_key)


def canvas_place_code(
    node_id: str,
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
    sibling_ids: list[str],
) -> str:
    """Canvas quadrant for tutor pointing: center / left|right[_top|_mid|_bottom]."""
    if node_id == topic_id:
        return "center"
    topic = by_id.get(topic_id) or {}
    node = by_id.get(node_id) or {}
    topic_x = _node_coord(topic, "x")
    node_x = _node_coord(node, "x")
    if node_x is not None and topic_x is not None:
        side = "right" if node_x >= topic_x else "left"
    elif node_id.startswith("branch-r-"):
        side = "right"
    elif node_id.startswith("branch-l-"):
        side = "left"
    else:
        return "center"
    same_side = [sibling for sibling in sibling_ids if _same_canvas_side(sibling, side, by_id, topic_id)]
    if node_id not in same_side:
        same_side.append(node_id)
    has_y = any(_node_coord(by_id.get(sibling) or {}, "y") is not None for sibling in same_side)
    if len(same_side) <= 1 or not has_y:
        return side
    ordered = sort_child_ids_by_y(same_side, by_id)
    if node_id == ordered[0]:
        return f"{side}_top"
    if node_id == ordered[-1]:
        return f"{side}_bottom"
    return f"{side}_mid"


def _same_canvas_side(
    node_id: str,
    side: str,
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> bool:
    topic = by_id.get(topic_id) or {}
    node = by_id.get(node_id) or {}
    topic_x = _node_coord(topic, "x")
    node_x = _node_coord(node, "x")
    if node_x is not None and topic_x is not None:
        actual = "right" if node_x >= topic_x else "left"
        return actual == side
    if node_id.startswith("branch-r-"):
        return side == "right"
    if node_id.startswith("branch-l-"):
        return side == "left"
    return False


def sort_topic_branch_ids_clockwise(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[str]:
    """
    Match canvas presentation order: right column top→bottom, then left
    column bottom→top (continuation of clockwise).

    Prefer geometric side-of-topic when positions exist; else ``branch-r-`` /
    ``branch-l-`` prefixes; else polar angle.
    """
    if len(child_ids) <= 1:
        return list(child_ids)

    if _topic_and_children_have_positions(child_ids, by_id, topic_id):
        return _sort_ids_by_side_of_topic(child_ids, by_id, topic_id)

    right = [node_id for node_id in child_ids if node_id.startswith("branch-r-")]
    left = [node_id for node_id in child_ids if node_id.startswith("branch-l-")]
    other = [
        node_id for node_id in child_ids if not node_id.startswith("branch-r-") and not node_id.startswith("branch-l-")
    ]

    if not right and not left:
        return _sort_ids_clockwise_from_topic(child_ids, by_id, topic_id)

    # Left stack is stored/drawn top→bottom; reverse for clockwise continuation.
    return [
        *_sort_ids_by_y(right, by_id),
        *_sort_ids_by_y(left, by_id, reverse=True),
        *_sort_ids_by_y(other, by_id),
    ]


def _child_texts(node: dict[str, Any]) -> list[str]:
    kids = node.get("children")
    if not isinstance(kids, list):
        kids = node.get("branches")
    if not isinstance(kids, list):
        return []
    texts: list[str] = []
    for kid in kids:
        if isinstance(kid, str):
            text = kid.strip()
            if text:
                texts.append(text)
            continue
        if not isinstance(kid, dict):
            continue
        text = _clean_text(kid.get("text") or kid.get("label") or kid.get("topic"))
        if text:
            texts.append(text)
    return texts


def _branch_from_item(item: Any, index: int) -> Optional[MindMapBranchOutline]:
    if isinstance(item, str):
        text = item.strip()
        if not text:
            return None
        return MindMapBranchOutline(id=f"branch-{index}", text=text)
    if not isinstance(item, dict):
        return None
    text = _clean_text(item.get("text") or item.get("label") or item.get("topic"))
    if not text:
        return None
    node_id = item.get("id") or item.get("uid")
    return MindMapBranchOutline(
        id=str(node_id) if node_id else f"branch-{index}",
        text=text,
        children=_child_texts(item),
    )


def _branches_from_hierarchical(spec: dict[str, Any]) -> list[MindMapBranchOutline]:
    raw_branches: list[Any] = []
    if isinstance(spec.get("children"), list):
        raw_branches = spec["children"]
    elif isinstance(spec.get("branches"), list):
        raw_branches = spec["branches"]
    else:
        left = spec.get("leftBranches") or spec.get("left") or []
        right = spec.get("rightBranches") or spec.get("right") or []
        # Clockwise = right top→bottom, then left bottom→top.
        if isinstance(right, list):
            raw_branches.extend(right)
        if isinstance(left, list):
            raw_branches.extend(list(reversed(left)))

    branches: list[MindMapBranchOutline] = []
    for index, item in enumerate(raw_branches):
        branch = _branch_from_item(item, index)
        if branch is not None:
            branches.append(branch)
    return branches


def _branches_from_nodes(spec: dict[str, Any]) -> tuple[str, list[MindMapBranchOutline]]:
    nodes = spec.get("nodes")
    connections = spec.get("connections")
    if not isinstance(nodes, list) or not nodes:
        return "", []

    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            by_id[node_id] = node

    children_map: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    if isinstance(connections, list):
        for conn in connections:
            if not isinstance(conn, dict):
                continue
            source = conn.get("source")
            target = conn.get("target")
            if isinstance(source, str) and isinstance(target, str):
                if source in children_map and target in by_id:
                    children_map[source].append(target)

    topic_id = None
    topic_text = ""
    for node_id, node in by_id.items():
        node_type = str(node.get("type") or "").lower()
        if node_type == "topic" or node_id == "topic":
            topic_id = node_id
            topic_text = _clean_text(node.get("text") or node.get("label"))
            break
    if topic_id is None:
        # Fallback: first node
        topic_id = next(iter(by_id))
        topic_text = _clean_text(by_id[topic_id].get("text") or by_id[topic_id].get("label"))

    raw_child_ids = list(children_map.get(topic_id or "", []))
    ordered_ids = sort_topic_branch_ids_clockwise(raw_child_ids, by_id, topic_id)

    branches: list[MindMapBranchOutline] = []
    for child_id in ordered_ids:
        node = by_id.get(child_id)
        if not node:
            continue
        text = _clean_text(node.get("text") or node.get("label"))
        if not text:
            continue
        grandchild_ids = _sort_ids_by_y(list(children_map.get(child_id, [])), by_id)
        grandchild_texts = []
        for gid in grandchild_ids:
            gnode = by_id.get(gid)
            if not gnode:
                continue
            gtext = _clean_text(gnode.get("text") or gnode.get("label"))
            if gtext:
                grandchild_texts.append(gtext)
        branches.append(MindMapBranchOutline(id=child_id, text=text, children=grandchild_texts))
    return topic_text, branches


def is_mindmap_type(diagram_type: Optional[str]) -> bool:
    """Return True for mind-map diagram type slugs."""
    slug = (diagram_type or "").strip().lower().replace("-", "_")
    return slug in {"mindmap", "mind_map"}


def extract_mindmap_outline(
    spec: Any,
    *,
    diagram_type: Optional[str] = None,
    fallback_title: str = "",
) -> MindMapOutline:
    """
    Normalize a saved diagram ``spec`` into topic + first-level branches.

    Supports hierarchical ``topic``/``children`` and flat ``nodes``/``connections``.
    Branch list is clockwise (right top→bottom, then left bottom→top).
    """
    if not isinstance(spec, dict):
        raise ValueError("Diagram spec must be a JSON object")

    type_hint = diagram_type or spec.get("type") or spec.get("diagramType")
    if type_hint and not is_mindmap_type(str(type_hint)):
        # Still try hierarchical extract; reject clearly non-mindmap later in API.
        pass

    topic = _clean_text(spec.get("topic") or spec.get("title") or spec.get("centralTopic"))
    branches = _branches_from_hierarchical(spec)

    # Prefer nodes/connections when present — includes positions for clockwise order.
    if isinstance(spec.get("nodes"), list):
        node_topic, node_branches = _branches_from_nodes(spec)
        if node_branches:
            branches = node_branches
            if not topic:
                topic = node_topic
        elif not topic:
            topic = node_topic

    if not topic:
        topic = _clean_text(fallback_title) or "未命名主题"
    if not branches:
        raise ValueError("Mind map has no first-level branches to teach from")

    return MindMapOutline(
        topic=topic,
        branches=branches,
        diagram_type="mind_map",
    )
