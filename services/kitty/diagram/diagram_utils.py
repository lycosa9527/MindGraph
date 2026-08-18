"""Diagram helpers for voice command handling.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from typing import Any

from services.diagram.mindmap_identity import as_live_mindmap_node_id, identity_aliases
from services.kitty.session.runtime_state import logger

NODE_TARGET_ACTIONS = frozenset(
    {
        "delete_node",
        "select_node",
        "start_inline_recommendations",
        "explain_node",
    }
)


def get_diagram_prefix_map() -> dict[str, str]:
    """
    Get the node ID prefix map for all supported diagram types.
    This ensures consistent node ID generation across the voice agent.

    Returns:
        Dictionary mapping diagram_type to node ID prefix
    """
    return {
        "circle_map": "context",
        "bubble_map": "attribute",
        "double_bubble_map": "node",
        "tree_map": "item",
        "flow_map": "step",
        "multi_flow_map": "step",  # Uses same prefix as flow_map
        "brace_map": "part",
        "bridge_map": "node",  # Bridge maps use node prefix
        "mindmap": "branch",
        "mind_map": "branch",  # Alias for mindmap
        "concept_map": "concept",
    }


def is_paragraph_text(text: str) -> bool:
    """
    Detect if input text is a paragraph (long text for processing) vs a command.

    Criteria:
    - Contains 30+ words OR contains multiple sentences (2+)
    - Not a simple command structure
    - Valid content (not just whitespace)

    Args:
        text: Input text to check

    Returns:
        True if text appears to be a paragraph for processing
    """
    # Input validation
    if not text:
        return False

    text_stripped = text.strip()

    # Must have minimum meaningful content
    if len(text_stripped) < 10:
        return False

    # Must not be too long (prevent abuse)
    if len(text_stripped) > 5000:
        logger.warning(
            "Text too long (%d chars), treating as paragraph but may be truncated",
            len(text_stripped),
        )
        # Still process, but warn

    # Count words (split by whitespace, filter empty strings)
    words = [w for w in text_stripped.split() if w.strip()]
    word_count = len(words)

    # Count sentences (periods, exclamation marks, question marks)
    sentence_endings = len(re.findall(r"[.!?。！？]", text_stripped))

    # Check word count and sentence count
    # Changed from 100 chars to 30 words - more accurate for paragraph detection
    is_long = word_count >= 30
    has_multiple_sentences = sentence_endings >= 2

    # Check if it looks like a command (short, imperative structure)
    command_prefixes = (
        "请",
        "帮我",
        "请帮我",
        "can you",
        "please",
        "change",
        "update",
        "add",
        "delete",
        "select",
    )
    command_suffixes = ("吗", "?", "？")
    is_command_like = (
        word_count < 10
        and sentence_endings <= 1
        and (text_stripped.startswith(command_prefixes) or text_stripped.endswith(command_suffixes))
    )

    # It's a paragraph if it has 30+ words OR has multiple sentences AND doesn't look like a command
    return (is_long or has_multiple_sentences) and not is_command_like


def _voice_node_text(node: object) -> str:
    """Voice node text."""
    if isinstance(node, dict):
        raw = node.get("text") or node.get("label") or ""
        return str(raw).strip()
    if node is None:
        return ""
    return str(node).strip()


def _prefix_node_id(diagram_type: str, index: int) -> str:
    """Prefix node id."""
    prefix_map = get_diagram_prefix_map()
    prefix = prefix_map.get(diagram_type, "node")
    return f"{prefix}_{index}"


def is_mindmap_diagram_type(diagram_type: str | None) -> bool:
    """True when the session is a mind map (UUID identity, never invent branch_N)."""
    return diagram_type in {"mindmap", "mind_map"}


def child_node_live_id(node: object, index: int, diagram_type: str) -> str | None:
    """Prefer the child's live canvas id. Never invent or echo leftover mind-map ids."""
    if isinstance(node, dict):
        raw = node.get("id")
        if isinstance(raw, str) and raw.strip():
            live = raw.strip()
            if is_mindmap_diagram_type(diagram_type):
                return as_live_mindmap_node_id(live)
            return live
    if is_mindmap_diagram_type(diagram_type):
        return None
    return _prefix_node_id(diagram_type, index)


def session_context_child_record(text: str, index: int, diagram_type: str) -> dict[str, Any]:
    """Voice ``children[]`` snapshot. Mind maps omit invented prefix ids."""
    record: dict[str, Any] = {"index": index, "text": text}
    if not is_mindmap_diagram_type(diagram_type):
        record["id"] = _prefix_node_id(diagram_type, index)
    return record


