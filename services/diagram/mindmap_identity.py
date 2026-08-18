"""Migrate positional mind-map ids to stable identity ids.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from uuid import uuid4

from services.diagram.mindmap_location import (
    MINDMAP_DEPTH_DATA_KEY,
    MINDMAP_LEGACY_ID_DATA_KEY,
    MINDMAP_SIDE_DATA_KEY,
    MINDMAP_UID_DATA_KEY,
    is_leftover_mindmap_branch_id,
    mindmap_node_depth,
    mindmap_node_side,
    parse_positional_mindmap_branch_id,
    read_mindmap_uid,
)

CANVAS_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

IdMap = dict[str, str]


def _as_dict_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _claimed_identity_ids(nodes: list[dict[str, Any]]) -> set[str]:
    claimed: set[str] = set()
    for node in nodes:
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id and not is_leftover_mindmap_branch_id(node_id):
            claimed.add(node_id)
            uid = read_mindmap_uid(node)
            if uid:
                claimed.add(uid)
    return claimed


def _next_identity_id(claimed: set[str], preferred: str | None) -> str:
    if preferred and preferred not in claimed:
        claimed.add(preferred)
        return preferred
    minted = str(uuid4())
    while minted in claimed:
        minted = str(uuid4())
    claimed.add(minted)
    return minted


def _node_data_mut(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data")
    if isinstance(data, dict):
        return data
    fresh: dict[str, Any] = {}
    node["data"] = fresh
    return fresh


def _stamp_location(
    node: dict[str, Any],
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> None:
    node_id = node.get("id")
    if not isinstance(node_id, str) or not node_id:
        return
    side = mindmap_node_side(node_id, nodes=nodes, connections=connections, node=node)
    depth = mindmap_node_depth(node_id, nodes=nodes, connections=connections, node=node)
    data = _node_data_mut(node)
    if side:
        data[MINDMAP_SIDE_DATA_KEY] = side
    data[MINDMAP_DEPTH_DATA_KEY] = depth


def _rewrite_edge_id(edge_id: str, id_map: IdMap) -> str:
    next_id = edge_id
    for old_id, new_id in id_map.items():
        if old_id in next_id:
            next_id = next_id.replace(old_id, new_id)
    return next_id


def rewrite_style_keys(styles: Any, id_map: IdMap) -> Any:
    """Rewrite ``_node_styles`` keys through the identity map."""
    if not isinstance(styles, dict) or not id_map:
        return styles
    return {id_map.get(str(key), key): value for key, value in styles.items()}


def remap_id_list(ids: Any, id_map: Mapping[str, str]) -> list[str]:
    """Rewrite a list of node ids; unknown values pass through."""
    if not isinstance(ids, list):
        return []
    out: list[str] = []
    for item in ids:
        if not isinstance(item, str) or not item:
            continue
        out.append(id_map.get(item, item))
    return out


def remap_optional_id(node_id: Any, id_map: Mapping[str, str]) -> str | None:
    """Rewrite one optional node id."""
    if not isinstance(node_id, str) or not node_id:
        return None
    return id_map.get(node_id, node_id)


def migrate_mindmap_identity_ids(
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], IdMap]:
    """Rewrite positional branch ids to ``mindMapUid`` (mint when missing)."""
    id_map: IdMap = {}
    claimed = _claimed_identity_ids(nodes)
    next_nodes: list[dict[str, Any]] = []
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not is_leftover_mindmap_branch_id(node_id):
            next_nodes.append(node)
            continue
        identity = _next_identity_id(claimed, read_mindmap_uid(node))
        id_map[node_id] = identity
        updated = dict(node)
        updated["id"] = identity
        data = dict(_node_data_mut(updated))
        data[MINDMAP_UID_DATA_KEY] = identity
        data[MINDMAP_LEGACY_ID_DATA_KEY] = node_id
        parsed = parse_positional_mindmap_branch_id(node_id)
        if parsed is not None:
            data[MINDMAP_SIDE_DATA_KEY] = "left" if parsed[0] == "l" else "right"
            data[MINDMAP_DEPTH_DATA_KEY] = parsed[1]
        updated["data"] = data
        next_nodes.append(updated)

    if not id_map:
        for node in next_nodes:
            _stamp_location(node, next_nodes, connections)
        return next_nodes, connections, id_map

    next_connections: list[dict[str, Any]] = []
    for connection in connections:
        updated = dict(connection)
        source = updated.get("source")
        target = updated.get("target")
        if isinstance(source, str):
            updated["source"] = id_map.get(source, source)
        if isinstance(target, str):
            updated["target"] = id_map.get(target, target)
        edge_id = updated.get("id")
        if isinstance(edge_id, str):
            updated["id"] = _rewrite_edge_id(edge_id, id_map)
        next_connections.append(updated)

    for node in next_nodes:
        _stamp_location(node, next_nodes, next_connections)
    return next_nodes, next_connections, id_map


def migrate_mindmap_diagram_payload(payload: dict[str, Any]) -> IdMap:
    """In-place migrate ``nodes`` / ``connections`` / ``_node_styles`` on a payload."""
    nodes = _as_dict_list(payload.get("nodes"))
    connections = _as_dict_list(payload.get("connections"))
    if not nodes:
        return {}
    next_nodes, next_connections, id_map = migrate_mindmap_identity_ids(nodes, connections)
    payload["nodes"] = next_nodes
    if connections:
        payload["connections"] = next_connections
    styles = payload.get("_node_styles")
    rewritten = rewrite_style_keys(styles, id_map)
    if rewritten is not styles:
        payload["_node_styles"] = rewritten
    children = payload.get("children")
    if isinstance(children, list) and id_map:
        payload["children"] = _remap_children_tree(children, id_map)
    return id_map


def _remap_children_tree(children: list[Any], id_map: IdMap) -> list[Any]:
    remapped: list[Any] = []
    for item in children:
        if isinstance(item, dict):
            row = dict(item)
            child_id = row.get("id")
            if isinstance(child_id, str):
                row["id"] = id_map.get(child_id, child_id)
            nested = row.get("children")
            if isinstance(nested, list):
                row["children"] = _remap_children_tree(nested, id_map)
            remapped.append(row)
        else:
            remapped.append(item)
    return remapped


def as_live_mindmap_node_id(
    node_id: str | None,
    aliases: Mapping[str, str] | None = None,
) -> str | None:
    """Return a durable canvas id, or None when the value is leftover invented."""
    if not isinstance(node_id, str):
        return None
    text = node_id.strip()
    if not text:
        return None
    if aliases:
        mapped = aliases.get(text)
        if isinstance(mapped, str) and mapped.strip():
            text = mapped.strip()
    if is_leftover_mindmap_branch_id(text):
        return None
    return text


def is_machine_node_id(node_id: str | None) -> bool:
    """True when ``node_id`` is a UUID or leftover invented id, not a user label."""
    if not isinstance(node_id, str):
        return False
    text = node_id.strip()
    if not text:
        return False
    return bool(CANVAS_UUID_RE.fullmatch(text)) or is_leftover_mindmap_branch_id(text)


def identity_aliases(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """Map current id, uid, and leftover invented id to the live node id."""
    aliases: dict[str, str] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        aliases[node_id] = node_id
        uid = read_mindmap_uid(node)
        if uid:
            aliases[uid] = node_id
        data = node.get("data")
        if isinstance(data, dict):
            legacy = data.get(MINDMAP_LEGACY_ID_DATA_KEY)
            if isinstance(legacy, str) and legacy.strip():
                aliases[legacy.strip()] = node_id
    return aliases


def remap_focus_payload(payload: dict[str, Any], id_map: Mapping[str, str]) -> None:
    """Rewrite classroom / Zhihui focus fields on a step or frame dict."""
    if not id_map:
        return
    if "focus_node_ids" in payload:
        payload["focus_node_ids"] = remap_id_list(payload.get("focus_node_ids"), id_map)
    if "focusNodeIds" in payload:
        payload["focusNodeIds"] = remap_id_list(payload.get("focusNodeIds"), id_map)
    branch = remap_optional_id(payload.get("branch_node_id"), id_map)
    if branch is not None:
        payload["branch_node_id"] = branch
    branch_camel = remap_optional_id(payload.get("branchNodeId"), id_map)
    if branch_camel is not None:
        payload["branchNodeId"] = branch_camel
    focus_branch = payload.get("focus_branch")
    if isinstance(focus_branch, str) and focus_branch in id_map:
        payload["focus_branch"] = id_map[focus_branch]
    focus_child = payload.get("focus_child")
    if isinstance(focus_child, str) and focus_child in id_map:
        payload["focus_child"] = id_map[focus_child]
