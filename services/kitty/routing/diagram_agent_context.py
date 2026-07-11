"""Full diagram payload for NodeActionAgent prompts (compact JSON, size-capped).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Literal

Lang = Literal["zh", "en"]

_MAX_PAYLOAD_CHARS = 8000
_MAX_NODES = 120
_MAX_CHILDREN_TREE = 120
_MAX_RELATIONSHIPS = 40
_MAX_LIST_ITEMS = 24


def _extract_mindmap_topic(diagram_data: Dict[str, Any]) -> str:
    ctr = diagram_data.get("center")
    if isinstance(ctr, dict):
        text = ctr.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    topic_raw = diagram_data.get("topic")
    if isinstance(topic_raw, str) and topic_raw.strip():
        return topic_raw.strip()
    if ctr and not isinstance(ctr, dict):
        return str(ctr).strip()
    return ""


def _node_display_text(node: Dict[str, Any]) -> str:
    raw = node.get("text") or node.get("label")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    data = node.get("data")
    if isinstance(data, dict):
        for key in ("label", "text"):
            val = data.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return ""


def _compact_node(node: Dict[str, Any]) -> Dict[str, str]:
    entry: Dict[str, str] = {}
    node_id = node.get("id")
    if isinstance(node_id, str) and node_id.strip():
        entry["id"] = node_id.strip()
    text = _node_display_text(node)
    if text:
        entry["text"] = text
    node_type = node.get("type")
    if isinstance(node_type, str) and node_type.strip():
        entry["type"] = node_type.strip()
    return entry


def _compact_children_tree(
    children: Any,
    *,
    limit: int,
    counter: List[int],
) -> List[Any]:
    if not isinstance(children, list) or counter[0] >= limit:
        return []
    out: List[Any] = []
    for item in children:
        if counter[0] >= limit:
            break
        if isinstance(item, str):
            text = item.strip()
            if text:
                out.append(text)
                counter[0] += 1
            continue
        if not isinstance(item, dict):
            continue
        compact: Dict[str, Any] = {}
        node_id = item.get("id")
        if isinstance(node_id, str) and node_id.strip():
            compact["id"] = node_id.strip()
        text = _node_display_text(item)
        if not text:
            raw = item.get("text") or item.get("label")
            if isinstance(raw, str) and raw.strip():
                text = raw.strip()
        if text:
            compact["text"] = text
        nested = item.get("children")
        if isinstance(nested, list) and nested:
            nested_compact = _compact_children_tree(nested, limit=limit, counter=counter)
            if nested_compact:
                compact["children"] = nested_compact
        if compact:
            out.append(compact)
            counter[0] += 1
    return out


def _compact_nodes_from_pinia(nodes: Any, *, limit: int) -> List[Dict[str, str]]:
    if not isinstance(nodes, list):
        return []
    out: List[Dict[str, str]] = []
    for item in nodes:
        if len(out) >= limit:
            break
        if not isinstance(item, dict):
            continue
        entry = _compact_node(item)
        if entry.get("id") or entry.get("text"):
            out.append(entry)
    return out


def _compact_list_field(items: Any, *, limit: int) -> Any:
    if not isinstance(items, list):
        return items
    compact: List[Any] = []
    for item in items[:limit]:
        if isinstance(item, dict):
            text = _node_display_text(item)
            if text:
                compact.append(text)
            elif item.get("text") or item.get("label"):
                compact.append(str(item.get("text") or item.get("label")).strip())
        elif item is not None:
            compact.append(str(item).strip())
    if len(items) > limit:
        return compact + [f"… (+{len(items) - limit} more)"]
    return compact


def build_diagram_agent_payload(
    session_context: Dict[str, Any],
    *,
    diagram_type: str,
) -> Dict[str, Any]:
    """Compact but complete diagram dict for node-action routing."""
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        diagram_data = {}

    payload: Dict[str, Any] = {"diagram_type": diagram_type}

    topic = _extract_mindmap_topic(diagram_data)
    if topic:
        payload["topic"] = topic

    center = diagram_data.get("center")
    if isinstance(center, dict):
        center_text = center.get("text")
        if isinstance(center_text, str) and center_text.strip():
            payload["center"] = {"text": center_text.strip()}
    elif isinstance(center, str) and center.strip():
        payload["center"] = {"text": center.strip()}

    for key in ("left", "right", "title", "event", "whole", "dimension", "focus_question"):
        val = diagram_data.get(key)
        if isinstance(val, str) and val.strip():
            payload[key] = val.strip()

    pinia_nodes = _compact_nodes_from_pinia(diagram_data.get("nodes"), limit=_MAX_NODES)
    if pinia_nodes:
        payload["nodes"] = pinia_nodes

    counter = [0]
    children_tree = _compact_children_tree(
        diagram_data.get("children"),
        limit=_MAX_CHILDREN_TREE,
        counter=counter,
    )
    if children_tree:
        payload["children"] = children_tree

    for key in ("context", "attributes"):
        val = diagram_data.get(key)
        if val:
            payload[key] = _compact_list_field(val, limit=_MAX_LIST_ITEMS)

    rels = diagram_data.get("relationships")
    if isinstance(rels, list) and rels:
        trimmed: List[Any] = []
        for rel in rels[:_MAX_RELATIONSHIPS]:
            if isinstance(rel, dict):
                trimmed.append(
                    {k: rel[k] for k in ("from", "to", "label") if isinstance(rel.get(k), str) and str(rel[k]).strip()}
                )
            elif rel is not None:
                trimmed.append(rel)
        if len(rels) > _MAX_RELATIONSHIPS:
            trimmed.append({"_truncated": len(rels) - _MAX_RELATIONSHIPS})
        payload["relationships"] = trimmed

    selected_raw = session_context.get("selected_nodes")
    if not isinstance(selected_raw, list):
        selected_raw = diagram_data.get("selected_nodes")
    if isinstance(selected_raw, list) and selected_raw:
        selected_entries: List[Dict[str, str]] = []
        for raw in selected_raw[:8]:
            if not isinstance(raw, str) or not raw.strip():
                continue
            resolved = resolve_diagram_node_ref(diagram_data, node_id=raw.strip())
            if resolved:
                selected_entries.append(resolved)
            else:
                selected_entries.append({"node_id": raw.strip()})
        if selected_entries:
            payload["selected"] = selected_entries

    return payload


def diagram_agent_payload_stats(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Counts for debug logs."""
    nodes = payload.get("nodes")
    node_count = len(nodes) if isinstance(nodes, list) else 0
    children = payload.get("children")
    child_count = len(children) if isinstance(children, list) else 0
    selected = payload.get("selected_nodes")
    selected_count = len(selected) if isinstance(selected, list) else 0
    topic = payload.get("topic")
    topic_text = topic if isinstance(topic, str) else ""
    return {
        "node_count": node_count,
        "child_count": child_count,
        "selected_count": selected_count,
        "topic": topic_text,
    }


