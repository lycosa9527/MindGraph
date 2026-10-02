"""Stamp 思维讲堂 tour nodes with each diagram's node-system role.

The canvas already stores roles (circle context, double-bubble side, cause/effect,
bridge pair). The lecture walk used to flatten those into generic branches and,
for some maps, drop a whole side. This module names every content node and
inserts nodes the mind-map child walk never reached.
"""

from __future__ import annotations

import math
from typing import Any

from services.diagram.mindmap_outline_order import node_coord
from services.diagram.thinking_map_patterns import (
    leftover_slot_role,
    normalize_diagram_type,
    topic_node_id_for,
)
from services.mind_classroom.prompts.diagram_prompts import normalize_lecture_diagram

_SKIP_TYPES = frozenset({"boundary"})
_SKIP_IDS = frozenset({"outer-boundary"})

_ROLE_LABELS = {
    "topic": "中心主题",
    "context": "联想",
    "attribute": "属性",
    "left_topic": "左侧事物",
    "right_topic": "右侧事物",
    "similarity": "相同点",
    "left_diff": "左侧不同点",
    "right_diff": "右侧不同点",
    "dimension": "维度",
    "category": "类别",
    "item": "项目",
    "whole": "整体",
    "part": "部分",
    "subpart": "子部分",
    "step": "步骤",
    "substep": "子步骤",
    "event": "事件",
    "cause": "原因",
    "effect": "结果",
    "relating_factor": "关系因子",
    "analogy_left": "类比左项",
    "analogy_right": "类比右项",
    "concept": "概念",
    "branch": "分支",
    "child": "子点",
}

# Missing nodes are inserted in this order. Existing walk order stays put.
_INSERT_RANK = {
    "dimension": 10,
    "cause": 20,
    "left_diff": 30,
    "similarity": 40,
    "right_topic": 50,
    "right_diff": 60,
    "analogy_left": 70,
    "analogy_right": 80,
    "context": 90,
    "attribute": 90,
    "category": 90,
    "part": 90,
    "step": 90,
    "effect": 100,
    "item": 110,
    "subpart": 110,
    "substep": 110,
    "concept": 90,
    "branch": 90,
    "child": 110,
}


def _slug(spec: dict[str, Any]) -> str:
    raw = spec.get("type") or spec.get("diagramType") or spec.get("diagram_type") or ""
    slug = normalize_diagram_type(str(raw))
    if slug == "mindmap":
        return "mind_map"
    return normalize_lecture_diagram(slug)


def _text(node: dict[str, Any]) -> str:
    raw = node.get("text") if node.get("text") not in (None, "") else node.get("label")
    return str(raw or "").strip()


