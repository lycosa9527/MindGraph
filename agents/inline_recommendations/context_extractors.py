"""
Context extractors for inline recommendations.

Extract diagram-specific context (topic, branches, steps, etc.) from nodes and connections
to build focused prompts for AI recommendations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, List, Optional

from utils.placeholder import is_placeholder_text


def _get_node_text(node: Dict[str, Any]) -> str:
    """Extract text from node (text or data.label)."""
    text = node.get("text") or (node.get("data") or {}).get("label")
    return (text or "").strip()


def _has_real_text(node: Dict[str, Any]) -> bool:
    """Check if node has non-placeholder text."""
    t = _get_node_text(node)
    return bool(t) and not is_placeholder_text(t)


def _get_children_texts(
    parent_id: str,
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> List[str]:
    """Get non-placeholder child texts for a parent node."""
    target_ids = {c["target"] for c in connections if c.get("source") == parent_id}
    texts = [_get_node_text(next((x for x in nodes if x.get("id") == tid), {})) for tid in target_ids]
    return [t for t in texts if t and not is_placeholder_text(t)]


def _find_mindmap_branch_context(
    current_node_id: str,
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> tuple:
    """Return (current_branch_id, branch_name, children_texts) for mindmap."""
    current_node = next((n for n in nodes if n.get("id") == current_node_id), None)
    if not current_node:
        return (None, "", [])
    nid = current_node.get("id") or ""
    if nid.startswith("branch-l-1-") or nid.startswith("branch-r-1-"):
        return (
            nid,
            _get_node_text(current_node),
            _get_children_texts(nid, nodes, connections),
        )
    for conn in connections:
        if conn.get("target") == current_node_id:
            pid = conn.get("source")
            parent = next((n for n in nodes if n.get("id") == pid), None)
            if parent and ((pid or "").startswith("branch-l-1-") or (pid or "").startswith("branch-r-1-")):
                return (
                    pid,
                    _get_node_text(parent),
                    _get_children_texts(pid, nodes, connections),
                )
            break
    return (None, "", [])


def extract_mindmap_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract mindmap context for prompt building.

    Returns:
        topic, branch_names, current_branch_id, branch_name, children_texts
    """
    connections = connections or []
    topic_node = next(
        (n for n in nodes if n.get("id") in ("topic", "center", "root") or n.get("type") in ("topic", "center")),
        None,
    )
    topic = _get_node_text(topic_node) if topic_node else ""

    branch_nodes = [
        n
        for n in nodes
        if (n.get("id") or "").startswith("branch-l-1-") or (n.get("id") or "").startswith("branch-r-1-")
    ]
    branch_names = [_get_node_text(n) for n in branch_nodes if _has_real_text(n)]

    branch_id, branch_name, children_texts = (None, "", [])
    if current_node_id:
        branch_id, branch_name, children_texts = _find_mindmap_branch_context(current_node_id, nodes, connections)

    return {
        "topic": topic,
        "branch_names": branch_names,
        "current_branch_id": branch_id,
        "branch_name": branch_name,
        "children_texts": children_texts,
    }