def serialize_diagram_for_node_action(
    session_context: Dict[str, Any],
    *,
    diagram_type: str,
    lang: Lang = "zh",
    max_chars: int = _MAX_PAYLOAD_CHARS,
) -> tuple[str, bool]:
    """
    Full diagram JSON block for the node-action user prompt.

    Returns (text, was_truncated).
    """
    payload = build_diagram_agent_payload(session_context, diagram_type=diagram_type)
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    truncated = len(raw) > max_chars
    if truncated:
        body = f"{raw[: max_chars - 24]}\n…[truncated for length]…"
    else:
        body = raw

    if lang == "en":
        header = "Current diagram (JSON — ground truth for labels and node ids):"
    else:
        header = "当前导图（JSON，节点名称与 id 以此为准）："
    return f"{header}\n{body}", truncated


def _collect_id_text_pairs(diagram_data: Dict[str, Any]) -> List[tuple[str, str]]:
    """All (id, label) pairs from nodes[] and nested children[]."""
    pairs: List[tuple[str, str]] = []
    seen: set[str] = set()

    def add_pair(node_id: str, label: str) -> None:
        if not node_id or node_id in seen:
            return
        seen.add(node_id)
        pairs.append((node_id, label))

    nodes = diagram_data.get("nodes")
    if isinstance(nodes, list):
        for item in nodes:
            if not isinstance(item, dict):
                continue
            node_id = item.get("id")
            if not isinstance(node_id, str) or not node_id.strip():
                continue
            add_pair(node_id.strip(), _node_display_text(item))

    def walk_children(children: Any) -> None:
        if not isinstance(children, list):
            return
        for item in children:
            if isinstance(item, str):
                continue
            if not isinstance(item, dict):
                continue
            node_id = item.get("id")
            text = _node_display_text(item)
            if not text:
                raw = item.get("text") or item.get("label")
                if isinstance(raw, str):
                    text = raw.strip()
            if isinstance(node_id, str) and node_id.strip():
                add_pair(node_id.strip(), text)
            walk_children(item.get("children"))

    walk_children(diagram_data.get("children"))
    return pairs


