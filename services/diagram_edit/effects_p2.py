"""P2 scaffold: ExpectedEffect tables for non-mindmap diagram types.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import FrozenSet

from services.diagram_edit.types import MINDMAP_DIAGRAM_TYPES

P2_DIAGRAM_TYPES: FrozenSet[str] = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "flow_map",
        "multi_flow_map",
        "brace_map",
        "bridge_map",
        "concept_map",
    }
)


def is_p2_diagram_type(diagram_type: str) -> bool:
    """Return True when diagram type is scheduled for P2 verify tables."""
    norm = diagram_type.strip().lower()
    if norm == "mind_map":
        norm = "mindmap"
    if norm in MINDMAP_DIAGRAM_TYPES:
        return False
    return norm in P2_DIAGRAM_TYPES
