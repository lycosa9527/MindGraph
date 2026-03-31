"""
Context-aware prompts for inline recommendations.

Diagram-specific prompt builders organized by diagram type.
User is creating a mindmap about X, there are already branch nodes A, B, C.
Generate recommendations for branches or children based on diagram content.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict, List, Optional

from utils.prompt_locale import output_language_instruction

from .brace_map import (
    build_brace_dimensions_prompt,
    build_brace_parts_prompt,
    build_brace_subparts_prompt,
)
from .bridge_map import build_bridge_dimensions_prompt, build_bridge_pairs_prompt
from .bubble_map import build_bubble_attributes_prompt
from .circle_map import build_circle_observations_prompt
from .double_bubble_map import (
    build_double_bubble_differences_prompt,
    build_double_bubble_similarities_prompt,
)
from .flow_map import build_flow_steps_prompt, build_flow_substeps_prompt
from .mindmap import build_mindmap_branches_prompt, build_mindmap_children_prompt
from .multi_flow_map import (
    build_multi_flow_causes_prompt,
    build_multi_flow_effects_prompt,
)
from .tree_map import (
    build_tree_categories_prompt,
    build_tree_dimensions_prompt,
    build_tree_items_prompt,
)

_BUILDERS: Dict[str, Dict[str, Any]] = {
    "mindmap": {
        "branches": build_mindmap_branches_prompt,
        "children": build_mindmap_children_prompt,
    },
    "flow_map": {
        "steps": build_flow_steps_prompt,
        "substeps": build_flow_substeps_prompt,
    },
    "tree_map": {
        "dimensions": build_tree_dimensions_prompt,
        "categories": build_tree_categories_prompt,
        "children": build_tree_items_prompt,
    },
    "brace_map": {
        "dimensions": build_brace_dimensions_prompt,
        "parts": build_brace_parts_prompt,
        "subparts": build_brace_subparts_prompt,
    },
    "circle_map": {
        "observations": build_circle_observations_prompt,
    },
    "bubble_map": {
        "attributes": build_bubble_attributes_prompt,
    },
    "double_bubble_map": {
        "similarities": build_double_bubble_similarities_prompt,
        "differences": build_double_bubble_differences_prompt,
    },
    "multi_flow_map": {
        "causes": build_multi_flow_causes_prompt,
        "effects": build_multi_flow_effects_prompt,
    },
    "bridge_map": {
        "dimensions": build_bridge_dimensions_prompt,
        "pairs": build_bridge_pairs_prompt,
    },
}

_FALLBACK_STAGES = (
    "children",
    "substeps",
    "subparts",
    "observations",
    "attributes",
    "similarities",
    "differences",
    "causes",
    "effects",
    "dimensions",
    "pairs",
)


def build_prompt(
    diagram_type: str,
    stage: str,
    context: Dict[str, Any],
    language: str = "en",
    count: int = 15,
    batch_num: int = 1,
    existing: Optional[List[str]] = None,
) -> str:
    """
    Build prompt for inline recommendations based on diagram type and stage.

    diagram_type: mindmap, flow_map, tree_map, brace_map, circle_map, etc.
    stage: branches, children, steps, substeps, categories, parts, subparts, etc.
    """
    dt = (diagram_type or "").strip().lower()
    if dt == "mind_map":
        dt = "mindmap"
    st = (stage or "").strip().lower()
    existing = existing or []

    stage_builders = _BUILDERS.get(dt, {})
    builder = stage_builders.get(st)
    if not builder:
        for fallback in _FALLBACK_STAGES:
            builder = stage_builders.get(fallback)
            if builder:
                break
    if not builder:
        return ""
    text = builder(context, language, count, batch_num, existing)
    if not text:
        return ""
    return text + output_language_instruction(language)
