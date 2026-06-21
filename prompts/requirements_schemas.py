"""
Per-diagram-type JSON schemas for prompt requirements extraction (stage 2).

Injected into PROMPT_REQUIREMENTS_BASE via get_requirements_schema().

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from utils.prompt_locale import template_lang_for_registry

_REQUIREMENTS_SCHEMA_EN = {
    "mind_map": """mind_map — central field: topic
Case 1 (free): {"topic": "...", "clarity": "clear", "structure_mode": "free", "constraints": ""}
Case 2 (fixed branches): {"topic": "...", "clarity": "clear", "structure_mode": "fixed", "children": ["Branch1", "Branch2"], "constraints": ""}
Example fixed: "北京三日游，四个分支衣食住行" → topic "北京三日游计划", children ["衣","食","住","行"]""",
    "bubble_map": """bubble_map — central field: topic
Case 1: {"topic": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2: {"topic": "...", "structure_mode": "fixed", "attributes": ["attr1", "attr2"], "clarity": "clear", "constraints": ""}""",
    "circle_map": """circle_map — central field: topic
Case 1: {"topic": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2: {"topic": "...", "structure_mode": "fixed", "context": ["item1", "item2"], "clarity": "clear", "constraints": ""}""",
    "double_bubble_map": """double_bubble_map — central fields: left, right
Case 1: {"left": "A", "right": "B", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2 pair: {"left": "苹果", "right": "橙子", "structure_mode": "fixed", "clarity": "clear", "constraints": ""}
Case 2 arrays optional: add similarities, left_differences, right_differences arrays when user lists them""",
    "tree_map": """tree_map — central field: topic; optional dimension
Case 1: {"topic": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2 dimension only: {"topic": "...", "dimension": "栖息地", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2 fixed categories: {"topic": "...", "dimension": "...", "structure_mode": "fixed", "children": ["Cat1", "Cat2"], "clarity": "clear", "constraints": ""}""",
    "brace_map": """brace_map — central field: whole (NOT topic)
Case 1: {"whole": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2: {"whole": "...", "dimension": "...", "structure_mode": "fixed", "parts": ["Part1", "Part2"], "clarity": "clear", "constraints": ""}""",
    "flow_map": """flow_map — central field: title (NOT topic)
Case 1: {"title": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2: {"title": "制作咖啡", "structure_mode": "fixed", "steps": ["磨豆", "萃取", "打奶泡"], "clarity": "clear", "constraints": ""}""",
    "multi_flow_map": """multi_flow_map — central field: event (NOT topic)
Case 1: {"event": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2: {"event": "...", "structure_mode": "fixed", "causes": ["..."], "effects": ["..."], "clarity": "clear", "constraints": ""}""",
    "bridge_map": """bridge_map — optional dimension (relationship pattern)
Case 1: {"topic": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2 dimension: {"dimension": "首都到国家", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2 pairs: {"structure_mode": "fixed", "analogies": [{"left": "巴黎", "right": "法国"}], "clarity": "clear", "constraints": ""}""",
    "concept_map": """concept_map — central field: topic (stub)
Case 1: {"topic": "...", "structure_mode": "free", "clarity": "clear", "constraints": ""}
Case 2: {"topic": "...", "structure_mode": "fixed", "concepts": ["c1", "c2"], "clarity": "clear", "constraints": ""}""",
}

_REQUIREMENTS_SCHEMA_ZH = {
    "mind_map": """mind_map — 中心字段 topic
Case 1: {"topic": "...", "clarity": "clear", "structure_mode": "free", "constraints": ""}
Case 2: {"topic": "北京三日游计划", "structure_mode": "fixed", "children": ["衣","食","住","行"], "clarity": "clear", "constraints": "三日游"}""",
    "bubble_map": """bubble_map — 中心字段 topic
Case 1/2 同 EN，attributes 数组表示用户指定的特征词""",
    "circle_map": """circle_map — 中心字段 topic，context 数组表示联想词""",
    "double_bubble_map": """double_bubble_map — left/right 为两个对比主题；可选 similarities 等数组""",
    "tree_map": """tree_map — topic + dimension；children 为分类标签""",
    "brace_map": """brace_map — 中心字段 whole；parts 为部分名称""",
    "flow_map": """flow_map — 中心字段 title；steps 为有序步骤""",
    "multi_flow_map": """multi_flow_map — 中心字段 event；causes/effects 数组""",
    "bridge_map": """bridge_map — dimension 为关系模式；analogies 为类比对""",
    "concept_map": """concept_map — concepts 数组（stub）""",
}

_DIAGRAM_TYPE_ALIASES = {
    "mindmap": "mind_map",
}


def normalize_diagram_type_for_requirements(diagram_type: str) -> str:
    """Normalize diagram type string for schema lookup."""
    normalized = (diagram_type or "mind_map").strip().lower()
    return _DIAGRAM_TYPE_ALIASES.get(normalized, normalized)


def get_requirements_schema(diagram_type: str, language: str = "zh") -> str:
    """Return type-specific JSON schema fragment for requirements extraction."""
    dtype = normalize_diagram_type_for_requirements(diagram_type)
    registry_lang = template_lang_for_registry(language)
    schemas = _REQUIREMENTS_SCHEMA_ZH if registry_lang == "zh" else _REQUIREMENTS_SCHEMA_EN
    return schemas.get(dtype, schemas.get("mind_map", ""))
