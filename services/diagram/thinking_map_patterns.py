"""Leftover slot patterns and reserved roots for the eight Thinking Maps.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re

THINKING_MAP_TYPES = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
    }
)

CIRCLE_TOPIC_NODE_ID = "topic"
CIRCLE_BOUNDARY_NODE_ID = "outer-boundary"
CIRCLE_MAP_UID_DATA_KEY = "circleMapUid"
CIRCLE_MAP_LEGACY_ID_DATA_KEY = "circleMapLegacyId"
CIRCLE_MAP_RESERVED_IDS = frozenset({CIRCLE_TOPIC_NODE_ID, CIRCLE_BOUNDARY_NODE_ID})

BUBBLE_TOPIC_NODE_ID = "topic"
BUBBLE_MAP_UID_DATA_KEY = "bubbleMapUid"
BUBBLE_MAP_LEGACY_ID_DATA_KEY = "bubbleMapLegacyId"
BUBBLE_MAP_RESERVED_IDS = frozenset({BUBBLE_TOPIC_NODE_ID})

DOUBLE_BUBBLE_LEFT_TOPIC_ID = "left-topic"
DOUBLE_BUBBLE_RIGHT_TOPIC_ID = "right-topic"
DOUBLE_BUBBLE_UID_DATA_KEY = "doubleBubbleMapUid"
DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY = "doubleBubbleMapLegacyId"
DOUBLE_BUBBLE_ROLE_DATA_KEY = "doubleBubbleRole"
DOUBLE_BUBBLE_RESERVED_IDS = frozenset({DOUBLE_BUBBLE_LEFT_TOPIC_ID, DOUBLE_BUBBLE_RIGHT_TOPIC_ID})

TREE_TOPIC_NODE_ID = "tree-topic"
TREE_DIMENSION_LABEL_ID = "dimension-label"
TREE_MAP_UID_DATA_KEY = "treeMapUid"
TREE_MAP_LEGACY_ID_DATA_KEY = "treeMapLegacyId"
TREE_CATEGORY_INDEX_DATA_KEY = "categoryIndex"
TREE_LEAF_INDEX_DATA_KEY = "leafIndex"
TREE_PARENT_CATEGORY_ID_DATA_KEY = "parentCategoryId"
TREE_MAP_RESERVED_IDS = frozenset({TREE_TOPIC_NODE_ID, TREE_DIMENSION_LABEL_ID})

BRACE_WHOLE_NODE_ID = "brace-whole"
BRACE_LEFTOVER_WHOLE_ID = "brace-0-0"
BRACE_DIMENSION_LABEL_ID = "dimension-label"
BRACE_MAP_UID_DATA_KEY = "braceMapUid"
BRACE_MAP_LEGACY_ID_DATA_KEY = "braceMapLegacyId"
BRACE_MAP_RESERVED_IDS = frozenset({BRACE_WHOLE_NODE_ID, BRACE_DIMENSION_LABEL_ID})

FLOW_TOPIC_NODE_ID = "flow-topic"
FLOW_MAP_UID_DATA_KEY = "flowMapUid"
FLOW_MAP_LEGACY_ID_DATA_KEY = "flowMapLegacyId"
FLOW_STEP_INDEX_DATA_KEY = "stepIndex"
FLOW_SUBSTEP_INDEX_DATA_KEY = "substepIndex"
FLOW_PARENT_STEP_ID_DATA_KEY = "parentStepId"
FLOW_MAP_RESERVED_IDS = frozenset({FLOW_TOPIC_NODE_ID})

MULTI_FLOW_EVENT_NODE_ID = "event"
MULTI_FLOW_UID_DATA_KEY = "multiFlowMapUid"
MULTI_FLOW_LEGACY_ID_DATA_KEY = "multiFlowMapLegacyId"
MULTI_FLOW_ROLE_DATA_KEY = "multiFlowRole"
MULTI_FLOW_RESERVED_IDS = frozenset({MULTI_FLOW_EVENT_NODE_ID})

BRIDGE_DIMENSION_LABEL_ID = "dimension-label"
BRIDGE_MAP_UID_DATA_KEY = "bridgeMapUid"
BRIDGE_MAP_LEGACY_ID_DATA_KEY = "bridgeMapLegacyId"
BRIDGE_MAP_RESERVED_IDS = frozenset({BRIDGE_DIMENSION_LABEL_ID})

_CONTEXT_LEFTOVER = re.compile(r"^context-(\d+)$")
_BUBBLE_LEFTOVER = re.compile(r"^bubble-(\d+)$")
_SIM_LEFTOVER = re.compile(r"^similarity-(\d+)$")
_LEFT_DIFF_LEFTOVER = re.compile(r"^left-diff-(\d+)$")
_RIGHT_DIFF_LEFTOVER = re.compile(r"^right-diff-(\d+)$")
_TREE_CAT_LEFTOVER = re.compile(r"^tree-cat-(\d+)$")
_TREE_LEAF_LEFTOVER = re.compile(r"^tree-leaf-(\d+)-(\d+)$")
_TREE_NATIVE_CAT = re.compile(r"^cat-(\d+)$")
_TREE_NATIVE_ITEM = re.compile(r"^cat-(\d+)-item-(\d+)$")
_BRACE_PART_LEFTOVER = re.compile(r"^brace-part-(\d+)$")
_BRACE_SUBPART_LEFTOVER = re.compile(r"^brace-subpart-(\d+)-(\d+)$")
_BRACE_DEPTH_LEFTOVER = re.compile(r"^brace-(\d+)-(\d+)$")
_BRACE_NATIVE_PART = re.compile(r"^part-(\d+)$")
_BRACE_NATIVE_SUB = re.compile(r"^part-(\d+)-sp-(\d+)$")
_FLOW_STEP_LEFTOVER = re.compile(r"^flow-step-(\d+)$")
_FLOW_SUBSTEP_LEFTOVER = re.compile(r"^flow-substep-(\d+)-(\d+)$")
_CAUSE_LEFTOVER = re.compile(r"^cause-(\d+)$")
_EFFECT_LEFTOVER = re.compile(r"^effect-(\d+)$")
_PAIR_LEFTOVER = re.compile(r"^pair-(\d+)-(left|right)$")
_BRIDGE_NATIVE_PAIR = re.compile(r"^bridge-([LR])-(\d+)$")
_UNDERSCORE_SLOT = re.compile(r"^([a-zA-Z][\w]*)_(\d+)$")

_UNDERSCORE_PREFIXES = frozenset(
    {
        "context",
        "attribute",
        "bubble",
        "node",
        "item",
        "category",
        "step",
        "cause",
        "effect",
        "part",
        "subpart",
        "similarity",
        "left",
        "right",
    }
)

_RESERVED_REWRITES: dict[str, dict[str, str]] = {
    "tree_map": {"tree-main": TREE_TOPIC_NODE_ID},
    "brace_map": {BRACE_LEFTOVER_WHOLE_ID: BRACE_WHOLE_NODE_ID},
    "multi_flow_map": {"multi-event": MULTI_FLOW_EVENT_NODE_ID},
    "bridge_map": {"bridge-rel": BRIDGE_DIMENSION_LABEL_ID},
}

_UID_KEYS: dict[str, str] = {
    "circle_map": CIRCLE_MAP_UID_DATA_KEY,
    "bubble_map": BUBBLE_MAP_UID_DATA_KEY,
    "double_bubble_map": DOUBLE_BUBBLE_UID_DATA_KEY,
    "tree_map": TREE_MAP_UID_DATA_KEY,
    "brace_map": BRACE_MAP_UID_DATA_KEY,
    "flow_map": FLOW_MAP_UID_DATA_KEY,
    "multi_flow_map": MULTI_FLOW_UID_DATA_KEY,
    "bridge_map": BRIDGE_MAP_UID_DATA_KEY,
}

_LEGACY_KEYS: dict[str, str] = {
    "circle_map": CIRCLE_MAP_LEGACY_ID_DATA_KEY,
    "bubble_map": BUBBLE_MAP_LEGACY_ID_DATA_KEY,
    "double_bubble_map": DOUBLE_BUBBLE_LEGACY_ID_DATA_KEY,
    "tree_map": TREE_MAP_LEGACY_ID_DATA_KEY,
    "brace_map": BRACE_MAP_LEGACY_ID_DATA_KEY,
    "flow_map": FLOW_MAP_LEGACY_ID_DATA_KEY,
    "multi_flow_map": MULTI_FLOW_LEGACY_ID_DATA_KEY,
    "bridge_map": BRIDGE_MAP_LEGACY_ID_DATA_KEY,
}

_RESERVED_BY_TYPE: dict[str, frozenset[str]] = {
    "circle_map": CIRCLE_MAP_RESERVED_IDS,
    "bubble_map": BUBBLE_MAP_RESERVED_IDS,
    "double_bubble_map": DOUBLE_BUBBLE_RESERVED_IDS,
    "tree_map": TREE_MAP_RESERVED_IDS,
    "brace_map": BRACE_MAP_RESERVED_IDS,
    "flow_map": FLOW_MAP_RESERVED_IDS,
    "multi_flow_map": MULTI_FLOW_RESERVED_IDS,
    "bridge_map": BRIDGE_MAP_RESERVED_IDS,
}


def normalize_diagram_type(diagram_type: str | None) -> str:
    """Normalize hyphen aliases to underscore slugs."""
    if not isinstance(diagram_type, str):
        return ""
    return diagram_type.strip().lower().replace("-", "_")


def is_thinking_map_diagram_type(diagram_type: str | None) -> bool:
    """True for the eight Thinking Maps."""
    return normalize_diagram_type(diagram_type) in THINKING_MAP_TYPES


def reserved_ids_for(diagram_type: str) -> frozenset[str]:
    """Reserved live roots that must not remint."""
    return _RESERVED_BY_TYPE.get(normalize_diagram_type(diagram_type), frozenset())


def uid_key_for(diagram_type: str) -> str:
    """Per-map uid data key."""
    return _UID_KEYS.get(normalize_diagram_type(diagram_type), "")


def legacy_key_for(diagram_type: str) -> str:
    """Per-map leftover alias data key."""
    return _LEGACY_KEYS.get(normalize_diagram_type(diagram_type), "")


def reserved_rewrites_for(diagram_type: str) -> dict[str, str]:
    """Leftover ids that become reserved roots (not UUIDs)."""
    return dict(_RESERVED_REWRITES.get(normalize_diagram_type(diagram_type), {}))


def _is_underscore_invented(node_id: str) -> bool:
    match = _UNDERSCORE_SLOT.fullmatch(node_id)
    if not match:
        return False
    return match.group(1) in _UNDERSCORE_PREFIXES


def is_leftover_circle_map_id(node_id: str | None) -> bool:
    """True for ``context-N`` / ``context_N``."""
    if not isinstance(node_id, str) or not node_id:
        return False
    return bool(_CONTEXT_LEFTOVER.fullmatch(node_id)) or (
        _is_underscore_invented(node_id) and node_id.startswith("context_")
    )


def is_leftover_bubble_map_id(node_id: str | None) -> bool:
    """True for ``bubble-N`` / ``attribute_N`` / ``bubble_N``."""
    if not isinstance(node_id, str) or not node_id:
        return False
    return bool(_BUBBLE_LEFTOVER.fullmatch(node_id)) or (
        _is_underscore_invented(node_id) and node_id.startswith(("attribute_", "bubble_"))
    )


def is_leftover_double_bubble_id(node_id: str | None) -> bool:
    """True for similarity / diff leftover slot ids."""
    if not isinstance(node_id, str) or not node_id:
        return False
    if (
        _SIM_LEFTOVER.fullmatch(node_id)
        or _LEFT_DIFF_LEFTOVER.fullmatch(node_id)
        or _RIGHT_DIFF_LEFTOVER.fullmatch(node_id)
    ):
        return True
    return _is_underscore_invented(node_id) and node_id.startswith(("similarity_", "node_", "left_", "right_"))


def is_leftover_tree_map_id(node_id: str | None) -> bool:
    """True for tree leftover / native-spec invented ids."""
    if not isinstance(node_id, str) or not node_id:
        return False
    if node_id == "tree-main":
        return False
    if (
        _TREE_CAT_LEFTOVER.fullmatch(node_id)
        or _TREE_LEAF_LEFTOVER.fullmatch(node_id)
        or _TREE_NATIVE_CAT.fullmatch(node_id)
        or _TREE_NATIVE_ITEM.fullmatch(node_id)
    ):
        return True
    return _is_underscore_invented(node_id) and node_id.startswith(("item_", "category_"))


def is_leftover_brace_map_id(node_id: str | None) -> bool:
    """True for brace leftover / native-spec invented ids (not the reserved whole)."""
    if not isinstance(node_id, str) or not node_id:
        return False
    if node_id == BRACE_LEFTOVER_WHOLE_ID:
        return True
    if (
        _BRACE_PART_LEFTOVER.fullmatch(node_id)
        or _BRACE_SUBPART_LEFTOVER.fullmatch(node_id)
        or _BRACE_DEPTH_LEFTOVER.fullmatch(node_id)
        or _BRACE_NATIVE_PART.fullmatch(node_id)
        or _BRACE_NATIVE_SUB.fullmatch(node_id)
    ):
        return True
    return _is_underscore_invented(node_id) and node_id.startswith(("part_", "subpart_"))


def is_leftover_flow_map_id(node_id: str | None) -> bool:
    """True for ``flow-step-N`` / ``flow-substep-N-M`` / ``step_N``."""
    if not isinstance(node_id, str) or not node_id:
        return False
    if _FLOW_STEP_LEFTOVER.fullmatch(node_id) or _FLOW_SUBSTEP_LEFTOVER.fullmatch(node_id):
        return True
    return _is_underscore_invented(node_id) and node_id.startswith("step_")


def is_leftover_multi_flow_map_id(node_id: str | None) -> bool:
    """True for ``cause-N`` / ``effect-N`` / ``step_N``."""
    if not isinstance(node_id, str) or not node_id:
        return False
    if node_id == "multi-event":
        return False
    if _CAUSE_LEFTOVER.fullmatch(node_id) or _EFFECT_LEFTOVER.fullmatch(node_id):
        return True
    return _is_underscore_invented(node_id) and node_id.startswith(("cause_", "effect_", "step_"))


def is_leftover_bridge_map_id(node_id: str | None) -> bool:
    """True for ``pair-N-left/right`` / ``bridge-L-N`` / ``node_N``."""
    if not isinstance(node_id, str) or not node_id:
        return False
    if node_id == "bridge-rel":
        return False
    if _PAIR_LEFTOVER.fullmatch(node_id) or _BRIDGE_NATIVE_PAIR.fullmatch(node_id):
        return True
    return _is_underscore_invented(node_id) and node_id.startswith("node_")


_LEFTOVER_BY_TYPE = {
    "circle_map": is_leftover_circle_map_id,
    "bubble_map": is_leftover_bubble_map_id,
    "double_bubble_map": is_leftover_double_bubble_id,
    "tree_map": is_leftover_tree_map_id,
    "brace_map": is_leftover_brace_map_id,
    "flow_map": is_leftover_flow_map_id,
    "multi_flow_map": is_leftover_multi_flow_map_id,
    "bridge_map": is_leftover_bridge_map_id,
}


def is_leftover_thinking_map_id(diagram_type: str | None, node_id: str | None) -> bool:
    """True when ``node_id`` is a leftover slot for this Thinking Map."""
    checker = _LEFTOVER_BY_TYPE.get(normalize_diagram_type(diagram_type))
    if checker is None:
        return False
    return checker(node_id)


def is_any_thinking_map_leftover_id(node_id: str | None) -> bool:
    """True when ``node_id`` matches any Thinking Map leftover pattern."""
    if not isinstance(node_id, str) or not node_id:
        return False
    return any(checker(node_id) for checker in _LEFTOVER_BY_TYPE.values()) or node_id in {
        "tree-main",
        "multi-event",
        "bridge-rel",
        BRACE_LEFTOVER_WHOLE_ID,
    }


def hyphen_alias_for_invented(diagram_type: str | None, node_id: str) -> str | None:
    """Map Kitty underscore invented ids onto FE hyphen leftovers."""
    match = _UNDERSCORE_SLOT.fullmatch(node_id)
    if not match:
        return None
    prefix = match.group(1)
    index = match.group(2)
    slug = normalize_diagram_type(diagram_type)
    if slug == "circle_map" and prefix == "context":
        return f"context-{index}"
    if slug == "bubble_map" and prefix in {"attribute", "bubble"}:
        return f"bubble-{index}"
    if slug == "double_bubble_map":
        if prefix in {"similarity", "node"}:
            return f"similarity-{index}"
        if prefix == "left":
            return f"left-diff-{index}"
        if prefix == "right":
            return f"right-diff-{index}"
    if slug == "tree_map" and prefix in {"item", "category"}:
        return f"tree-cat-{index}"
    if slug == "flow_map" and prefix in {"step", "flow"}:
        return f"flow-step-{index}"
    if slug == "multi_flow_map":
        if prefix == "cause":
            return f"cause-{index}"
        if prefix == "effect":
            return f"effect-{index}"
        if prefix == "step":
            return f"cause-{index}"
    if slug == "brace_map":
        if prefix == "part":
            return f"brace-part-{index}"
        if prefix == "subpart":
            return f"brace-subpart-{index}"
    if slug == "bridge_map" and prefix == "node":
        return f"pair-{index}-left"
    return None


def leftover_slot_index(diagram_type: str | None, node_id: str) -> int:
    """Parse a leftover slot index from a hyphen or underscore invented id."""
    if not node_id:
        return -1
    hyphen = hyphen_alias_for_invented(diagram_type, node_id) or node_id
    for pattern in (
        _CONTEXT_LEFTOVER,
        _BUBBLE_LEFTOVER,
        _SIM_LEFTOVER,
        _LEFT_DIFF_LEFTOVER,
        _RIGHT_DIFF_LEFTOVER,
        _TREE_CAT_LEFTOVER,
        _BRACE_PART_LEFTOVER,
        _BRACE_NATIVE_PART,
        _FLOW_STEP_LEFTOVER,
        _CAUSE_LEFTOVER,
        _EFFECT_LEFTOVER,
        _TREE_NATIVE_CAT,
    ):
        match = pattern.fullmatch(hyphen)
        if match:
            return int(match.group(1))
    pair = _PAIR_LEFTOVER.fullmatch(hyphen)
    if pair:
        return int(pair.group(1))
    native_pair = _BRIDGE_NATIVE_PAIR.fullmatch(hyphen)
    if native_pair:
        return int(native_pair.group(2))
    leaf = _TREE_LEAF_LEFTOVER.fullmatch(hyphen)
    if leaf:
        return int(leaf.group(1))
    sub = _FLOW_SUBSTEP_LEFTOVER.fullmatch(hyphen)
    if sub:
        return int(sub.group(1))
    brace_sub = _BRACE_SUBPART_LEFTOVER.fullmatch(hyphen)
    if brace_sub:
        return int(brace_sub.group(1))
    return -1


def leftover_slot_role(diagram_type: str | None, node_id: str) -> str | None:
    """Parse leftover role (double-bubble / multi-flow / bridge side)."""
    del diagram_type
    if not node_id:
        return None
    if _SIM_LEFTOVER.fullmatch(node_id) or node_id.startswith("similarity_"):
        return "similarity"
    if _LEFT_DIFF_LEFTOVER.fullmatch(node_id) or node_id.startswith("left_"):
        return "leftDiff"
    if _RIGHT_DIFF_LEFTOVER.fullmatch(node_id) or node_id.startswith("right_"):
        return "rightDiff"
    if _CAUSE_LEFTOVER.fullmatch(node_id) or node_id.startswith("cause_"):
        return "cause"
    if _EFFECT_LEFTOVER.fullmatch(node_id) or node_id.startswith("effect_"):
        return "effect"
    pair = _PAIR_LEFTOVER.fullmatch(node_id)
    if pair:
        return pair.group(2)
    native_pair = _BRIDGE_NATIVE_PAIR.fullmatch(node_id)
    if native_pair:
        return "left" if native_pair.group(1) == "L" else "right"
    return None


def topic_node_id_for(diagram_type: str | None) -> str:
    """Reserved center / whole / event id for this Thinking Map."""
    slug = normalize_diagram_type(diagram_type)
    mapping = {
        "circle_map": CIRCLE_TOPIC_NODE_ID,
        "bubble_map": BUBBLE_TOPIC_NODE_ID,
        "double_bubble_map": DOUBLE_BUBBLE_LEFT_TOPIC_ID,
        "tree_map": TREE_TOPIC_NODE_ID,
        "brace_map": BRACE_WHOLE_NODE_ID,
        "flow_map": FLOW_TOPIC_NODE_ID,
        "multi_flow_map": MULTI_FLOW_EVENT_NODE_ID,
        "bridge_map": BRIDGE_DIMENSION_LABEL_ID,
    }
    return mapping.get(slug, "topic")