def _data(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data")
    return data if isinstance(data, dict) else {}


def _nodes(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw = spec.get("nodes")
    if not isinstance(raw, list):
        return []
    return [node for node in raw if isinstance(node, dict) and str(node.get("id") or "").strip()]


def _by_id(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(node.get("id")): node for node in nodes}


def _parent_of(spec: dict[str, Any]) -> dict[str, str]:
    """First incoming source for each target. Multi-flow causes point at the event."""
    parents: dict[str, str] = {}
    connections = spec.get("connections")
    if not isinstance(connections, list):
        return parents
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        source = conn.get("source")
        target = conn.get("target")
        if isinstance(source, str) and isinstance(target, str) and target not in parents:
            parents[target] = source
    return parents


def _edge_label(spec: dict[str, Any], node_id: str) -> str:
    connections = spec.get("connections")
    if not isinstance(connections, list):
        return ""
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        if conn.get("target") != node_id:
            continue
        label = str(conn.get("label") or "").strip()
        if label:
            return label
    return ""


def _double_role(node: dict[str, Any]) -> str:
    stamped = _data(node).get("doubleBubbleRole")
    if stamped == "similarity":
        return "similarity"
    if stamped == "leftDiff":
        return "left_diff"
    if stamped == "rightDiff":
        return "right_diff"
    legacy = str(_data(node).get("doubleBubbleMapLegacyId") or node.get("id") or "")
    leftover = leftover_slot_role("double_bubble_map", legacy)
    if leftover == "similarity":
        return "similarity"
    if leftover == "leftDiff":
        return "left_diff"
    if leftover == "rightDiff":
        return "right_diff"
    return ""


def _multi_role(node: dict[str, Any], *, parent_id: str, event_id: str) -> str:
    stamped = _data(node).get("multiFlowRole")
    if stamped in {"cause", "effect"}:
        return str(stamped)
    leftover = leftover_slot_role("multi_flow_map", str(node.get("id") or ""))
    if leftover in {"cause", "effect"}:
        return leftover
    if parent_id == event_id:
        return "effect"
    return "cause"


def _bridge_side(node: dict[str, Any]) -> str:
    position = _data(node).get("position")
    if position == "left":
        return "analogy_left"
    if position == "right":
        return "analogy_right"
    leftover = leftover_slot_role("bridge_map", str(node.get("id") or ""))
    if leftover == "left":
        return "analogy_left"
    if leftover == "right":
        return "analogy_right"
    return ""


def _is_center(node_id: str, node_type: str, *aliases: str) -> bool:
    return node_id in aliases or node_type in {"topic", "center"}


def _circle_role(node_id: str, node_type: str, **_ignored: Any) -> str:
    if _is_center(node_id, node_type, "topic"):
        return "topic"
    return "context"


def _bubble_role(node_id: str, node_type: str, **_ignored: Any) -> str:
    if _is_center(node_id, node_type, "topic"):
        return "topic"
    return "attribute"


def _double_bubble_role(node_id: str, node_type: str, node: dict[str, Any], **_ignored: Any) -> str:
    del node_type, _ignored
    if node_id == "left-topic":
        return "left_topic"
    if node_id == "right-topic":
        return "right_topic"
    return _double_role(node)


def _tree_role(
    node_id: str,
    node_type: str,
    *,
    parent_id: str,
    topic_id: str,
    **_ignored: Any,
) -> str:
    if _is_center(node_id, node_type, "tree-topic", "topic"):
        return "topic"
    if node_id == "dimension-label" or node_type == "label":
        return "dimension"
    if parent_id in {topic_id, "tree-topic", "topic"}:
        return "category"
    return "item"


def _brace_role(
    node_id: str,
    node_type: str,
    *,
    parent_id: str,
    topic_id: str,
    **_ignored: Any,
) -> str:
    if node_id in {"brace-whole", "topic"} or node_type == "topic":
        return "whole"
    if node_id == "dimension-label" or node_type == "label":
        return "dimension"
    if parent_id in {topic_id, "brace-whole"}:
        return "part"
    return "subpart"


def _flow_role(node_id: str, node_type: str, **_ignored: Any) -> str:
    if node_id in {"flow-topic", "topic"} or node_type == "topic":
        return "topic"
    if node_type == "flowsubstep":
        return "substep"
    return "step"


def _multi_flow_role_for(
    node_id: str,
    node_type: str,
    node: dict[str, Any],
    *,
    parent_id: str,
    topic_id: str,
    **_ignored: Any,
) -> str:
    if node_id in {"event", "topic"} or node_type == "topic":
        return "event"
    return _multi_role(node, parent_id=parent_id, event_id=topic_id or "event")


def _bridge_role(node_id: str, node_type: str, node: dict[str, Any], **_ignored: Any) -> str:
    if node_id == "dimension-label" or node_type == "label":
        return "relating_factor"
    return _bridge_side(node) or "analogy_left"


def _concept_role(node_id: str, node_type: str, node: dict[str, Any], **_ignored: Any) -> str:
    if node_id == "topic" or node_type == "topic":
        return "topic"
    if node_type == "label" and not _text(node):
        return ""
    return "concept"


def _mind_map_role(
    node_id: str,
    node_type: str,
    *,
    parent_id: str,
    topic_id: str,
    **_ignored: Any,
) -> str:
    if node_id in {"topic", topic_id} or node_type == "topic":
        return "topic"
    if parent_id in {topic_id, "topic"}:
        return "branch"
    return "child"


_ROLE_BY_DIAGRAM = {
    "circle_map": _circle_role,
    "bubble_map": _bubble_role,
    "double_bubble_map": _double_bubble_role,
    "tree_map": _tree_role,
    "brace_map": _brace_role,
    "flow_map": _flow_role,
    "multi_flow_map": _multi_flow_role_for,
    "bridge_map": _bridge_role,
    "concept_map": _concept_role,
}


def lecture_role(
    diagram_type: str,
    node: dict[str, Any],
    *,
    parent_id: str = "",
    topic_id: str = "",
) -> str:
    """Return the lecture role id, or empty when the node is structural."""
    node_id = str(node.get("id") or "").strip()
    node_type = str(node.get("type") or "").strip().lower()
    if node_id in _SKIP_IDS or node_type in _SKIP_TYPES:
        return ""
    slug = normalize_lecture_diagram(diagram_type)
    resolver = _ROLE_BY_DIAGRAM.get(slug, _mind_map_role)
    return resolver(
        node_id,
        node_type,
        node=node,
        parent_id=parent_id,
        topic_id=topic_id,
    )


def _topic_id(spec: dict[str, Any], nodes: list[dict[str, Any]]) -> str:
    slug = _slug(spec)
    reserved = topic_node_id_for(slug)
    by_id = _by_id(nodes)
    if reserved and reserved in by_id:
        return reserved
    for node in nodes:
        node_id = str(node.get("id") or "")
        node_type = str(node.get("type") or "").lower()
        if node_type in {"topic", "center", "whole", "event"} or node_id == "topic":
            return node_id
    return str(nodes[0].get("id") or "") if nodes else ""


def _axis_x(node: dict[str, Any]) -> float:
    position = node.get("position")
    if not isinstance(position, dict):
        return 0.0
    try:
        return float(position.get("x") or 0)
    except (TypeError, ValueError):
        return 0.0


def _place(node: dict[str, Any], topic: dict[str, Any]) -> str:
    node_x = _axis_x(node)
    topic_x = _axis_x(topic)
    if node_x < topic_x - 8:
        return "left"
    if node_x > topic_x + 8:
        return "right"
    return "center"


def _blank_item(
    node: dict[str, Any],
    *,
    role: str,
    topic_id: str,
    topic_text: str,
    place: str,
) -> dict[str, Any]:
    node_id = str(node.get("id") or "")
    return {
        "id": node_id,
        "text": _text(node),
        "kind": "branch",
        "parent_id": topic_id or None,
        "parent_text": topic_text or None,
        "sibling_texts": [],
        "child_texts": [],
        "descendant_ids": [node_id] if node_id else [],
        "place": place,
        "stop": "leaf",
        "role": role,
        "role_label": _ROLE_LABELS.get(role, role),
    }


def _parent_id_for(item: dict[str, Any], parents: dict[str, str]) -> str:
    stored = item.get("parent_id")
    if stored:
        return str(stored)
    return parents.get(str(item.get("id") or ""), "")


def _stamp(
    spec: dict[str, Any],
    item: dict[str, Any],
    node: dict[str, Any] | None,
    *,
    topic_id: str,
    parents: dict[str, str],
) -> None:
    slug = _slug(spec)
    parent_id = _parent_id_for(item, parents)
    if node is None:
        role = "topic" if item.get("kind") == "topic" else "branch"
    else:
        role = lecture_role(slug, node, parent_id=parent_id, topic_id=topic_id)
        if not role:
            role = "topic" if item.get("kind") == "topic" else "branch"
    item["role"] = role
    item["role_label"] = _ROLE_LABELS.get(role, role)
    if role == "concept" and node is not None:
        relation = _edge_label(spec, str(node.get("id") or ""))
        if relation:
            item["relation"] = relation


_ROOT_ROLES = frozenset({"topic", "left_topic", "event", "whole"})

# Overview camera: the nodes that carry this diagram's idea. Mind maps stay on
# the existing topic-plus-first-level walk in focus.py.
_OVERVIEW_ROLES: dict[str, frozenset[str]] = {
    "circle_map": frozenset({"topic", "context"}),
    "bubble_map": frozenset({"topic", "attribute"}),
    "double_bubble_map": frozenset({"left_topic", "right_topic", "similarity", "left_diff", "right_diff"}),
    "tree_map": frozenset({"topic", "dimension", "category", "item"}),
    "brace_map": frozenset({"whole", "dimension", "part", "subpart"}),
    "flow_map": frozenset({"topic", "step", "substep"}),
    "multi_flow_map": frozenset({"event", "cause", "effect"}),
    "bridge_map": frozenset({"relating_factor", "analogy_left", "analogy_right"}),
    "concept_map": frozenset({"topic", "concept"}),
}
_OVERVIEW_ROOTS = frozenset({"topic", "left_topic", "right_topic", "whole", "event", "relating_factor"})


def _missing_items(
    spec: dict[str, Any],
    nodes: list[dict[str, Any]],
    *,
    present: set[str],
    parents: dict[str, str],
    topic_id: str,
    topic: dict[str, Any],
    topic_text: str,
) -> list[tuple[int, dict[str, Any]]]:
    """Content nodes the mind-map child walk never listed."""
    slug = _slug(spec)
    missing: list[tuple[int, dict[str, Any]]] = []
    for node in nodes:
        node_id = str(node.get("id") or "")
        if node_id in present or not _text(node):
            continue
        role = lecture_role(slug, node, parent_id=parents.get(node_id, ""), topic_id=topic_id)
        if not role or role in _ROOT_ROLES:
            continue
        missing.append(
            (
                _INSERT_RANK.get(role, 90),
                _blank_item(
                    node,
                    role=role,
                    topic_id=topic_id,
                    topic_text=topic_text,
                    place=_place(node, topic),
                ),
            )
        )
    return missing


def _insertion_index(items: list[dict[str, Any]], role: str) -> int:
    if role == "dimension":
        return 1 if items else 0
    if role == "cause":
        for index, item in enumerate(items):
            if item.get("role") == "effect":
                return index
        return len(items)
    if role == "right_topic":
        last = 1 if items else 0
        for index, item in enumerate(items):
            if item.get("role") in {"left_diff", "similarity", "left_topic"}:
                last = index + 1
        return last
    return len(items)


def overview_focus_node_ids(spec: dict[str, Any]) -> list[str] | None:
    """Content nodes for overview / closing. None means use the mind-map walk."""
    if not isinstance(spec, dict):
        return None
    allowed = _OVERVIEW_ROLES.get(_slug(spec))
    nodes = _nodes(spec)
    if not allowed or not nodes:
        return None
    topic_id = _topic_id(spec, nodes)
    parents = _parent_of(spec)
    ranked: list[tuple[int, int, str]] = []
    for index, node in enumerate(nodes):
        node_id = str(node.get("id") or "")
        role = lecture_role(
            _slug(spec),
            node,
            parent_id=parents.get(node_id, ""),
            topic_id=topic_id,
        )
        if role not in allowed:
            continue
        if not _text(node) and role not in _OVERVIEW_ROOTS:
            continue
        ranked.append((0 if role in _OVERVIEW_ROOTS else 1, index, node_id))
    ranked.sort()
    ordered = [node_id for _, _, node_id in ranked]
    return ordered or None


def apply_lecture_roles(spec: dict[str, Any], items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Stamp roles and append content nodes the generic walk omitted."""
    if not isinstance(spec, dict):
        return items
    nodes = _nodes(spec)
    if not nodes:
        if items:
            slug = _slug(spec)
            root = "event" if slug == "multi_flow_map" else "whole" if slug == "brace_map" else "topic"
            items[0]["role"] = root if items[0].get("kind") == "topic" else items[0].get("role") or "branch"
            items[0]["role_label"] = _ROLE_LABELS.get(str(items[0]["role"]), str(items[0]["role"]))
        return items

    topic_id = _topic_id(spec, nodes)
    by_id = _by_id(nodes)
    parents = _parent_of(spec)
    topic = by_id.get(topic_id) or {}
    topic_text = _text(topic)
    for item in items:
        node = by_id.get(str(item.get("id") or ""))
        _stamp(spec, item, node, topic_id=topic_id, parents=parents)

    present = {str(item.get("id") or "") for item in items if item.get("id")}
    missing = _missing_items(
        spec,
        nodes,
        present=present,
        parents=parents,
        topic_id=topic_id,
        topic=topic,
        topic_text=topic_text,
    )
    missing.sort(key=lambda pair: pair[0])
    for _rank, item in missing:
        items.insert(_insertion_index(items, str(item.get("role") or "")), item)
        if item.get("id"):
            present.add(str(item["id"]))
    ordered = _reading_order(spec, items, by_id, topic_id)
    ordered = _fold_bridge_pairs(spec, ordered, by_id)
    _mark_opening_walk(ordered)
    return ordered


_RADIAL = frozenset({"circle_map", "bubble_map"})
_WALK_ROOTS = frozenset({"topic", "left_topic", "event", "whole"})
# Named in the overview. They stay on the node list so the script can read them,
# and they are not their own camera step.
_OPENING_WALK_ROLES = frozenset({"dimension", "relating_factor", "right_topic"})


def _xy(node: dict[str, Any]) -> tuple[float, float]:
    x_val = node_coord(node, "x")
    y_val = node_coord(node, "y")
    return (0.0 if x_val is None else x_val, 0.0 if y_val is None else y_val)


def _clockwise_from_top(node: dict[str, Any], origin: tuple[float, float]) -> float:
    """Match the canvas: angle 0 is above the center, and increasing is clockwise."""
    nx_val, ny_val = _xy(node)
    angle = math.atan2(ny_val - origin[1], nx_val - origin[0])
    return (angle + math.pi / 2.0) % math.tau


def _pair_index(node: dict[str, Any]) -> float:
    raw = _data(node).get("pairIndex")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return 0.0
    return float(raw)


def _band_key(
    slug: str,
    role: str,
    node: dict[str, Any],
    x_val: float,
    y_val: float,
) -> tuple[float, float, float, float] | None:
    if slug == "double_bubble_map":
        band = {"left_diff": 0, "similarity": 1, "right_topic": 2, "right_diff": 3}.get(role, 4)
        return (1.0, float(band), y_val, x_val)
    if slug == "multi_flow_map":
        band = {"cause": 0, "effect": 1}.get(role, 2)
        return (1.0, float(band), y_val, x_val)
    if slug == "bridge_map":
        if role == "relating_factor":
            return (2.0, 0.0, 0.0, 0.0)
        side = 0.0 if role == "analogy_left" else 1.0
        return (1.0, _pair_index(node), side, y_val)
    return None


def _reading_key(
    slug: str,
    item: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> tuple[float, float, float, float]:
    """Visual reading order. Opening labels sit with the topic, then the groups."""
    role = str(item.get("role") or "")
    if role in _WALK_ROOTS:
        return (0.0, 0.0, 0.0, 0.0)
    if role in _OPENING_WALK_ROLES:
        return (0.5, 0.0, 0.0, 0.0)
    node = by_id.get(str(item.get("id") or ""), {})
    x_val, y_val = _xy(node)
    if slug in _RADIAL:
        return (1.0, _clockwise_from_top(node, _xy(by_id.get(topic_id, {}))), 0.0, 0.0)
    band = _band_key(slug, role, node, x_val, y_val)
    if band is not None:
        return band
    if role == "dimension":
        return (2.0, 0.0, 0.0, 0.0)
    parent_id = str(item.get("parent_id") or "")
    parent = by_id.get(parent_id)
    if parent is not None and parent_id != topic_id:
        px_val, py_val = _xy(parent)
        return (1.0, px_val, py_val, y_val)
    return (1.0, x_val, y_val, 0.0)


def _reading_order(
    spec: dict[str, Any],
    items: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[dict[str, Any]]:
    """Ring maps orbit from the top. Columns walk left to right, children under their group."""
    slug = _slug(spec)
    if slug == "mind_map":
        return items
    ranked = sorted(
        enumerate(items),
        key=lambda pair: (*_reading_key(slug, pair[1], by_id, topic_id), pair[0]),
    )
    return [item for _, item in ranked]


def _mark_opening_walk(items: list[dict[str, Any]]) -> None:
    for item in items:
        if item.get("role") in _OPENING_WALK_ROLES:
            item["walk"] = "opening"


def _fold_bridge_pairs(
    spec: dict[str, Any],
    items: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """One lecture node per analogy pair. The right side stays in child_texts."""
    if _slug(spec) != "bridge_map":
        return items
    rights: dict[float, dict[str, Any]] = {}
    for item in items:
        if item.get("role") != "analogy_right":
            continue
        node = by_id.get(str(item.get("id") or ""), {})
        rights[_pair_index(node)] = item
    folded: list[dict[str, Any]] = []
    consumed: set[float] = set()
    for item in items:
        if item.get("role") == "analogy_right":
            node = by_id.get(str(item.get("id") or ""), {})
            if _pair_index(node) in consumed:
                continue
            folded.append(item)
            continue
        if item.get("role") == "analogy_left":
            node = by_id.get(str(item.get("id") or ""), {})
            pair = _pair_index(node)
            right = rights.get(pair)
            if right is not None:
                consumed.add(pair)
                _attach_pair_side(item, right)
        folded.append(item)
    return folded


def _attach_pair_side(item: dict[str, Any], right: dict[str, Any]) -> None:
    text = str(right.get("text") or "").strip()
    children = [str(value) for value in (item.get("child_texts") or []) if str(value).strip()]
    if text and text not in children:
        children.append(text)
    item["child_texts"] = children
    right_id = str(right.get("id") or "")
    descendants = [str(value) for value in (item.get("descendant_ids") or []) if str(value).strip()]
    if right_id and right_id not in descendants:
        descendants.append(right_id)
    item["descendant_ids"] = descendants


def opening_walk_node_ids(spec: dict[str, Any]) -> set[str]:
    """Nodes named in the overview. A branch step that is only these is dropped."""
    if not isinstance(spec, dict):
        return set()
    nodes = _nodes(spec)
    if not nodes:
        return set()
    topic_id = _topic_id(spec, nodes)
    parents = _parent_of(spec)
    slug = _slug(spec)
    opening: set[str] = set()
    for node in nodes:
        node_id = str(node.get("id") or "")
        role = lecture_role(
            slug,
            node,
            parent_id=parents.get(node_id, ""),
            topic_id=topic_id,
        )
        if role in _OPENING_WALK_ROLES and node_id:
            opening.add(node_id)
    return opening


def drop_opening_only_steps(spec: dict[str, Any], steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop a branch beat whose camera would only be the dimension, factor, or right topic."""
    opening = opening_walk_node_ids(spec)
    if not opening:
        return steps
    kept: list[dict[str, Any]] = []
    for step in steps:
        if step.get("kind") != "branch":
            kept.append(step)
            continue
        focus = {str(node_id) for node_id in (step.get("focus_node_ids") or []) if node_id}
        branch = str(step.get("branch_node_id") or "")
        if branch:
            focus.add(branch)
        if focus and focus <= opening:
            continue
        kept.append(step)
    return kept


def order_lecture_steps(spec: dict[str, Any], steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Play branch steps in visual reading order. Overview stays first, closing last."""
    if not isinstance(spec, dict) or _slug(spec) == "mind_map" or len(steps) < 2:
        return steps
    nodes = _nodes(spec)
    by_id = _by_id(nodes)
    topic_id = _topic_id(spec, nodes)
    parents = _parent_of(spec)
    slug = _slug(spec)

    def sort_key(pair: tuple[int, dict[str, Any]]) -> tuple[float, ...]:
        index, step = pair
        kind = str(step.get("kind") or "")
        if kind == "overview":
            return (0.0, 0.0, 0.0, 0.0, 0.0, float(index))
        if kind == "closing":
            return (3.0, 0.0, 0.0, 0.0, 0.0, float(index))
        node_id = str(step.get("branch_node_id") or "")
        if not node_id:
            focus = step.get("focus_node_ids") or []
            node_id = str(focus[0]) if focus else ""
        parent_id = parents.get(node_id, "")
        node = by_id.get(node_id) or {}
        role = lecture_role(slug, node, parent_id=parent_id, topic_id=topic_id) if node else ""
        item = {"id": node_id, "role": role, "parent_id": parent_id, "kind": "branch"}
        key = _reading_key(slug, item, by_id, topic_id)
        return (*key, 1.0, float(index))

    return [step for _, step in sorted(enumerate(steps), key=sort_key)]
