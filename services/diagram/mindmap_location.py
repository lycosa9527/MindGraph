"""Mind-map location derived from the tree, not positional node ids.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

MINDMAP_SIDE_DATA_KEY = "mindMapSide"
MINDMAP_DEPTH_DATA_KEY = "mindMapDepth"
MINDMAP_UID_DATA_KEY = "mindMapUid"
MINDMAP_LEGACY_ID_DATA_KEY = "mindMapLegacyId"
MINDMAP_TOPIC_ID = "topic"
POSITIONAL_MINDMAP_BRANCH_ID_RE = re.compile(r"^branch-([lr])-(\d+)-(\d+)$")
INVENTED_MINDMAP_PREFIX_ID_RE = re.compile(r"^(?:[A-Za-z][\w]*_\d+(?:_\d+)*|branch-\d+)$")

MindMapSide = str


def is_positional_mindmap_branch_id(node_id: str) -> bool:
    """True when ``node_id`` is the legacy ``branch-{l|r}-{depth}-{idx}`` form."""
    return bool(POSITIONAL_MINDMAP_BRANCH_ID_RE.match(node_id))


def is_leftover_mindmap_branch_id(node_id: str) -> bool:
    """True when ``node_id`` is a leftover invented address, not a stable UUID."""
    return is_positional_mindmap_branch_id(node_id) or bool(INVENTED_MINDMAP_PREFIX_ID_RE.match(node_id))


def parse_positional_mindmap_branch_id(node_id: str) -> tuple[str, int, int] | None:
    """Return ``(side_char, depth, global_index)`` or ``None``."""
    match = POSITIONAL_MINDMAP_BRANCH_ID_RE.match(node_id)
    if match is None:
        return None
    return match.group(1), int(match.group(2)), int(match.group(3))


def mindmap_side_from_char(side_char: str) -> MindMapSide:
    """Map ``l`` / ``r`` to ``left`` / ``right``."""
    return "left" if side_char == "l" else "right"


def mindmap_side_to_char(side: MindMapSide) -> str:
    """Map ``left`` / ``right`` to ``l`` / ``r``."""
    return "l" if side == "left" else "r"


def _node_data(node: Mapping[str, Any] | None) -> Mapping[str, Any]:
    data = node.get("data") if isinstance(node, Mapping) else None
    return data if isinstance(data, Mapping) else {}


def read_mindmap_side(node: Mapping[str, Any] | None) -> MindMapSide | None:
    """Read stamped ``data.mindMapSide``."""
    raw = _node_data(node).get(MINDMAP_SIDE_DATA_KEY)
    if raw in ("left", "right"):
        return raw
    return None


def read_mindmap_depth(node: Mapping[str, Any] | None) -> int | None:
    """Read stamped ``data.mindMapDepth``."""
    raw = _node_data(node).get(MINDMAP_DEPTH_DATA_KEY)
    if isinstance(raw, int) and raw >= 1:
        return raw
    return None


def read_mindmap_uid(node: Mapping[str, Any] | None) -> str | None:
    """Read stamped ``data.mindMapUid``."""
    raw = _node_data(node).get(MINDMAP_UID_DATA_KEY)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def is_mindmap_branch_node(node: Mapping[str, Any] | None) -> bool:
    """True for a mind-map branch (type, positional id, or stamped uid)."""
    if not isinstance(node, Mapping):
        return False
    node_id = str(node.get("id") or "")
    if node_id == MINDMAP_TOPIC_ID:
        return False
    if node.get("type") == "branch":
        return True
    return is_positional_mindmap_branch_id(node_id)


def mindmap_side_from_handle(handle: Any) -> MindMapSide | None:
    """Topic handle ``mindmap-left-*`` / ``mindmap-right-*``."""
    if not isinstance(handle, str):
        return None
    if handle.startswith("mindmap-left"):
        return "left"
    if handle.startswith("mindmap-right"):
        return "right"
    return None


def _parent_of(connections: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    parent_of: dict[str, str] = {}
    for connection in connections:
        source = connection.get("source")
        target = connection.get("target")
        if isinstance(source, str) and isinstance(target, str):
            parent_of[target] = source
    return parent_of


def _l1_ancestor_id(node_id: str, parent_of: Mapping[str, str]) -> str | None:
    current: str | None = node_id
    last_branch: str | None = None
    while current and current != MINDMAP_TOPIC_ID:
        last_branch = current
        current = parent_of.get(current)
    return last_branch


def mindmap_node_depth_from_connections(
    node_id: str,
    connections: Sequence[Mapping[str, Any]],
) -> int | None:
    """Hop count from ``topic`` to ``node_id``."""
    if node_id == MINDMAP_TOPIC_ID:
        return 0
    parent_of = _parent_of(connections)
    depth = 0
    current: str | None = node_id
    while current and current != MINDMAP_TOPIC_ID:
        parent = parent_of.get(current)
        if parent is None:
            return depth if depth > 0 else None
        depth += 1
        current = parent
    return depth if depth > 0 else None


def is_mindmap_l1(node_id: str, connections: Sequence[Mapping[str, Any]]) -> bool:
    """True when the node's parent is ``topic``."""
    if node_id == MINDMAP_TOPIC_ID:
        return False
    return _parent_of(connections).get(node_id) == MINDMAP_TOPIC_ID


