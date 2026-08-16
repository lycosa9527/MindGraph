"""Deep mind-map walk for canvas_tour each_node scope."""

from __future__ import annotations

from typing import Any

from services.mind_classroom.outline import (
    canvas_place_code,
    clean_node_text,
    extract_mindmap_outline,
    sort_child_ids_by_y,
    sort_topic_branch_ids_clockwise,
)


def _node_label(by_id: dict[str, dict[str, Any]], node_id: str) -> str:
    node = by_id.get(node_id) or {}
    return clean_node_text(node.get("text") or node.get("label"))


def _children_map(spec: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]], str]:
    nodes = spec.get("nodes")
    connections = spec.get("connections")
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(nodes, list):
        for node in nodes:
            if not isinstance(node, dict):
                continue
            node_id = node.get("id")
            if isinstance(node_id, str) and node_id:
                by_id[node_id] = node
    children: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    if isinstance(connections, list):
        for conn in connections:
            if not isinstance(conn, dict):
                continue
            source = conn.get("source")
            target = conn.get("target")
            if isinstance(source, str) and isinstance(target, str):
                if source in children and target in by_id:
                    children[source].append(target)
    topic_id = ""
    for node_id, node in by_id.items():
        node_type = str(node.get("type") or "").lower()
        if node_type == "topic" or node_id == "topic":
            topic_id = node_id
            break
    if not topic_id and by_id:
        topic_id = next(iter(by_id))
    return by_id, children, topic_id


def build_tour_nodes(
    spec: dict[str, Any],
    *,
    deep: bool,
    fallback_title: str = "",
) -> list[dict[str, Any]]:
    """
    Build ordered tour nodes: topic, then branches (and descendants if deep).

    Each item: id, text, kind (topic|branch), parent_id, child_texts, descendant_ids.
    """
    outline = extract_mindmap_outline(spec, fallback_title=fallback_title)
    by_id, children, topic_id = _children_map(spec)
    if not by_id or not topic_id:
        return [
            {
                "id": "",
                "text": outline.topic,
                "kind": "topic",
                "parent_id": None,
                "child_texts": [branch.text for branch in outline.branches],
                "descendant_ids": [branch.id for branch in outline.branches if branch.id],
                "place": "center",
                "parent_text": None,
                "sibling_texts": [],
                "stop": "trunk",
            }
        ]

    topic_text = clean_node_text(by_id[topic_id].get("text") or by_id[topic_id].get("label")) or outline.topic
    first_ids = sort_topic_branch_ids_clockwise(list(children.get(topic_id, [])), by_id, topic_id)
    items: list[dict[str, Any]] = [
        {
            "id": topic_id,
            "text": topic_text,
            "kind": "topic",
            "parent_id": None,
            "child_texts": [_node_label(by_id, cid) for cid in first_ids if _node_label(by_id, cid)],
            "descendant_ids": list(first_ids),
            "place": "center",
            "parent_text": None,
            "sibling_texts": [],
            "stop": "trunk",
        }
    ]

    def walk(node_id: str, parent_id: str) -> None:
        node = by_id.get(node_id)
        if not node:
            return
        text = clean_node_text(node.get("text") or node.get("label"))
        if not text:
            return
        kid_ids = sort_child_ids_by_y(list(children.get(node_id, [])), by_id)
        descendant_ids = [node_id]
        if deep:
            stack = list(kid_ids)
            seen = {node_id}
            while stack:
                current = stack.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                descendant_ids.append(current)
                stack.extend(sort_child_ids_by_y(list(children.get(current, [])), by_id))
        else:
            descendant_ids.extend(kid_ids)
        sibling_ids = (
            first_ids
            if parent_id == topic_id
            else sort_child_ids_by_y(
                list(children.get(parent_id, [])),
                by_id,
            )
        )
        parent_text = _node_label(by_id, parent_id)
        sibling_texts = [label for cid in sibling_ids if cid != node_id and (label := _node_label(by_id, cid))]
        child_texts = [label for cid in kid_ids if (label := _node_label(by_id, cid))]
        items.append(
            {
                "id": node_id,
                "text": text,
                "kind": "branch",
                "parent_id": parent_id,
                "parent_text": parent_text or None,
                "sibling_texts": sibling_texts,
                "child_texts": child_texts,
                "descendant_ids": descendant_ids,
                "place": canvas_place_code(node_id, by_id, topic_id, sibling_ids),
                "stop": "leaf" if deep and not kid_ids else "trunk",
            }
        )
        if deep:
            for kid in kid_ids:
                walk(kid, node_id)

    for branch_id in first_ids:
        walk(branch_id, topic_id)
    return items
