"""Migrate leftover Thinking Map ids to UUID live identity.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Mapping

from services.diagram.mindmap_identity import identity_aliases
from services.diagram.thinking_map_patterns import (
    BRACE_MAP_UID_DATA_KEY,
    BRIDGE_MAP_UID_DATA_KEY,
    DOUBLE_BUBBLE_ROLE_DATA_KEY,
    FLOW_MAP_UID_DATA_KEY,
    FLOW_STEP_INDEX_DATA_KEY,
    MULTI_FLOW_ROLE_DATA_KEY,
    MULTI_FLOW_UID_DATA_KEY,
    TREE_CATEGORY_INDEX_DATA_KEY,
    TREE_MAP_UID_DATA_KEY,
    hyphen_alias_for_invented,
    is_any_thinking_map_leftover_id,
    is_leftover_thinking_map_id,
    is_thinking_map_diagram_type,
    leftover_slot_index,
    leftover_slot_role,
    legacy_key_for,
    normalize_diagram_type,
    reserved_ids_for,
    reserved_rewrites_for,
    uid_key_for,
)
from services.diagram.thinking_map_stable_id import (
    CANVAS_UUID_RE,
    IdMap,
    aliases_from_keys,
    as_dict_list,
    migrate_leftover_slot_ids,
    node_data_mut,
    read_stamped_number,
    read_stamped_string,
    remap_children_tree,
    rewrite_connections,
    rewrite_style_keys,
)


def read_thinking_map_uid(diagram_type: str | None, node: dict[str, Any]) -> str | None:
    """Read the stamped uid for this Thinking Map node."""
    if not diagram_type:
        return None
    return read_stamped_string(node.get("data"), uid_key_for(diagram_type))


def diagram_spec_identity_aliases(spec: dict[str, Any] | None) -> dict[str, str]:
    """Mindmap + Thinking Map aliases from a saved/live spec."""
    if not isinstance(spec, dict):
        return {}
    nodes_raw = spec.get("nodes")
    typed = [node for node in nodes_raw if isinstance(node, dict)] if isinstance(nodes_raw, list) else []
    if not typed:
        return {}
    aliases = identity_aliases(typed)
    slug = normalize_diagram_type(str(spec.get("type") or spec.get("diagram_type") or spec.get("diagramType") or ""))
    if is_thinking_map_diagram_type(slug):
        aliases.update(thinking_map_identity_aliases(slug, typed))
    return aliases


def thinking_map_identity_aliases(
    diagram_type: str | None,
    nodes: list[dict[str, Any]],
) -> dict[str, str]:
    """Map live id, uid, leftover, and underscore invented ids to the live id."""
    slug = normalize_diagram_type(diagram_type)
    uid_key = uid_key_for(slug)
    legacy_key = legacy_key_for(slug)
    if not uid_key or not legacy_key:
        return {}
    aliases = aliases_from_keys(nodes, uid_key, legacy_key)
    extra: dict[str, str] = {}
    for hint, live in list(aliases.items()):
        hyphen = hyphen_alias_for_invented(slug, hint)
        if hyphen and hyphen not in aliases:
            extra[hyphen] = live
    aliases.update(extra)
    return aliases


def as_live_thinking_map_node_id(
    diagram_type: str | None,
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
        else:
            hyphen = hyphen_alias_for_invented(diagram_type, text)
            if hyphen and hyphen in aliases:
                text = aliases[hyphen]
    if is_leftover_thinking_map_id(diagram_type, text):
        return None
    return text


def unique_label_thinking_map_id(hint: str, nodes: list[dict[str, Any]]) -> str | None:
    """Resolve a hint to a canvas id when the label is unique."""
    cleaned = hint.strip()
    if not cleaned:
        return None
    hits: list[str] = []
    for node in nodes:
        text = _node_label(node)
        if text == cleaned:
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id:
                hits.append(node_id)
    if len(hits) != 1:
        return None
    return hits[0]


def resolve_thinking_map_alias_id(
    diagram_type: str | None,
    hint: str | None,
    nodes: list[dict[str, Any]],
) -> str | None:
    """Resolve id / uid / leftover invented id (no label match)."""
    if not isinstance(hint, str) or not hint.strip():
        return None
    cleaned = hint.strip()
    aliases = thinking_map_identity_aliases(diagram_type, nodes)
    mapped = aliases.get(cleaned)
    if mapped and not is_leftover_thinking_map_id(diagram_type, mapped):
        return mapped
    hyphen = hyphen_alias_for_invented(diagram_type, cleaned)
    if hyphen:
        mapped = aliases.get(hyphen)
        if mapped and not is_leftover_thinking_map_id(diagram_type, mapped):
            return mapped
    return None


def resolve_thinking_map_identity_id(
    diagram_type: str | None,
    hint: str | None,
    nodes: list[dict[str, Any]],
) -> str | None:
    """Resolve id / uid / leftover / unique label to the live canvas id."""
    if not isinstance(hint, str) or not hint.strip():
        return None
    cleaned = hint.strip()
    mapped = resolve_thinking_map_alias_id(diagram_type, cleaned, nodes)
    if mapped:
        return mapped
    label_id = unique_label_thinking_map_id(cleaned, nodes)
    if label_id and is_leftover_thinking_map_id(diagram_type, label_id):
        return None
    return label_id


def migrate_thinking_map_identity_ids(
    diagram_type: str,
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], IdMap]:
    """Rewrite leftover slot ids to uid / minted UUID and stamp location."""
    slug = normalize_diagram_type(diagram_type)
    if not is_thinking_map_diagram_type(slug):
        return nodes, connections, {}

    next_nodes, next_connections, reserved_map = _rewrite_reserved_roots(slug, nodes, connections)
    leftover_nodes, leftover_connections, leftover_map = migrate_leftover_slot_ids(
        next_nodes,
        next_connections,
        reserved_ids_for(slug),
        lambda node_id: is_leftover_thinking_map_id(slug, node_id),
        uid_key_for(slug),
        legacy_key_for(slug),
    )
    id_map: IdMap = {}
    id_map.update(reserved_map)
    id_map.update(leftover_map)
    stamped = [_stamp_node(slug, node) for node in leftover_nodes]
    return stamped, leftover_connections, id_map


def migrate_thinking_map_diagram_payload(payload: dict[str, Any], diagram_type: str | None) -> IdMap:
    """In-place migrate ``nodes`` / ``connections`` / ``_node_styles`` / ``children``."""
    slug = normalize_diagram_type(diagram_type)
    if not is_thinking_map_diagram_type(slug):
        return {}
    nodes = as_dict_list(payload.get("nodes"))
    connections = as_dict_list(payload.get("connections"))
    if not nodes:
        return {}
    next_nodes, next_connections, id_map = migrate_thinking_map_identity_ids(slug, nodes, connections)
    payload["nodes"] = next_nodes
    if connections:
        payload["connections"] = next_connections
    styles = payload.get("_node_styles")
    rewritten = rewrite_style_keys(styles, id_map)
    if rewritten is not styles:
        payload["_node_styles"] = rewritten
    children = payload.get("children")
    if isinstance(children, list) and id_map:
        payload["children"] = remap_children_tree(children, id_map)
    return id_map


def _rewrite_reserved_roots(
    diagram_type: str,
    nodes: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], IdMap]:
    rewrites = reserved_rewrites_for(diagram_type)
    if not rewrites:
        return nodes, connections, {}
    uid_key = uid_key_for(diagram_type)
    legacy_key = legacy_key_for(diagram_type)
    id_map: IdMap = {}
    next_nodes: list[dict[str, Any]] = []
    for node in nodes:
        node_id = node.get("id")
        if not isinstance(node_id, str) or node_id not in rewrites:
            next_nodes.append(node)
            continue
        reserved = rewrites[node_id]
        id_map[node_id] = reserved
        updated = dict(node)
        updated["id"] = reserved
        data = dict(node_data_mut(updated))
        data[uid_key] = reserved
        data[legacy_key] = node_id
        updated["data"] = data
        next_nodes.append(updated)
    return next_nodes, rewrite_connections(connections, id_map), id_map


def _node_label(node: dict[str, Any]) -> str:
    raw = node.get("text") or node.get("label") or ""
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    data = node.get("data")
    if isinstance(data, dict):
        for key in ("text", "label"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _stamp_node(diagram_type: str, node: dict[str, Any]) -> dict[str, Any]:
    node_id = node.get("id")
    if not isinstance(node_id, str) or node_id in reserved_ids_for(diagram_type):
        return node
    uid_key = uid_key_for(diagram_type)
    data = dict(node_data_mut(node))
    if not read_stamped_string(data, uid_key):
        data[uid_key] = node_id
    _stamp_location_fields(diagram_type, node, data)
    updated = dict(node)
    updated["data"] = data
    return updated


def _stamp_location_fields(diagram_type: str, node: dict[str, Any], data: dict[str, Any]) -> None:
    slug = normalize_diagram_type(diagram_type)
    legacy = read_stamped_string(data, legacy_key_for(slug)) or ""
    index = leftover_slot_index(slug, legacy)
    role = leftover_slot_role(slug, legacy)
    group = read_stamped_number(data, "groupIndex")
    if index >= 0:
        if group < 0:
            data["groupIndex"] = index
    if slug == "double_bubble_map" and role and DOUBLE_BUBBLE_ROLE_DATA_KEY not in data:
        data[DOUBLE_BUBBLE_ROLE_DATA_KEY] = role
    if slug == "tree_map":
        category = read_stamped_number(data, TREE_CATEGORY_INDEX_DATA_KEY)
        if index >= 0:
            if category < 0:
                data[TREE_CATEGORY_INDEX_DATA_KEY] = index
        data.setdefault(TREE_MAP_UID_DATA_KEY, node.get("id"))
        return
    if slug == "flow_map":
        step = read_stamped_number(data, FLOW_STEP_INDEX_DATA_KEY)
        if index >= 0:
            if step < 0:
                data[FLOW_STEP_INDEX_DATA_KEY] = index
        data.setdefault(FLOW_MAP_UID_DATA_KEY, node.get("id"))
        return
    if slug == "multi_flow_map":
        if role and MULTI_FLOW_ROLE_DATA_KEY not in data:
            data[MULTI_FLOW_ROLE_DATA_KEY] = role
        data.setdefault(MULTI_FLOW_UID_DATA_KEY, node.get("id"))
        return
    if slug == "bridge_map":
        pair = read_stamped_number(data, "pairIndex")
        if index >= 0:
            if pair < 0:
                data["pairIndex"] = index
        if role in {"left", "right"}:
            data.setdefault("position", role)
        data.setdefault(BRIDGE_MAP_UID_DATA_KEY, node.get("id"))
        return
    if slug == "brace_map":
        data.setdefault(BRACE_MAP_UID_DATA_KEY, node.get("id"))


def is_machine_thinking_map_id(node_id: str | None) -> bool:
    """True when ``node_id`` is a UUID or leftover invented Thinking Map id."""
    if not isinstance(node_id, str):
        return False
    text = node_id.strip()
    if not text:
        return False
    if CANVAS_UUID_RE.fullmatch(text):
        return True
    return is_any_thinking_map_leftover_id(text)
