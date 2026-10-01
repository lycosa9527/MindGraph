"""Blank thinking-map specs for Learning Space student start (non-scaffold).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any

_SLOT = "…"

TEMPLATE_ROLE_NONE = "none"
TEMPLATE_ROLE_REFERENCE = "reference"
TEMPLATE_ROLE_SCAFFOLD = "scaffold"
TEMPLATE_ROLES = frozenset({TEMPLATE_ROLE_NONE, TEMPLATE_ROLE_REFERENCE, TEMPLATE_ROLE_SCAFFOLD})


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


def blank_spec_for_type(title: str, diagram_type: str) -> dict[str, Any]:
    """Minimal valid semantic spec so students start from an empty canvas."""
    topic = (title or "").strip() or "作业"
    dtype = normalize_ls_diagram_type(diagram_type)
    slot = _SLOT
    if dtype == "circle_map":
        return {"topic": topic, "context": [slot]}
    if dtype == "bubble_map":
        return {"topic": topic, "attributes": [slot]}
    if dtype == "double_bubble_map":
        return {
            "left": topic,
            "right": slot,
            "similarities": [slot],
            "left_differences": [slot],
            "right_differences": [slot],
        }
    if dtype == "tree_map":
        return {"topic": topic, "children": [{"text": slot, "children": []}]}
    if dtype == "brace_map":
        return {"whole": topic, "parts": [{"name": slot}]}
    if dtype == "flow_map":
        return {"title": topic, "steps": [slot]}
    if dtype == "multi_flow_map":
        return {"event": topic, "causes": [slot], "effects": [slot]}
    if dtype == "bridge_map":
        return {"relating_factor": topic, "analogies": [{"left": slot, "right": slot}]}
    if dtype == "concept_map":
        return {
            "topic": topic,
            "concepts": [slot],
            "relationships": [{"from": topic, "to": slot}],
        }
    return {"topic": topic, "children": [{"text": slot, "children": []}]}
