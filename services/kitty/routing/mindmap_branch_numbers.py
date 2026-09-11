"""Outline numbers for mind-map nodes (1, 1.1) in canvas chrome order.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from services.diagram.mindmap_outline_order import (
    sort_child_ids_by_y,
    sort_topic_branch_ids_clockwise,
)

_UTTER_NO_FIND = re.compile(
    r"第\d+(?:\.\d+)*个?|第[一二三四五六七八九十]+个?"
    r"|\d+(?:\.\d+)+|\d+号|[①-⑳]"
)
_SPOKEN_NO_RE = re.compile(
    r"^(?:第)?"
    r"(?P<body>\d+(?:\.\d+)*|[一二三四五六七八九十]+|[①-⑳])"
    r"(?:[.、．])?"
    r"(?:号|个)?"
    r"(?:分支|节点)?"
    r"$"
)
_CHINESE_ONES = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
_TOPIC_PARENT_IDS = frozenset({"topic", "center", "root"})


def is_branch_numbering_enabled(diagram_data: Dict[str, Any]) -> bool:
    """True when the canvas numbering flag is on."""
    return diagram_data.get("_mindmap_branch_numbering") is True


def spoken_outline_is_explicit(token: str) -> bool:
    """True when the speaker named an ordinal, dotted path, or circled glyph."""
    raw = token.strip()
    if not raw:
        return False
    if "." in raw or raw in _CIRCLED:
        return True
    if raw.startswith("第") or "号" in raw or "个" in raw:
        return True
    return any(glyph in raw for glyph in _CIRCLED)


def build_outline_number_by_id(diagram_data: Dict[str, Any]) -> Dict[str, str]:
    """Map live node id → outline token (``1``, ``1.1``) in canvas chrome order."""
    by_id: Dict[str, str] = {}
    child_map = _children_from_connections(diagram_data)
    if child_map:
        nodes_by_id = _nodes_by_id(diagram_data)
        root = _root_id(child_map, nodes_by_id)
        _walk_connection_tree(child_map, nodes_by_id, root, [], by_id)
        return by_id
    _walk_children_list(diagram_data.get("children"), [], by_id)
    return by_id


def resolve_outline_number_ref(
    diagram_data: Dict[str, Any],
    token: str,
) -> Optional[str]:
    """Return node id for a spoken outline token.

    Dotted paths and explicit ordinals (``第2个`` / ``2号`` / ``①``) always
    resolve. A bare digit such as ``2`` only resolves when numbering chrome is on.
    """
    outline = normalize_spoken_outline(token)
    if not outline:
        return None
    if "." not in outline and not spoken_outline_is_explicit(token) and not is_branch_numbering_enabled(diagram_data):
        return None
    numbers = build_outline_number_by_id(diagram_data)
    for node_id, no in numbers.items():
        if no == outline:
            return node_id
    return None


def outline_ref_mentioned(utterance: str, diagram_data: Dict[str, Any], node_id: str) -> bool:
    """True when the user named this node's outline number."""
    if not node_id:
        return False
    wanted = build_outline_number_by_id(diagram_data).get(node_id)
    if not wanted:
        return False
    text = utterance.strip()
    if not text:
        return False
    numbering_on = is_branch_numbering_enabled(diagram_data)
    for match in _UTTER_NO_FIND.finditer(text):
        spoken = match.group(0)
        outline = normalize_spoken_outline(spoken)
        if outline != wanted:
            continue
        if "." in wanted or spoken_outline_is_explicit(spoken) or numbering_on:
            return True
    if numbering_on or "." in wanted:
        if re.search(rf"(?<!\d){re.escape(wanted)}(?!\d)", text):
            return True
    return False


def normalize_spoken_outline(token: str) -> Optional[str]:
    """Turn ``第2个`` / ``2号`` / ``1.1`` / ``二`` into an outline token."""
    raw = token.strip()
    if not raw:
        return None
    match = _SPOKEN_NO_RE.match(raw)
    if match is None:
        return None
    body = match.group("body")
    if body in _CIRCLED:
        return str(_CIRCLED.index(body) + 1)
    if body.isdigit() or re.fullmatch(r"\d+(?:\.\d+)+", body):
        return body
    chinese = _chinese_to_int(body)
    if chinese is not None:
        return str(chinese)
    return None