def _find_flow_step_context(
    current_node_id: str,
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> tuple:
    """Return (current_step_id, step_name, substep_texts) for flow map."""
    current_node = next((n for n in nodes if n.get("id") == current_node_id), None)
    if not current_node:
        return (None, "", [])
    nid = current_node.get("id") or ""
    if nid.startswith("flow-step-"):
        return (
            nid,
            _get_node_text(current_node),
            _get_children_texts(nid, nodes, connections),
        )
    if nid.startswith("flow-substep-"):
        for conn in connections:
            if conn.get("target") == current_node_id:
                pid = conn.get("source")
                parent = next((n for n in nodes if n.get("id") == pid), None)
                if parent and (pid or "").startswith("flow-step-"):
                    return (
                        pid,
                        _get_node_text(parent),
                        _get_children_texts(pid, nodes, connections),
                    )
                break
    return (None, "", [])


def extract_flow_map_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract flow map context for prompt building.

    Returns:
        topic, step_names, current_step_id, step_name, substep_texts
    """
    connections = connections or []
    topic_node = next(
        (n for n in nodes if n.get("id") == "flow-topic" or n.get("type") == "topic"),
        None,
    )
    topic = _get_node_text(topic_node) if topic_node else ""

    step_nodes = [n for n in nodes if n.get("type") == "flow" and (n.get("id") or "").startswith("flow-step-")]
    step_names = [_get_node_text(n) for n in step_nodes if _has_real_text(n)]

    step_id, step_name, substep_texts = (None, "", [])
    if current_node_id:
        step_id, step_name, substep_texts = _find_flow_step_context(current_node_id, nodes, connections)

    return {
        "topic": topic,
        "step_names": step_names,
        "current_step_id": step_id,
        "step_name": step_name,
        "substep_texts": substep_texts,
    }


def _find_tree_category_context(
    current_node_id: str,
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> tuple:
    """Return (current_category_id, category_name, item_texts) for tree map."""
    current_node = next((n for n in nodes if n.get("id") == current_node_id), None)
    if not current_node:
        return (None, "", [])
    nid = current_node.get("id") or ""
    if nid.startswith("tree-cat-"):
        return (
            nid,
            _get_node_text(current_node),
            _get_children_texts(nid, nodes, connections),
        )
    for conn in connections:
        if conn.get("target") == current_node_id:
            pid = conn.get("source")
            parent = next((n for n in nodes if n.get("id") == pid), None)
            if parent and (pid or "").startswith("tree-cat-"):
                return (
                    pid,
                    _get_node_text(parent),
                    _get_children_texts(pid, nodes, connections),
                )
            break
    return (None, "", [])


def extract_tree_map_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract tree map context for prompt building.

    Returns:
        topic, dimension, category_names, current_category_id, category_name, item_texts
    """
    connections = connections or []
    topic_node = next(
        (n for n in nodes if n.get("id") in ("tree-topic", "topic") or n.get("type") == "topic"),
        None,
    )
    topic = _get_node_text(topic_node) if topic_node else ""

    dim_node = next(
        (n for n in nodes if n.get("id") == "dimension-label"),
        None,
    )
    dimension = _get_node_text(dim_node) if dim_node else ""
    if is_placeholder_text(dimension):
        dimension = ""

    category_nodes = [n for n in nodes if (n.get("id") or "").startswith("tree-cat-")]
    category_names = [_get_node_text(n) for n in category_nodes if _has_real_text(n)]

    cat_id, category_name, item_texts = (None, "", [])
    if current_node_id:
        cat_id, category_name, item_texts = _find_tree_category_context(current_node_id, nodes, connections)

    return {
        "topic": topic,
        "dimension": dimension,
        "category_names": category_names,
        "current_category_id": cat_id,
        "category_name": category_name,
        "item_texts": item_texts,
    }


def _find_brace_part_context(
    current_node_id: str,
    root_id: Optional[str],
    nodes: List[Dict[str, Any]],
    connections: List[Dict[str, Any]],
) -> tuple:
    """Return (current_part_id, part_name, subpart_texts) for brace map."""
    current_node = next((n for n in nodes if n.get("id") == current_node_id), None)
    if not current_node or not root_id:
        return (None, "", [])
    nid = current_node.get("id") or ""
    is_direct_part = current_node.get("type") == "brace" and any(
        c.get("source") == root_id and c.get("target") == nid for c in connections
    )
    if is_direct_part:
        return (
            nid,
            _get_node_text(current_node),
            _get_children_texts(nid, nodes, connections),
        )
    for conn in connections:
        if conn.get("target") == current_node_id:
            pid = conn.get("source")
            parent = next((n for n in nodes if n.get("id") == pid), None)
            if parent and parent.get("type") == "brace":
                return (
                    pid,
                    _get_node_text(parent),
                    _get_children_texts(pid, nodes, connections),
                )
            break
    return (None, "", [])


def extract_brace_map_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract brace map context for prompt building.

    Returns:
        whole, dimension, part_names, current_part_id, part_name, subpart_texts
    """
    connections = connections or []
    root_ids = {"brace-whole", "brace-0-0", "whole"}
    root_node = next(
        (n for n in nodes if n.get("id") in root_ids or n.get("type") in ("topic", "whole")),
        None,
    )
    whole = _get_node_text(root_node) if root_node else ""

    dim_node = next(
        (n for n in nodes if n.get("id") == "dimension-label"),
        None,
    )
    dimension = _get_node_text(dim_node) if dim_node else ""
    if is_placeholder_text(dimension):
        dimension = ""

    root_id = root_node.get("id") if root_node else None
    direct_parts = [
        n
        for n in nodes
        if n.get("type") == "brace"
        and root_id
        and any(c.get("source") == root_id and c.get("target") == n.get("id") for c in connections)
    ]
    part_names = [_get_node_text(n) for n in direct_parts if _has_real_text(n)]

    part_id, part_name, subpart_texts = (None, "", [])
    if current_node_id:
        part_id, part_name, subpart_texts = _find_brace_part_context(current_node_id, root_id, nodes, connections)

    return {
        "whole": whole,
        "dimension": dimension,
        "part_names": part_names,
        "current_part_id": part_id,
        "part_name": part_name,
        "subpart_texts": subpart_texts,
    }


def extract_circle_map_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract circle map context for prompt building.

    Returns:
        topic, context_texts (existing observation nodes)
    """
    del connections, current_node_id  # Single-level diagram
    topic_node = next(
        (n for n in nodes if n.get("id") == "topic" or n.get("type") in ("topic", "center")),
        None,
    )
    topic = _get_node_text(topic_node) if topic_node else ""

    context_nodes = [
        n
        for n in nodes
        if (n.get("id") or "").startswith("context-")
        and (n.get("type") == "bubble" or (n.get("id") or "").startswith("context-"))
    ]
    context_texts = [_get_node_text(n) for n in context_nodes if _has_real_text(n)]

    return {"topic": topic, "context_texts": context_texts}


def extract_bubble_map_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract bubble map context for prompt building.

    Returns:
        topic, attribute_texts (existing attribute nodes)
    """
    del connections, current_node_id  # Single-level diagram
    topic_node = next(
        (n for n in nodes if n.get("id") == "topic" or n.get("type") in ("topic", "center")),
        None,
    )
    topic = _get_node_text(topic_node) if topic_node else ""

    attr_nodes = [n for n in nodes if (n.get("id") or "").startswith("bubble-")]
    attribute_texts = [_get_node_text(n) for n in attr_nodes if _has_real_text(n)]

    return {"topic": topic, "attribute_texts": attribute_texts}


def _get_double_bubble_difference_texts(
    nodes: List[Dict[str, Any]],
) -> List[str]:
    """Extract difference pair texts (left | right) from double bubble nodes."""
    diff_left = [n for n in nodes if (n.get("id") or "").startswith("left-diff-")]
    diff_right = [n for n in nodes if (n.get("id") or "").startswith("right-diff-")]
    result = []
    for i in range(max(len(diff_left), len(diff_right))):
        ltxt = _get_node_text(diff_left[i]) if i < len(diff_left) else ""
        rtxt = _get_node_text(diff_right[i]) if i < len(diff_right) else ""
        if ltxt and rtxt and not is_placeholder_text(ltxt) and not is_placeholder_text(rtxt):
            result.append(f"{ltxt} | {rtxt}")
    return result


def extract_double_bubble_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract double bubble map context for prompt building.

    Returns:
        left_topic, right_topic, similarity_texts, difference_texts, mode
    """
    del connections  # Unused for double bubble
    left_node = next((n for n in nodes if n.get("id") == "left-topic"), None)
    right_node = next((n for n in nodes if n.get("id") == "right-topic"), None)
    left_topic = _get_node_text(left_node) if left_node else ""
    right_topic = _get_node_text(right_node) if right_node else ""

    sim_nodes = [n for n in nodes if (n.get("id") or "").startswith("similarity-")]
    similarity_texts = [_get_node_text(n) for n in sim_nodes if _has_real_text(n)]
    difference_texts = _get_double_bubble_difference_texts(nodes)

    mode = "similarities"
    if current_node_id and (current_node_id.startswith("left-diff-") or current_node_id.startswith("right-diff-")):
        mode = "differences"

    return {
        "left_topic": left_topic,
        "right_topic": right_topic,
        "similarity_texts": similarity_texts,
        "difference_texts": difference_texts,
        "mode": mode,
    }


def extract_multi_flow_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract multi flow map context for prompt building.

    Returns:
        event (topic), cause_texts, effect_texts, mode
    """
    del connections  # Unused for multi flow
    event_node = next(
        (n for n in nodes if n.get("id") == "event" or n.get("type") == "topic"),
        None,
    )
    event = _get_node_text(event_node) if event_node else ""

    cause_nodes = [n for n in nodes if (n.get("id") or "").startswith("cause-")]
    effect_nodes = [n for n in nodes if (n.get("id") or "").startswith("effect-")]
    cause_texts = [_get_node_text(n) for n in cause_nodes if _has_real_text(n)]
    effect_texts = [_get_node_text(n) for n in effect_nodes if _has_real_text(n)]

    mode = "causes"
    if current_node_id:
        nid = current_node_id
        if nid.startswith("effect-"):
            mode = "effects"
        elif nid.startswith("cause-"):
            mode = "causes"

    return {
        "event": event,
        "cause_texts": cause_texts,
        "effect_texts": effect_texts,
        "mode": mode,
    }


def _get_bridge_pair_texts(nodes: List[Dict[str, Any]]) -> List[str]:
    """Extract pair texts (left | right) from bridge map nodes."""
    pair_indices = set()
    for n in nodes:
        nid = n.get("id") or ""
        if nid.startswith("pair-") and "-left" in nid:
            idx = nid.replace("pair-", "").replace("-left", "")
            if idx.isdigit():
                pair_indices.add(int(idx))
    result = []
    for idx in sorted(pair_indices):
        left_n = next((x for x in nodes if x.get("id") == f"pair-{idx}-left"), None)
        right_n = next((x for x in nodes if x.get("id") == f"pair-{idx}-right"), None)
        lt = _get_node_text(left_n) if left_n else ""
        rt = _get_node_text(right_n) if right_n else ""
        if lt and rt and not is_placeholder_text(lt) and not is_placeholder_text(rt):
            result.append(f"{lt} | {rt}")
    return result


def extract_bridge_map_context(
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract bridge map context for prompt building.

    Returns:
        dimension, pair_texts (existing pairs as "left | right"), stage
    """
    del connections  # Unused for bridge map
    dim_node = next((n for n in nodes if n.get("id") == "dimension-label"), None)
    dimension = _get_node_text(dim_node) if dim_node else ""
    if is_placeholder_text(dimension):
        dimension = ""
    pair_texts = _get_bridge_pair_texts(nodes)
    stage = "dimensions" if current_node_id == "dimension-label" else "pairs"
    return {
        "dimension": dimension,
        "pair_texts": pair_texts,
        "stage": stage,
    }


_EXTRACTORS = {
    "mindmap": extract_mindmap_context,
    "flow_map": extract_flow_map_context,
    "tree_map": extract_tree_map_context,
    "brace_map": extract_brace_map_context,
    "circle_map": extract_circle_map_context,
    "bubble_map": extract_bubble_map_context,
    "double_bubble_map": extract_double_bubble_context,
    "multi_flow_map": extract_multi_flow_context,
    "bridge_map": extract_bridge_map_context,
}


# Keys in context that hold lists of texts already on the diagram (for deduplication)
_DIAGRAM_TEXT_KEYS = (
    "branch_names",
    "children_texts",
    "step_names",
    "substep_texts",
    "category_names",
    "item_texts",
    "part_names",
    "subpart_texts",
    "context_texts",
    "attribute_texts",
    "similarity_texts",
    "difference_texts",
    "cause_texts",
    "effect_texts",
    "pair_texts",
)


def _collect_text_from_item(item: str) -> List[str]:
    """Collect text and parts from item (handles 'left | right' format)."""
    out = [item.strip()]
    if " | " in item:
        out.extend(p for part in item.split("|") if (p := part.strip()))
    return out


def get_diagram_existing_texts(context: Dict[str, Any]) -> List[str]:
    """
    Collect all texts already on the diagram for deduplication.

    Used to filter out recommendations that duplicate existing diagram content.
    For "left | right" format (pair_texts, difference_texts), also adds each part.
    """
    result: List[str] = []
    for key in _DIAGRAM_TEXT_KEYS:
        val = context.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, str) and item.strip():
                    result.extend(_collect_text_from_item(item.strip()))
    for scalar_key in (
        "topic",
        "whole",
        "dimension",
        "branch_name",
        "step_name",
        "category_name",
        "part_name",
    ):
        val = context.get(scalar_key)
        if isinstance(val, str) and val.strip():
            result.append(val.strip())
    return result


def extract_diagram_context(
    diagram_type: str,
    nodes: List[Dict[str, Any]],
    connections: Optional[List[Dict[str, Any]]] = None,
    current_node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Dispatch to diagram-specific context extractor.

    diagram_type: mindmap, flow_map, tree_map, brace_map, circle_map,
    bubble_map, double_bubble_map, multi_flow_map, bridge_map
    """
    dt = (diagram_type or "").strip().lower()
    if dt == "mind_map":
        dt = "mindmap"
    extractor = _EXTRACTORS.get(dt)
    if not extractor:
        return {}
    return extractor(nodes, connections, current_node_id)
