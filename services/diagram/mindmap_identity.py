"""Migrate positional mind-map ids to stable identity ids.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Mapping
from uuid import UUID, uuid4, uuid5

from services.diagram.mindmap_location import (
    MINDMAP_ALIAS_IDS_DATA_KEY,
    MINDMAP_DEPTH_DATA_KEY,
    MINDMAP_LEGACY_ID_DATA_KEY,
    MINDMAP_SIDE_DATA_KEY,
    MINDMAP_TOPIC_ID,
    MINDMAP_UID_DATA_KEY,
    is_leftover_mindmap_branch_id,
    mindmap_node_depth,
    mindmap_node_side,
    parse_positional_mindmap_branch_id,
    read_mindmap_uid,
)
from services.diagram.thinking_map_patterns import is_any_thinking_map_leftover_id

CANVAS_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")

IdMap = dict[str, str]

# uuid5(NAMESPACE_URL, "https://mindgraph.local/mindmap-branch-identity")
_MINDMAP_IDENTITY_NAMESPACE = UUID("f915c4fc-7887-5ebd-b5cf-633c332afe83")


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


def stable_mindmap_identity_id(leftover_id: str) -> str:
    """UUID shared by the server and every client for one leftover branch id."""
    return str(uuid5(_MINDMAP_IDENTITY_NAMESPACE, leftover_id))


def _next_identity_id(claimed: set[str], preferred: str | None, leftover_id: str) -> str:
    if preferred and preferred not in claimed and not is_leftover_mindmap_branch_id(preferred):
        claimed.add(preferred)
        return preferred
    if leftover_id and is_leftover_mindmap_branch_id(leftover_id):
        stable = stable_mindmap_identity_id(leftover_id)
        if stable not in claimed:
            claimed.add(stable)
            return stable
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


def read_mindmap_alias_ids(data: Any) -> list[str]:
    """Peer ids already remembered on a branch. Empty when the field is absent."""
    if not isinstance(data, dict):
        return []
    raw = data.get(MINDMAP_ALIAS_IDS_DATA_KEY)
    if not isinstance(raw, list):
        return []
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        cleaned = item.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def union_mindmap_alias_ids(data: dict[str, Any], peer_ids: list[str], live_id: str) -> None:
    """Keep every peer id that is not the live id itself."""
    current = read_mindmap_alias_ids(data)
    seen = set(current)
    seen.add(live_id)
    for peer in peer_ids:
        if not isinstance(peer, str):
            continue
        cleaned = peer.strip()
        if not cleaned or cleaned in seen or cleaned == live_id:
            continue
        seen.add(cleaned)
        current.append(cleaned)
    if current:
        data[MINDMAP_ALIAS_IDS_DATA_KEY] = current


def remember_mindmap_peer_ids(nodes: list[Any], peer_to_live: Mapping[str, str]) -> None:
    """Attach raw patch ids onto the live branch, including a position-only patch."""
    if not peer_to_live:
        return
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id:
            by_id[node_id] = node
    for raw, live in peer_to_live.items():
        node = by_id.get(live)
        if node is None:
            continue
        union_mindmap_alias_ids(_node_data_mut(node), [raw], live)


def preserve_mindmap_alias_ids(old_node: dict[str, Any], merged: dict[str, Any]) -> None:
    """A full ``data`` spread must not drop peer ids already stored on the survivor."""
    new_data = merged.get("data")
    if not isinstance(new_data, dict):
        return
    peers = read_mindmap_alias_ids(old_node.get("data")) + read_mindmap_alias_ids(new_data)
    union_mindmap_alias_ids(new_data, peers, str(merged.get("id") or ""))


def _absorb_dropped_branch(survivor: dict[str, Any], dropped: dict[str, Any]) -> None:
    """Remember the dropped copy so a later position-only patch still hits the survivor."""
    survivor_id = survivor.get("id")
    if not isinstance(survivor_id, str) or not survivor_id:
        return
    peers: list[str] = []
    dropped_id = dropped.get("id")
    if isinstance(dropped_id, str) and dropped_id.strip():
        peers.append(dropped_id.strip())
    dropped_data = dropped.get("data")
    if isinstance(dropped_data, dict):
        uid = dropped_data.get(MINDMAP_UID_DATA_KEY)
        if isinstance(uid, str) and uid.strip():
            peers.append(uid.strip())
        peers.extend(read_mindmap_alias_ids(dropped_data))
    union_mindmap_alias_ids(_node_data_mut(survivor), peers, survivor_id)


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
        identity = _next_identity_id(claimed, read_mindmap_uid(node), node_id)
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


def _mindmap_identity_tokens(node: dict[str, Any]) -> list[str]:
    """Shared leftover / uid keys. One node never lists the same token twice."""
    node_id = node.get("id")
    if node_id == MINDMAP_TOPIC_ID:
        return []
    raw: list[str] = []
    if isinstance(node_id, str) and node_id and is_leftover_mindmap_branch_id(node_id):
        raw.append("L:" + node_id)
    elif isinstance(node_id, str) and node_id:
        raw.append("U:" + node_id)
    data = node.get("data")
    if isinstance(data, dict):
        legacy = data.get(MINDMAP_LEGACY_ID_DATA_KEY)
        uid = data.get(MINDMAP_UID_DATA_KEY)
        if isinstance(legacy, str) and legacy.strip():
            raw.append("L:" + legacy.strip())
        if isinstance(uid, str) and uid.strip():
            raw.append("U:" + uid.strip())
        for alias in read_mindmap_alias_ids(data):
            prefix = "L:" if is_leftover_mindmap_branch_id(alias) else "U:"
            raw.append(prefix + alias)
    tokens: list[str] = []
    present: set[str] = set()
    for token in raw:
        if token in present:
            continue
        present.add(token)
        tokens.append(token)
    return tokens


def mindmap_nodes_have_duplicate_identity(nodes: list[dict[str, Any]]) -> bool:
    """True when two nodes are the same branch (shared leftover id or uid)."""
    seen: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        for token in _mindmap_identity_tokens(node):
            if token in seen:
                return True
            seen.add(token)
    return False


def _duplicate_index_groups(nodes: list[dict[str, Any]]) -> dict[int, list[int]]:
    """Union nodes that share a leftover id or uid. Earlier index stays the root."""
    parent = list(range(len(nodes)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left == root_right:
            return
        if root_left < root_right:
            parent[root_right] = root_left
        else:
            parent[root_left] = root_right

    seen: dict[str, int] = {}
    for index, node in enumerate(nodes):
        for token in _mindmap_identity_tokens(node):
            previous = seen.get(token)
            if previous is None:
                seen[token] = index
            else:
                union(previous, index)
    groups: dict[int, list[int]] = {}
    for index in range(len(nodes)):
        root = find(index)
        groups.setdefault(root, []).append(index)
    return groups


def _remap_collapsed_connections(
    connections: list[dict[str, Any]],
    id_map: IdMap,
) -> list[dict[str, Any]]:
    """Point edges at the survivor and drop the second tree's copy of the same edge."""
    seen: set[tuple[str, str, str]] = set()
    kept: list[dict[str, Any]] = []
    for connection in connections:
        row = dict(connection)
        source = row.get("source")
        target = row.get("target")
        if isinstance(source, str):
            row["source"] = id_map.get(source, source)
        if isinstance(target, str):
            row["target"] = id_map.get(target, target)
        key = (
            str(row.get("source") or ""),
            str(row.get("target") or ""),
            str(row.get("edgeType") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        edge_id = row.get("id")
        if isinstance(edge_id, str):
            row["id"] = _rewrite_edge_id(edge_id, id_map)
        kept.append(row)
    return kept


def _rewrite_styles_keep_survivor(styles: Any, id_map: IdMap) -> Any:
    """Move style keys onto the survivor without letting the dropped copy win."""
    if not isinstance(styles, dict) or not id_map:
        return styles
    kept: dict[Any, Any] = {key: value for key, value in styles.items() if str(key) not in id_map}
    for key, value in styles.items():
        mapped = id_map.get(str(key))
        if mapped and mapped not in kept:
            kept[mapped] = value
    return kept


def _payload_is_mindmap(payload: dict[str, Any]) -> bool:
    """True for a mind-map document, including one that omitted ``type``."""
    raw = str(payload.get("type") or payload.get("diagram_type") or "")
    if raw in {"mindmap", "mind_map"}:
        return True
    for node in _as_dict_list(payload.get("nodes")):
        data = node.get("data")
        if isinstance(data, dict) and (data.get(MINDMAP_LEGACY_ID_DATA_KEY) or data.get(MINDMAP_UID_DATA_KEY)):
            return True
    return False


def _dedupe_payload_connections(payload: dict[str, Any]) -> None:
    """Keep the first edge for each source/target/kind pair."""
    connections = _as_dict_list(payload.get("connections"))
    if len(connections) < 2:
        return
    seen: set[tuple[str, str, str]] = set()
    kept: list[dict[str, Any]] = []
    changed = False
    for connection in connections:
        key = (
            str(connection.get("source") or ""),
            str(connection.get("target") or ""),
            str(connection.get("edgeType") or ""),
        )
        if key in seen:
            changed = True
            continue
        seen.add(key)
        kept.append(connection)
    if changed:
        payload["connections"] = kept


def collapse_duplicate_mindmap_payload(payload: dict[str, Any]) -> IdMap:
    """Drop a second copy of the same mind-map tree so collab paints one layout."""
    if _payload_is_mindmap(payload):
        _dedupe_payload_connections(payload)
    nodes = _as_dict_list(payload.get("nodes"))
    if len(nodes) < 2 or not mindmap_nodes_have_duplicate_identity(nodes):
        return {}
    id_map: IdMap = {}
    drop: set[int] = set()
    for indexes in _duplicate_index_groups(nodes).values():
        if len(indexes) < 2:
            continue
        survivor_id = nodes[indexes[0]].get("id")
        if not isinstance(survivor_id, str) or not survivor_id:
            continue
        for index in indexes[1:]:
            dropped = nodes[index]
            dropped_id = dropped.get("id")
            if isinstance(dropped_id, str) and dropped_id and dropped_id != survivor_id:
                id_map[dropped_id] = survivor_id
                drop.add(index)
                _absorb_dropped_branch(nodes[indexes[0]], dropped)
    if not drop:
        return {}
    payload["nodes"] = [node for index, node in enumerate(nodes) if index not in drop]
    connections = _as_dict_list(payload.get("connections"))
    if connections:
        payload["connections"] = _remap_collapsed_connections(connections, id_map)
    rewritten = _rewrite_styles_keep_survivor(payload.get("_node_styles"), id_map)
    if rewritten is not payload.get("_node_styles"):
        payload["_node_styles"] = rewritten
    children = payload.get("children")
    if isinstance(children, list):
        payload["children"] = _remap_children_tree(children, id_map)
    return id_map


def mindmap_patch_is_unbound_layout(patch: dict[str, Any]) -> bool:
    """True when a patch has no branch identity and must not create a node."""
    if not isinstance(patch, dict):
        return True
    if patch.get("text") or patch.get("textSecondary") or patch.get("type") or patch.get("data"):
        return False
    return True


def mindmap_patch_live_id(patch: dict[str, Any], aliases: Mapping[str, str]) -> str | None:
    """Live id when ``patch`` is another UUID for a branch the spec already has."""
    raw = patch.get("id")
    if not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip()
    mapped = aliases.get(text)
    if (
        isinstance(mapped, str)
        and mapped.strip()
        and mapped.strip() != text
        and not is_leftover_mindmap_branch_id(mapped.strip())
    ):
        return mapped.strip()
    data = patch.get("data")
    if not isinstance(data, dict):
        return None
    tokens: list[str] = []
    for key in (MINDMAP_LEGACY_ID_DATA_KEY, MINDMAP_UID_DATA_KEY):
        token = data.get(key)
        if isinstance(token, str) and token.strip():
            tokens.append(token.strip())
    tokens.extend(read_mindmap_alias_ids(data))
    for token in tokens:
        live = aliases.get(token)
        if (
            isinstance(live, str)
            and live.strip()
            and live.strip() != text
            and not is_leftover_mindmap_branch_id(live.strip())
        ):
            return live.strip()
    return None


def retarget_divergent_mindmap_patches(
    patches: list[dict[str, Any]],
    aliases: Mapping[str, str],
) -> dict[str, str]:
    """Rewrite a second tree's patch ids onto the live nodes. Returns raw→live."""
    extra: dict[str, str] = {}
    for patch in patches:
        live = mindmap_patch_live_id(patch, {**dict(aliases), **extra})
        if not live:
            continue
        raw = patch.get("id")
        if not isinstance(raw, str) or not raw.strip():
            continue
        extra[raw.strip()] = live
        patch["id"] = live
        data = patch.get("data")
        if not isinstance(data, dict):
            continue
        peers = [raw.strip()]
        uid = data.get(MINDMAP_UID_DATA_KEY)
        if isinstance(uid, str) and uid.strip():
            peers.append(uid.strip())
        stamped = dict(data)
        stamped[MINDMAP_UID_DATA_KEY] = live
        union_mindmap_alias_ids(stamped, peers, live)
        patch["data"] = stamped
    return extra


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
    return (
        bool(CANVAS_UUID_RE.fullmatch(text))
        or is_leftover_mindmap_branch_id(text)
        or is_any_thinking_map_leftover_id(text)
    )


def _claim_alias(aliases: dict[str, str], key: str, node_id: str) -> None:
    """First writer wins so a later duplicate cannot steal the survivor's peer id."""
    cleaned = key.strip()
    if not cleaned or cleaned in aliases:
        return
    aliases[cleaned] = node_id


def identity_aliases(nodes: list[dict[str, Any]]) -> dict[str, str]:
    """Map current id, uid, leftover id, and remembered peer ids to the live node id."""
    aliases: dict[str, str] = {}
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            continue
        _claim_alias(aliases, node_id, node_id)
        uid = read_mindmap_uid(node)
        if uid:
            _claim_alias(aliases, uid, node_id)
        data = node.get("data")
        if not isinstance(data, dict):
            continue
        legacy = data.get(MINDMAP_LEGACY_ID_DATA_KEY)
        if isinstance(legacy, str):
            _claim_alias(aliases, legacy, node_id)
        for alias in read_mindmap_alias_ids(data):
            _claim_alias(aliases, alias, node_id)
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
