"""Classify Thinking Map nodes by type, stamped role, or leftover alias.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict


def node_data(node: Dict[str, Any]) -> Dict[str, Any]:
    """Return node.data when it is a dict."""
    data = node.get("data")
    return data if isinstance(data, dict) else {}


def is_circle_context_node(node: Dict[str, Any]) -> bool:
    """True for a circle-map observation node (UUID or leftover)."""
    nid = str(node.get("id") or "")
    if nid in {"topic", "outer-boundary"}:
        return False
    if node.get("type") == "bubble":
        return True
    data = node_data(node)
    if data.get("circleMapUid") or data.get("circleMapLegacyId"):
        return True
    return nid.startswith("context-") or nid.startswith("context_")


def is_bubble_attribute_node(node: Dict[str, Any]) -> bool:
    """True for a bubble-map attribute node (UUID or leftover)."""
    nid = str(node.get("id") or "")
    if nid == "topic":
        return False
    if node.get("type") in {"bubble", "child"}:
        return True
    data = node_data(node)
    if data.get("bubbleMapUid") or data.get("bubbleMapLegacyId"):
        return True
    return nid.startswith("bubble-")


def double_bubble_role(node: Dict[str, Any]) -> str:
    """Return similarity / leftDiff / rightDiff from stamp or leftover id."""
    stamped = node_data(node).get("doubleBubbleRole")
    if stamped in {"similarity", "leftDiff", "rightDiff"}:
        return str(stamped)
    for candidate in (str(node.get("id") or ""), str(node_data(node).get("doubleBubbleMapLegacyId") or "")):
        if candidate.startswith("similarity-"):
            return "similarity"
        if candidate.startswith("left-diff-"):
            return "leftDiff"
        if candidate.startswith("right-diff-"):
            return "rightDiff"
    return ""


def double_bubble_index(node: Dict[str, Any]) -> int:
    """Column index from groupIndex, or a large sentinel when missing."""
    raw = node_data(node).get("groupIndex")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw
    return 10**9


def is_tree_category_node(node: Dict[str, Any]) -> bool:
    """True for a tree-map category (not a leaf)."""
    data = node_data(node)
    if data.get("nodeType") == "leaf" or isinstance(data.get("leafIndex"), int):
        return False
    if data.get("nodeType") == "branch":
        return True
    if isinstance(data.get("categoryIndex"), int):
        return True
    return str(node.get("id") or "").startswith("tree-cat-")


def is_flow_step_node(node: Dict[str, Any]) -> bool:
    """True for a flow-map step (not a substep)."""
    ntype = str(node.get("type") or "")
    if ntype in {"flow", "step"}:
        return True
    data = node_data(node)
    if ntype in {"flowSubstep", "substep"} or data.get("parentStepId"):
        return False
    if isinstance(data.get("stepIndex"), int) and data.get("substepIndex") is None:
        return True
    return str(node.get("id") or "").startswith("flow-step-")


def is_flow_substep_node(node: Dict[str, Any]) -> bool:
    """True for a flow-map substep."""
    ntype = str(node.get("type") or "")
    if ntype in {"flowSubstep", "substep"}:
        return True
    data = node_data(node)
    if data.get("parentStepId") or isinstance(data.get("substepIndex"), int):
        return True
    return str(node.get("id") or "").startswith("flow-substep-")


def is_multi_cause_node(node: Dict[str, Any]) -> bool:
    """True for a multi-flow cause node."""
    if node_data(node).get("multiFlowRole") == "cause":
        return True
    return str(node.get("id") or "").startswith("cause-")


def is_multi_effect_node(node: Dict[str, Any]) -> bool:
    """True for a multi-flow effect node."""
    if node_data(node).get("multiFlowRole") == "effect":
        return True
    return str(node.get("id") or "").startswith("effect-")


def bridge_pair_index(node: Dict[str, Any]) -> int:
    """Bridge pair index from stamp or leftover ``pair-N-side``."""
    raw = node_data(node).get("pairIndex")
    if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
        return raw
    nid = str(node.get("id") or "")
    if nid.startswith("pair-") and nid.endswith(("-left", "-right")):
        mid = nid[len("pair-") :].rsplit("-", 1)[0]
        if mid.isdigit():
            return int(mid)
    return -1


def bridge_pair_side(node: Dict[str, Any]) -> str:
    """Bridge pair side from stamp or leftover suffix."""
    position = node_data(node).get("position")
    if position in {"left", "right"}:
        return str(position)
    nid = str(node.get("id") or "")
    if nid.endswith("-left"):
        return "left"
    if nid.endswith("-right"):
        return "right"
    return ""