def stamp_outline_numbers(payload: Dict[str, Any], diagram_data: Dict[str, Any]) -> None:
    """Add ``no`` onto payload nodes/children when numbering is enabled."""
    if not is_branch_numbering_enabled(diagram_data):
        return
    numbers = build_outline_number_by_id(diagram_data)
    if not numbers:
        return
    payload["numbering"] = True
    nodes = payload.get("nodes")
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id in numbers:
                node["no"] = numbers[node_id]
    _stamp_children(payload.get("children"), numbers)


def _nodes_by_id(diagram_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    nodes = diagram_data.get("nodes")
    out: Dict[str, Dict[str, Any]] = {}
    if not isinstance(nodes, list):
        return out
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str) and node_id.strip():
            out[node_id.strip()] = node
    return out


def _children_from_connections(diagram_data: Dict[str, Any]) -> Dict[str, List[str]]:
    connections = diagram_data.get("connections")
    child_map: Dict[str, List[str]] = {}
    if not isinstance(connections, list):
        return child_map
    seen: set[str] = set()
    for conn in connections:
        if not isinstance(conn, dict):
            continue
        source = conn.get("source")
        target = conn.get("target")
        if not isinstance(source, str) or not isinstance(target, str):
            continue
        src = source.strip()
        tgt = target.strip()
        if not src or not tgt or tgt in {"topic", "center"}:
            continue
        key = f"{src}->{tgt}"
        if key in seen:
            continue
        seen.add(key)
        child_map.setdefault(src, []).append(tgt)
    return child_map


def _root_id(child_map: Dict[str, List[str]], nodes_by_id: Dict[str, Dict[str, Any]]) -> str:
    for candidate in ("topic", "center", "root"):
        if candidate in child_map:
            return candidate
    for node_id, node in nodes_by_id.items():
        node_type = str(node.get("type") or "").lower()
        if node_type in {"topic", "center"}:
            return node_id
    return "topic"


def _ordered_children(
    parent_id: str,
    child_map: Dict[str, List[str]],
    nodes_by_id: Dict[str, Dict[str, Any]],
) -> List[str]:
    kids = list(child_map.get(parent_id) or [])
    if len(kids) <= 1 or not nodes_by_id:
        return kids
    parent = nodes_by_id.get(parent_id) or {}
    is_topic = parent_id in _TOPIC_PARENT_IDS or str(parent.get("type") or "").lower() in {
        "topic",
        "center",
    }
    if is_topic:
        return sort_topic_branch_ids_clockwise(kids, nodes_by_id, parent_id)
    return sort_child_ids_by_y(kids, nodes_by_id)


def _walk_connection_tree(
    child_map: Dict[str, List[str]],
    nodes_by_id: Dict[str, Dict[str, Any]],
    parent_id: str,
    prefix: List[int],
    out: Dict[str, str],
) -> None:
    kids = _ordered_children(parent_id, child_map, nodes_by_id)
    for index, child_id in enumerate(kids, start=1):
        path = prefix + [index]
        out[child_id] = ".".join(str(part) for part in path)
        _walk_connection_tree(child_map, nodes_by_id, child_id, path, out)


def _walk_children_list(children: Any, prefix: List[int], out: Dict[str, str]) -> None:
    if not isinstance(children, list):
        return
    index = 0
    for item in children:
        if not isinstance(item, dict):
            continue
        index += 1
        path = prefix + [index]
        node_id = item.get("id")
        if isinstance(node_id, str) and node_id.strip():
            out[node_id.strip()] = ".".join(str(part) for part in path)
        _walk_children_list(item.get("children"), path, out)


def _stamp_children(children: Any, numbers: Dict[str, str]) -> None:
    if not isinstance(children, list):
        return
    for item in children:
        if not isinstance(item, dict):
            continue
        node_id = item.get("id")
        if isinstance(node_id, str) and node_id in numbers:
            item["no"] = numbers[node_id]
        _stamp_children(item.get("children"), numbers)


def _chinese_to_int(raw: str) -> Optional[int]:
    if raw in _CHINESE_ONES:
        return _CHINESE_ONES[raw]
    if raw.startswith("十") and len(raw) == 2:
        ones = _CHINESE_ONES.get(raw[1])
        return 10 + ones if ones else None
    if raw.endswith("十") and len(raw) == 2:
        tens = _CHINESE_ONES.get(raw[0])
        return tens * 10 if tens else None
    return None