def resolve_diagram_node_ref(
    diagram_data: Dict[str, Any],
    *,
    label: str | None = None,
    node_id: str | None = None,
) -> Dict[str, str] | None:
    """
    Resolve a canvas node to stable ``node_id`` + current label.

    Matches exact id, exact label, then substring label (same as voice resolver).
    """
    pairs = _collect_id_text_pairs(diagram_data if isinstance(diagram_data, dict) else {})

    if isinstance(node_id, str) and node_id.strip():
        wanted = node_id.strip()
        for nid, lbl in pairs:
            if nid == wanted:
                return {"node_id": nid, "node_label": lbl or nid}
        return None

    if not isinstance(label, str) or not label.strip():
        return None
    wanted_label = label.strip()
    for nid, lbl in pairs:
        if lbl == wanted_label:
            return {"node_id": nid, "node_label": lbl}
    for nid, lbl in pairs:
        if lbl and (wanted_label in lbl or lbl in wanted_label):
            return {"node_id": nid, "node_label": lbl}
    return None


def enrich_node_action_command(
    command: Dict[str, Any],
    session_context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Attach stable ``node_id`` to node-targeting commands using current diagram_data.

    Labels in ``target`` / ``node_identifier`` are kept for acks; ``node_id`` survives renames.
    """
    if command.get("action") == "clarify_options":
        out = dict(command)
        options = out.get("option_commands")
        if isinstance(options, list):
            out["option_commands"] = [
                enrich_node_action_command(item, session_context) if isinstance(item, dict) else item
                for item in options
            ]
        return out

    action = str(command.get("action") or "")
    follow_raw = command.get("follow_up_actions")
    follow_ups: list[Any] = follow_raw if isinstance(follow_raw, list) else []
    has_follow_ups = bool(follow_ups)
    if action not in (
        "auto_complete_branch",
        "update_node",
        "delete_node",
        "add_node",
        "start_inline_recommendations",
        "select_node",
        "explain_node",
    ):
        if not has_follow_ups:
            return command
        out_follow = dict(command)
        out_follow["follow_up_actions"] = [
            enrich_node_action_command(item, session_context) if isinstance(item, dict) else item for item in follow_ups
        ]
        return out_follow

    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        diagram_data = {}

    out = dict(command)
    if has_follow_ups:
        out["follow_up_actions"] = [
            enrich_node_action_command(item, session_context) if isinstance(item, dict) else item for item in follow_ups
        ]

    # add_node creates a NEW canvas node — never invent node_id from target text.
    if action == "add_node":
        existing_id = out.get("node_id")
        if isinstance(existing_id, str) and existing_id.strip():
            resolved = resolve_diagram_node_ref(diagram_data, node_id=existing_id.strip())
            if resolved:
                out["node_id"] = resolved["node_id"]
            else:
                out.pop("node_id", None)
        parent = out.get("parent_ref")
        if isinstance(parent, str) and parent.strip() and parent.strip() not in ("topic", "center"):
            resolved_parent = resolve_diagram_node_ref(diagram_data, label=parent.strip())
            if not resolved_parent:
                resolved_parent = resolve_diagram_node_ref(diagram_data, node_id=parent.strip())
            if resolved_parent:
                out.setdefault("parent_node_id", resolved_parent["node_id"])
        return out

    existing_id = out.get("node_id")
    if isinstance(existing_id, str) and existing_id.strip():
        resolved = resolve_diagram_node_ref(diagram_data, node_id=existing_id.strip())
        if resolved:
            out["node_id"] = resolved["node_id"]
            if resolved.get("node_label") and not out.get("target"):
                out["target"] = resolved["node_label"]
        else:
            out.pop("node_id", None)
        if out.get("node_id"):
            return out

    ident_raw = out.get("node_identifier") or out.get("target") or out.get("node_label")
    ident = ident_raw.strip() if isinstance(ident_raw, str) else ""
    if not ident:
        selected = session_context.get("selected_nodes")
        if not isinstance(selected, list):
            selected = diagram_data.get("selected_nodes")
        if isinstance(selected, list) and selected:
            first = selected[0]
            if isinstance(first, str) and first.strip():
                resolved = resolve_diagram_node_ref(diagram_data, node_id=first.strip())
                if resolved:
                    out["node_id"] = resolved["node_id"]
                    if resolved.get("node_label"):
                        out.setdefault("target", resolved["node_label"])
        return out

    resolved = resolve_diagram_node_ref(diagram_data, label=ident)
    if not resolved:
        resolved = resolve_diagram_node_ref(diagram_data, node_id=ident)
    if resolved:
        out["node_id"] = resolved["node_id"]
        if resolved.get("node_label"):
            if action in ("auto_complete_branch", "update_node", "delete_node"):
                out.setdefault("target", resolved["node_label"])
            if action == "update_node" and not out.get("node_identifier"):
                out["node_identifier"] = resolved["node_id"]
    return out
