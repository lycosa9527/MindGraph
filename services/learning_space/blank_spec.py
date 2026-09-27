"""Blank thinking-map specs for Learning Space student start (non-scaffold).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

TEMPLATE_ROLE_NONE = "none"
TEMPLATE_ROLE_REFERENCE = "reference"
TEMPLATE_ROLE_SCAFFOLD = "scaffold"
TEMPLATE_ROLES = frozenset({TEMPLATE_ROLE_NONE, TEMPLATE_ROLE_REFERENCE, TEMPLATE_ROLE_SCAFFOLD})

_MIND_MAP_THEME_ID = "rainbow"
_MIND_MAP_DIAGRAM_STYLE_ID = "classic"
_CONCEPT_MAP_FOCUS_QUESTION = "焦点问题：请输入"


def normalize_ls_diagram_type(diagram_type: str | None) -> str:
    """Normalize assignment diagram_type aliases."""
    raw = (diagram_type or "").strip()
    if not raw or raw == "mindmap":
        return "mind_map"
    return raw


def resolve_template_role(perms: dict[str, Any] | None) -> str:
    """Resolve how the teacher diagram is used when a student opens homework.

    Legacy rows without ``template_role`` keep clone-on-open (scaffold) unless
    ``has_teacher_template`` is explicitly false (auto blank at publish).
    """
    data = perms if isinstance(perms, dict) else {}
    role = data.get("template_role")
    if isinstance(role, str) and role.strip() in TEMPLATE_ROLES:
        return role.strip()
    start = data.get("start_mode")
    if start == "blank":
        if data.get("has_teacher_template") is True:
            return TEMPLATE_ROLE_REFERENCE
        return TEMPLATE_ROLE_NONE
    if start == "scaffold":
        return TEMPLATE_ROLE_SCAFFOLD
    if data.get("has_teacher_template") is False:
        return TEMPLATE_ROLE_NONE
    return TEMPLATE_ROLE_SCAFFOLD


def _range(count: int, template: str) -> list[str]:
    return [template.format(n=i + 1) for i in range(count)]


def _mind_map_branch(branch_index: int, *, child_count: int = 2) -> dict[str, Any]:
    branch_label = f"分支{branch_index}"
    return {
        "label": branch_label,
        "text": branch_label,
        "children": [
            {
                "label": f"子项{branch_index}.{child_index}",
                "text": f"子项{branch_index}.{child_index}",
                "children": [],
            }
            for child_index in range(1, child_count + 1)
        ],
    }


def _tree_map_children() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category_index in range(1, 5):
        rows.append(
            {
                "text": f"类别{category_index}",
                "children": [
                    {
                        "text": f"项目{category_index}.{item_index}",
                        "children": [],
                    }
                    for item_index in range(1, 4)
                ],
            }
        )
    return rows


def _brace_map_parts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for part_index in range(1, 4):
        rows.append(
            {
                "name": f"部分{part_index}",
                "subparts": [{"name": f"子部分{part_index}.{subpart_index}"} for subpart_index in range(1, 3)],
            }
        )
    return rows


def _flow_map_substeps() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for step_index in range(1, 5):
        rows.append(
            {
                "step": f"步骤{step_index}",
                "substeps": [f"子步骤{step_index}.{substep_index}" for substep_index in range(1, 3)],
            }
        )
    return rows


def _bridge_map_analogies() -> list[dict[str, str]]:
    return [{"left": f"事物A{index}", "right": f"事物B{index}"} for index in range(1, 6)]


def blank_spec_for_type(title: str, diagram_type: str) -> dict[str, Any]:
    """Default zh canvas spec matching the normal new-diagram template.

    The assignment title is intentionally ignored so students start from the same
    blank canvas as opening a new diagram from the gallery.
    """
    _ = title
    dtype = normalize_ls_diagram_type(diagram_type)
    if dtype == "circle_map":
        return {"topic": "主题", "context": _range(8, "联想{n}")}
    if dtype == "bubble_map":
        return {"topic": "主题", "attributes": _range(5, "属性{n}")}
    if dtype == "double_bubble_map":
        return {
            "left": "主题A",
            "right": "主题B",
            "similarities": _range(2, "相似点 {n}"),
            "left_differences": _range(3, "不同点A{n}"),
            "right_differences": _range(3, "不同点B{n}"),
        }
    if dtype == "tree_map":
        return {
            "topic": "根主题",
            "dimension": "",
            "alternative_dimensions": [],
            "children": _tree_map_children(),
        }
    if dtype == "brace_map":
        return {"whole": "主题", "dimension": "", "parts": _brace_map_parts()}
    if dtype == "flow_map":
        return {
            "title": "事件流程",
            "steps": _range(4, "步骤{n}"),
            "substeps": _flow_map_substeps(),
        }
    if dtype == "multi_flow_map":
        return {
            "event": "事件",
            "causes": _range(4, "原因{n}"),
            "effects": _range(4, "结果{n}"),
        }
    if dtype == "bridge_map":
        return {
            "relating_factor": "[点击设置]",
            "dimension": "",
            "analogies": _bridge_map_analogies(),
            "alternative_dimensions": [],
        }
    if dtype == "concept_map":
        return {
            "topic": _CONCEPT_MAP_FOCUS_QUESTION,
            "concepts": [],
            "relationships": [],
            "focus_question": _CONCEPT_MAP_FOCUS_QUESTION,
        }
    return {
        "_mindmap_theme": _MIND_MAP_THEME_ID,
        "_mindmap_diagram_style": _MIND_MAP_DIAGRAM_STYLE_ID,
        "topic": "中心主题",
        "children": [_mind_map_branch(index) for index in range(1, 5)],
    }
