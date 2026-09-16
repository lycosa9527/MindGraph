"""Shared mint / rewrite helpers for Thinking Map dual ids.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any
from uuid import uuid4

CANVAS_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

IdMap = dict[str, str]
IsLeftover = Callable[[str | None], bool]


def as_dict_list(raw: Any) -> list[dict[str, Any]]:
    """Return dict rows from a list-like payload field."""
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def node_data_mut(node: dict[str, Any]) -> dict[str, Any]:
    """Return a mutable ``data`` dict on ``node``."""
    data = node.get("data")
    if isinstance(data, dict):
        return data
    fresh: dict[str, Any] = {}
    node["data"] = fresh
    return fresh


def read_stamped_string(data: Any, key: str) -> str | None:
    """Read a non-empty string stamp from node data."""
    if not isinstance(data, dict):
        return None
    value = data.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def read_stamped_number(data: Any, key: str) -> int:
    """Read a non-negative int stamp, or ``-1`` when missing."""
    if not isinstance(data, dict):
        return -1
    value = data.get(key)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return -1


def take_thinking_map_stable_id(
    claimed: set[str],
    is_leftover: IsLeftover,
    preferred: str | None = None,
) -> str:
    """Keep a non-leftover preferred id or mint a UUID."""
    if preferred and not is_leftover(preferred) and preferred not in claimed:
        claimed.add(preferred)
        return preferred
    minted = str(uuid4())
    while minted in claimed:
        minted = str(uuid4())
    claimed.add(minted)
    return minted


def rewrite_style_keys(styles: Any, id_map: IdMap) -> Any:
    """Rewrite ``_node_styles`` keys through the identity map."""
    if not isinstance(styles, dict) or not id_map:
        return styles
    return {id_map.get(str(key), key): value for key, value in styles.items()}


def rewrite_edge_id(edge_id: str, id_map: IdMap) -> str:
    """Rewrite concatenated edge ids that embed old node ids."""
    next_id = edge_id
    for old_id, new_id in id_map.items():
        if old_id in next_id:
            next_id = next_id.replace(old_id, new_id)
    return next_id


def rewrite_connections(connections: list[dict[str, Any]], id_map: IdMap) -> list[dict[str, Any]]:
    """Rewrite connection endpoints and edge ids."""
    if not id_map:
        return connections
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
            updated["id"] = rewrite_edge_id(edge_id, id_map)
        next_connections.append(updated)
    return next_connections


def remap_children_tree(children: list[Any], id_map: IdMap) -> list[Any]:
    """Rewrite nested ``children[].id`` through the identity map."""
    remapped: list[Any] = []
    for item in children:
        if isinstance(item, dict):
            row = dict(item)
            child_id = row.get("id")
            if isinstance(child_id, str):
                row["id"] = id_map.get(child_id, child_id)
            nested = row.get("children")
            if isinstance(nested, list):
                row["children"] = remap_children_tree(nested, id_map)
            remapped.append(row)
        else:
            remapped.append(item)
    return remapped


def aliases_from_keys(
    nodes: list[dict[str, Any]],
    uid_key: str,
    legacy_key: str,
) -> dict[str, str]:
    """Map live id, uid, and leftover invented id to the live node id."""
    aliases: dict[str, str] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        aliases[node_id] = node_id
        data = node.get("data")
        uid = read_stamped_string(data, uid_key)
        if uid:
            aliases[uid] = node_id
        legacy = read_stamped_string(data, legacy_key)
        if legacy:
            aliases[legacy] = node_id
    return aliases


def migrate_leftover_slot_ids(
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
    reserved_ids: frozenset[str] | set[str],
    is_leftover: IsLeftover,
    uid_key: str,
    legacy_key: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], IdMap]:
    """Rewrite leftover slot ids to existing uid or a minted UUID."""
    id_map: IdMap = {}
    claimed: set[str] = set(reserved_ids)
    for node in nodes:
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id and not is_leftover(node_id):
            claimed.add(node_id)
        uid = read_stamped_string(node.get("data"), uid_key)
        if uid:
            claimed.add(uid)

    next_nodes: list[dict[str, Any]] = []
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id or node_id in reserved_ids or not is_leftover(node_id):
            next_nodes.append(node)
            continue
        identity = take_thinking_map_stable_id(
            claimed,
            is_leftover,
            read_stamped_string(node.get("data"), uid_key),
        )
        id_map[node_id] = identity
        updated = dict(node)
        updated["id"] = identity
        data = dict(node_data_mut(updated))
        data[uid_key] = identity
        data[legacy_key] = node_id
        updated["data"] = data
        next_nodes.append(updated)

    next_connections = rewrite_connections(connections, id_map) if id_map else connections
    return next_nodes, next_connections, id_map