def typed_node_id_by_unique_label(
    node: object,
    typed_nodes: list[dict[str, Any]],
) -> str | None:
    """Resolve a voice child to a canvas id when the label is unique."""
    text = _voice_node_text(node)
    if not text:
        return None
    hits = [item for item in typed_nodes if _voice_node_text(item) == text]
    if len(hits) != 1:
        return None
    raw = hits[0].get("id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None


def resolve_voice_node_reference(
    session_context: dict[str, object],
    diagram_type: str,
    *,
    node_id: str | None = None,
    node_index: int | None = None,
    node_identifier: str | None = None,
    prefer_selected: bool = True,
) -> dict[str, object] | None:
    """
    Resolve ``node_id``, ``node_index``, and ``node_label`` for node-targeting voice commands.

    Falls back to the first ``selected_nodes`` entry when no explicit target is given.
    """
    diagram_data_raw = session_context.get("diagram_data")
    diagram_data: dict[str, Any] = diagram_data_raw if isinstance(diagram_data_raw, dict) else {}
    children_raw = diagram_data.get("children")
    children: list[Any] = children_raw if isinstance(children_raw, list) else []

    selected_raw = session_context.get("selected_nodes")
    if not isinstance(selected_raw, list):
        selected_nodes_raw = diagram_data.get("selected_nodes")
        selected_raw = selected_nodes_raw if isinstance(selected_nodes_raw, list) else []
    selected: list[str] = []
    if isinstance(selected_raw, list):
        selected = [str(item) for item in selected_raw if isinstance(item, str) and item.strip()]

    nodes_raw = diagram_data.get("nodes")
    typed_nodes = [item for item in nodes_raw if isinstance(item, dict)] if isinstance(nodes_raw, list) else []
    aliases = identity_aliases(typed_nodes) if typed_nodes else {}

    if isinstance(node_id, str) and node_id.strip():
        resolved_id = node_id.strip()
        if is_mindmap_diagram_type(diagram_type):
            live = as_live_mindmap_node_id(resolved_id, aliases)
            if live is None:
                return None
            resolved_id = live
        else:
            resolved_id = aliases.get(resolved_id, resolved_id)
        resolved_index: int | None = node_index
        resolved_label = ""
        for idx, node in enumerate(children):
            if isinstance(node, dict) and str(node.get("id") or "") == resolved_id:
                resolved_index = idx
                resolved_label = _voice_node_text(node)
                break
        if not resolved_label:
            for node in typed_nodes:
                if str(node.get("id") or "") == resolved_id:
                    resolved_label = _voice_node_text(node)
                    break
        return {
            "node_id": resolved_id,
            "node_index": resolved_index,
            "node_label": resolved_label,
        }

    if isinstance(node_index, int):
        if 0 <= node_index < len(children):
            node = children[node_index]
            resolved_id = child_node_live_id(node, node_index, diagram_type)
            if not resolved_id:
                resolved_id = typed_node_id_by_unique_label(node, typed_nodes)
            if not resolved_id:
                return None
            return {
                "node_id": str(resolved_id),
                "node_index": node_index,
                "node_label": _voice_node_text(node),
            }
        return None

    ident = (node_identifier or "").strip()
    if ident:
        for idx, node in enumerate(children):
            text = _voice_node_text(node)
            if text and (ident in text or text in ident):
                resolved_id = child_node_live_id(node, idx, diagram_type)
                if not resolved_id:
                    resolved_id = typed_node_id_by_unique_label(node, typed_nodes)
                if not resolved_id:
                    continue
                return {
                    "node_id": str(resolved_id),
                    "node_index": idx,
                    "node_label": text,
                }

    if prefer_selected and selected:
        sel_id = selected[0]
        if is_mindmap_diagram_type(diagram_type):
            live = as_live_mindmap_node_id(sel_id, aliases)
            if live is None:
                return None
            sel_id = live
        else:
            sel_id = aliases.get(sel_id, sel_id)
        for idx, node in enumerate(children):
            if isinstance(node, dict) and str(node.get("id") or "") == sel_id:
                return {
                    "node_id": sel_id,
                    "node_index": idx,
                    "node_label": _voice_node_text(node),
                }
        return {"node_id": sel_id, "node_index": None, "node_label": ""}

    return None
