"""Durable library draft specs for Kitty create / open_desktop_canvas.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict


def build_kitty_library_draft_spec(
    diagram_type: str,
    *,
    topic: str = "",
    left: str = "",
    right: str = "",
) -> Dict[str, Any]:
    """
    Minimal native library spec for a new durable draft.

    Matches Vue default-template *shape* (topic/children, etc.) so desktop
    ``loadFromSpec`` can hydrate without requiring a full template tree.
    """
    dt = (diagram_type or "mindmap").strip().replace("-", "_")
    topic_text = (topic or "").strip()
    left_text = (left or "").strip()
    right_text = (right or "").strip()

    if dt in ("mindmap", "mind_map"):
        return {"topic": topic_text, "children": []}
    if dt == "circle_map":
        return {"topic": topic_text, "context": []}
    if dt == "bubble_map":
        return {"topic": topic_text, "attributes": []}
    if dt == "double_bubble_map":
        return {
            "left": left_text or topic_text,
            "right": right_text or "",
            "similarities": [],
            "left_differences": [],
            "right_differences": [],
        }
    if dt == "tree_map":
        return {
            "topic": topic_text,
            "dimension": "",
            "alternative_dimensions": [],
            "children": [],
        }
    if dt == "brace_map":
        return {"whole": topic_text, "dimension": "", "parts": []}
    if dt == "flow_map":
        return {"title": topic_text, "steps": [], "substeps": []}
    if dt == "multi_flow_map":
        return {"event": topic_text, "causes": [], "effects": []}
    if dt == "bridge_map":
        return {"relating_factor": topic_text, "dimension": "", "analogies": []}
    if dt == "concept_map":
        return {
            "topic": topic_text,
            "concepts": [],
            "relationships": [],
            "focus_question": topic_text,
        }
    return {"topic": topic_text, "children": []}


def draft_title_for_diagram(
    diagram_type: str,
    *,
    topic: str = "",
    language: str = "zh",
) -> str:
    """User-facing library title for a newly created draft."""
    topic_text = (topic or "").strip()
    if topic_text:
        return topic_text[:200]
    lang = (language or "zh").strip().lower()
    dt = (diagram_type or "mindmap").strip().replace("-", "_")
    if lang.startswith("zh"):
        labels = {
            "mindmap": "新建思维导图",
            "mind_map": "新建思维导图",
            "circle_map": "新建圆圈图",
            "bubble_map": "新建气泡图",
            "double_bubble_map": "新建双气泡图",
            "tree_map": "新建树形图",
            "brace_map": "新建括号图",
            "flow_map": "新建流程图",
            "multi_flow_map": "新建复流程图",
            "bridge_map": "新建桥形图",
            "concept_map": "新建概念图",
        }
        return labels.get(dt, "新建导图")
    labels_en = {
        "mindmap": "New mind map",
        "mind_map": "New mind map",
        "circle_map": "New circle map",
        "bubble_map": "New bubble map",
        "double_bubble_map": "New double bubble map",
        "tree_map": "New tree map",
        "brace_map": "New brace map",
        "flow_map": "New flow map",
        "multi_flow_map": "New multi-flow map",
        "bridge_map": "New bridge map",
        "concept_map": "New concept map",
    }
    return labels_en.get(dt, "New diagram")


def normalize_library_diagram_type(diagram_type: str) -> str:
    """Normalize voice/FE slug to library ``diagram_type`` storage form."""
    dt = (diagram_type or "mindmap").strip().replace("-", "_")
    if dt == "mind_map":
        return "mindmap"
    return dt or "mindmap"