def _nodes_by_id(nodes: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    by_id: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            by_id[node_id] = node
    return by_id


def mindmap_node_side(
    node_id: str,
    *,
    nodes: Sequence[Mapping[str, Any]] | None = None,
    connections: Sequence[Mapping[str, Any]] | None = None,
    node: Mapping[str, Any] | None = None,
) -> MindMapSide | None:
    """Resolve left/right from stamp, topic handle, ancestor, or positional id."""
    resolved = node
    by_id = _nodes_by_id(nodes or ())
    if resolved is None:
        resolved = by_id.get(node_id)
    stamped = read_mindmap_side(resolved)
    if stamped:
        return stamped

    if connections:
        parent_of = _parent_of(connections)
        l1_id = _l1_ancestor_id(node_id, parent_of)
        if l1_id:
            l1_stamped = read_mindmap_side(by_id.get(l1_id))
            if l1_stamped:
                return l1_stamped
            for connection in connections:
                if connection.get("source") == MINDMAP_TOPIC_ID and connection.get("target") == l1_id:
                    from_handle = mindmap_side_from_handle(connection.get("sourceHandle"))
                    if from_handle:
                        return from_handle
                    break
            parsed_l1 = parse_positional_mindmap_branch_id(l1_id)
            if parsed_l1 is not None:
                return mindmap_side_from_char(parsed_l1[0])

    parsed = parse_positional_mindmap_branch_id(node_id)
    if parsed is not None:
        return mindmap_side_from_char(parsed[0])
    return None


def mindmap_node_depth(
    node_id: str,
    *,
    nodes: Sequence[Mapping[str, Any]] | None = None,
    connections: Sequence[Mapping[str, Any]] | None = None,
    node: Mapping[str, Any] | None = None,
) -> int:
    """Resolve 1-based depth from stamp, connections, or positional id."""
    resolved = node
    if resolved is None and nodes is not None:
        resolved = _nodes_by_id(nodes).get(node_id)
    stamped = read_mindmap_depth(resolved)
    if stamped is not None:
        return stamped
    if connections is not None:
        walked = mindmap_node_depth_from_connections(node_id, connections)
        if walked is not None:
            return walked
    parsed = parse_positional_mindmap_branch_id(node_id)
    return parsed[1] if parsed is not None else 1


def mindmap_location_path_key(
    node_id: str,
    connections: Sequence[Mapping[str, Any]],
    *,
    nodes: Sequence[Mapping[str, Any]] | None = None,
) -> str | None:
    """Stable tree path ``r/0/1`` or ``l/0`` from connection order."""
    if node_id == MINDMAP_TOPIC_ID:
        return MINDMAP_TOPIC_ID
    side = mindmap_node_side(node_id, nodes=nodes, connections=connections)
    if side is None:
        return None
    parent_of = _parent_of(connections)
    child_map: dict[str, list[str]] = {}
    for connection in connections:
        source = connection.get("source")
        target = connection.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        child_map.setdefault(source, []).append(target)
    indices: list[int] = []
    current: str | None = node_id
    while current and current != MINDMAP_TOPIC_ID:
        parent = parent_of.get(current)
        if parent is None:
            return None
        siblings = child_map.get(parent, [])
        try:
            indices.insert(0, siblings.index(current))
        except ValueError:
            return None
        current = parent
    return f"{mindmap_side_to_char(side)}/{'/'.join(str(index) for index in indices)}"


def sort_topic_child_ids_by_side(
    child_ids: Sequence[str],
    *,
    nodes: Sequence[Mapping[str, Any]] | None = None,
    connections: Sequence[Mapping[str, Any]] | None = None,
) -> list[str]:
    """Right children first (connection order), then left."""
    if len(child_ids) <= 1:
        return list(child_ids)
    right: list[str] = []
    left: list[str] = []
    other: list[str] = []
    for node_id in child_ids:
        side = mindmap_node_side(node_id, nodes=nodes, connections=connections)
        if side == "right":
            right.append(node_id)
        elif side == "left":
            left.append(node_id)
        else:
            other.append(node_id)
    if not right and not left:
        return list(child_ids)
    return [*right, *left, *other]
