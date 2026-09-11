"""Clockwise mind-map sibling order shared by canvas chrome and voice targeting.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import math
from typing import Any, Optional

from services.diagram.mindmap_location import mindmap_node_side


def node_coord(node: dict[str, Any], axis: str) -> Optional[float]:
    """Return a numeric canvas x/y from ``node.position`` when present."""
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
        y_val = node_coord(node, "y")
        return (y_val if y_val is not None else 0.0, child_ids.index(node_id))

    return sorted(child_ids, key=sort_key, reverse=reverse)


def _topic_and_children_have_positions(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> bool:
    topic = by_id.get(topic_id) or {}
    if node_coord(topic, "x") is None or node_coord(topic, "y") is None:
        return False
    for node_id in child_ids:
        node = by_id.get(node_id) or {}
        if node_coord(node, "x") is None or node_coord(node, "y") is None:
            return False
    return True


def _sort_ids_by_side_of_topic(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[str]:
    """Right of topic top→bottom, then left bottom→top. ``x >= topic.x`` is right."""
    topic = by_id.get(topic_id) or {}
    tx = node_coord(topic, "x")
    if tx is None:
        return sort_child_ids_by_y(child_ids, by_id)

    right: list[str] = []
    left: list[str] = []
    for node_id in child_ids:
        node = by_id.get(node_id) or {}
        x_val = node_coord(node, "x")
        if x_val is None or x_val >= tx:
            right.append(node_id)
        else:
            left.append(node_id)

    return [
        *sort_child_ids_by_y(right, by_id),
        *sort_child_ids_by_y(left, by_id, reverse=True),
    ]


def _sort_ids_clockwise_from_topic(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[str]:
    """Polar clockwise from 12 o'clock. Angle 0 = above topic."""
    if len(child_ids) <= 1:
        return list(child_ids)
    topic = by_id.get(topic_id) or {}
    tx = node_coord(topic, "x")
    ty = node_coord(topic, "y")
    if tx is None or ty is None:
        return sort_child_ids_by_y(child_ids, by_id)

    def angle_key(node_id: str) -> tuple[float, int]:
        node = by_id.get(node_id) or {}
        x_val = node_coord(node, "x")
        y_val = node_coord(node, "y")
        if x_val is None or y_val is None:
            return (math.tau, child_ids.index(node_id))
        angle = math.atan2(x_val - tx, -(y_val - ty))
        if angle < 0:
            angle += math.tau
        return (angle, child_ids.index(node_id))

    return sorted(child_ids, key=angle_key)


def sort_topic_branch_ids_clockwise(
    child_ids: list[str],
    by_id: dict[str, dict[str, Any]],
    topic_id: str,
) -> list[str]:
    """
    Canvas reading order: right column top→bottom, then left bottom→top.

    Prefer geometric side-of-topic when positions exist; else stamped /
    positional location; else polar angle.
    """
    if len(child_ids) <= 1:
        return list(child_ids)

    if _topic_and_children_have_positions(child_ids, by_id, topic_id):
        return _sort_ids_by_side_of_topic(child_ids, by_id, topic_id)

    nodes = list(by_id.values())
    right = [
        node_id for node_id in child_ids if mindmap_node_side(node_id, nodes=nodes, node=by_id.get(node_id)) == "right"
    ]
    left = [
        node_id for node_id in child_ids if mindmap_node_side(node_id, nodes=nodes, node=by_id.get(node_id)) == "left"
    ]
    other = [
        node_id for node_id in child_ids if mindmap_node_side(node_id, nodes=nodes, node=by_id.get(node_id)) is None
    ]

    if not right and not left:
        return _sort_ids_clockwise_from_topic(child_ids, by_id, topic_id)

    return [
        *sort_child_ids_by_y(right, by_id),
        *sort_child_ids_by_y(left, by_id, reverse=True),
        *sort_child_ids_by_y(other, by_id),
    ]
