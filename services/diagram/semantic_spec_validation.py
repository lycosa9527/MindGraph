"""
Structural validation for agent-authored semantic diagram specs.

Used by create/export/patch APIs so OpenClaw (and other clients) get clear
400 feedback. Canvas persist specs ({nodes, connections}) pass through.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from fastapi import HTTPException

from models.common import DiagramType

IssueList = List[str]
ValidateFn = Callable[[Dict[str, Any], IssueList], None]

_KNOWN_TYPES = frozenset(item.value for item in DiagramType)
_TYPE_ALIASES = {
    "mindmap": "mind_map",
}


def normalize_diagram_type_slug(diagram_type: str) -> str:
    """Normalize diagram_type aliases (e.g. mindmap → mind_map)."""
    raw = (diagram_type or "").strip()
    return _TYPE_ALIASES.get(raw, raw)


def is_canvas_persist_spec(spec: Dict[str, Any]) -> bool:
    """True when spec looks like editor persist shape ({nodes, connections})."""
    nodes = spec.get("nodes")
    return isinstance(nodes, list) and len(nodes) > 0


def invalid_diagram_spec_detail(diagram_type: str, issues: IssueList) -> Dict[str, Any]:
    """Stable HTTP 400 detail payload for invalid semantic specs."""
    return {
        "error": "invalid_diagram_spec",
        "diagram_type": diagram_type,
        "issues": list(issues),
    }


def ensure_valid_semantic_spec(diagram_type: str, spec: Any) -> str:
    """
    Validate spec or raise FastAPI HTTPException(400) with structured detail.

    Returns normalized diagram_type when valid.
    """
    ok, issues, normalized_type = validate_semantic_spec(diagram_type, spec)
    if ok:
        return normalized_type
    raise HTTPException(
        status_code=400,
        detail=invalid_diagram_spec_detail(normalized_type or str(diagram_type), issues),
    )


def validate_semantic_spec(
    diagram_type: str,
    spec: Any,
) -> Tuple[bool, IssueList, str]:
    """
    Validate a semantic (or canvas) diagram spec.

    Returns:
        (ok, issues, normalized_diagram_type)
    """
    normalized_type = normalize_diagram_type_slug(str(diagram_type or ""))
    if not normalized_type:
        return False, ["Missing diagram_type"], ""

    if not isinstance(spec, dict):
        return False, ["Spec must be a JSON object"], normalized_type

    if is_canvas_persist_spec(spec):
        return True, [], normalized_type

    if normalized_type not in _KNOWN_TYPES:
        return (
            False,
            [f"Unknown diagram_type '{diagram_type}'"],
            normalized_type,
        )

    issues: IssueList = []
    validator = _VALIDATORS.get(normalized_type)
    if validator is None:
        issues.append(f"No validator for diagram_type '{normalized_type}'")
        return False, issues, normalized_type

    validator(spec, issues)
    return (not issues), issues, normalized_type


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _require_non_empty_string(
    spec: Dict[str, Any],
    field: str,
    issues: IssueList,
    *,
    diagram_type: str,
    aliases: Optional[Tuple[str, ...]] = None,
) -> Optional[str]:
    keys = (field,) + (aliases or ())
    for key in keys:
        if key in spec:
            value = spec[key]
            if _non_empty_str(value):
                return str(value).strip()
            issues.append(f"Field '{key}' must be a non-empty string for {diagram_type}")
            return None
    alias_hint = ""
    if aliases:
        alias_hint = f" (or {' / '.join(aliases)})"
    issues.append(f"Missing required field '{field}'{alias_hint} for {diagram_type}")
    return None


def _require_string_list(
    spec: Dict[str, Any],
    field: str,
    issues: IssueList,
    *,
    diagram_type: str,
    allow_empty: bool = False,
    aliases: Optional[Tuple[str, ...]] = None,
) -> None:
    keys = (field,) + (aliases or ())
    present_key: Optional[str] = None
    value: Any = None
    for key in keys:
        if key in spec:
            present_key = key
            value = spec[key]
            break
    if present_key is None:
        alias_hint = ""
        if aliases:
            alias_hint = f" (or {' / '.join(aliases)})"
        issues.append(f"Missing required field '{field}'{alias_hint} for {diagram_type}")
        return
    if not isinstance(value, list):
        issues.append(f"Field '{present_key}' must be an array of strings for {diagram_type}")
        return
    if not allow_empty and len(value) == 0:
        issues.append(f"Field '{present_key}' must be a non-empty array for {diagram_type}")
        return
    for idx, item in enumerate(value):
        if not _non_empty_str(item):
            issues.append(f"Field '{present_key}[{idx}]' must be a non-empty string for {diagram_type}")


def _node_label(node: Dict[str, Any]) -> str:
    for key in ("text", "label", "name"):
        value = node.get(key)
        if _non_empty_str(value):
            return str(value).strip()
    return ""


def _validate_children_tree(
    children: Any,
    issues: IssueList,
    *,
    path: str,
    diagram_type: str,
    require_non_empty: bool,
) -> None:
    if not isinstance(children, list):
        issues.append(f"Field '{path}' must be an array for {diagram_type}")
        return
    if require_non_empty and len(children) == 0:
        issues.append(f"Field '{path}' must be a non-empty array for {diagram_type}")
        return
    for idx, child in enumerate(children):
        child_path = f"{path}[{idx}]"
        if not isinstance(child, dict):
            issues.append(f"{child_path} must be an object with text or label for {diagram_type}")
            continue
        if not _node_label(child):
            issues.append(f"{child_path} must be an object with text or label for {diagram_type}")
        nested = child.get("children")
        if nested is not None:
            _validate_children_tree(
                nested,
                issues,
                path=f"{child_path}.children",
                diagram_type=diagram_type,
                require_non_empty=False,
            )


def _validate_bubble_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "bubble_map"
    _require_non_empty_string(spec, "topic", issues, diagram_type=dtype)
    _require_string_list(spec, "attributes", issues, diagram_type=dtype)


def _validate_circle_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "circle_map"
    _require_non_empty_string(spec, "topic", issues, diagram_type=dtype)
    _require_string_list(
        spec,
        "context",
        issues,
        diagram_type=dtype,
        aliases=("contexts",),
    )


def _validate_double_bubble_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "double_bubble_map"
    _require_non_empty_string(
        spec,
        "left",
        issues,
        diagram_type=dtype,
        aliases=("left_topic",),
    )
    _require_non_empty_string(
        spec,
        "right",
        issues,
        diagram_type=dtype,
        aliases=("right_topic",),
    )
    _require_string_list(spec, "similarities", issues, diagram_type=dtype)
    _require_string_list(
        spec,
        "left_differences",
        issues,
        diagram_type=dtype,
        aliases=("leftDifferences",),
    )
    _require_string_list(
        spec,
        "right_differences",
        issues,
        diagram_type=dtype,
        aliases=("rightDifferences",),
    )


def _validate_tree_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "tree_map"
    _require_non_empty_string(spec, "topic", issues, diagram_type=dtype)
    children = spec.get("children")
    if children is None and "categories" in spec:
        children = spec.get("categories")
        path = "categories"
    else:
        path = "children"
        if children is None:
            issues.append(f"Missing required field 'children' for {dtype}")
            return
    _validate_children_tree(
        children,
        issues,
        path=path,
        diagram_type=dtype,
        require_non_empty=True,
    )


def _validate_brace_parts(
    parts: Any,
    issues: IssueList,
    *,
    path: str,
) -> None:
    dtype = "brace_map"
    if not isinstance(parts, list):
        issues.append(f"Field '{path}' must be an array for {dtype}")
        return
    if len(parts) == 0:
        issues.append(f"Field '{path}' must be a non-empty array for {dtype}")
        return
    for idx, part in enumerate(parts):
        part_path = f"{path}[{idx}]"
        if not isinstance(part, dict):
            issues.append(f"{part_path} must be an object with name for {dtype}")
            continue
        if not _non_empty_str(part.get("name")):
            issues.append(f"{part_path} must include non-empty string 'name' for {dtype}")
        subparts = part.get("subparts")
        if subparts is None:
            continue
        if not isinstance(subparts, list):
            issues.append(f"{part_path}.subparts must be an array for {dtype}")
            continue
        for sidx, sub in enumerate(subparts):
            sub_path = f"{part_path}.subparts[{sidx}]"
            if isinstance(sub, str):
                if not sub.strip():
                    issues.append(f"{sub_path} must be a non-empty string for {dtype}")
                continue
            if not isinstance(sub, dict) or not _non_empty_str(sub.get("name")):
                issues.append(f"{sub_path} must be an object with name for {dtype}")


def _validate_brace_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "brace_map"
    _require_non_empty_string(
        spec,
        "whole",
        issues,
        diagram_type=dtype,
        aliases=("topic",),
    )
    if "parts" not in spec:
        issues.append(f"Missing required field 'parts' for {dtype}")
        return
    _validate_brace_parts(spec.get("parts"), issues, path="parts")


def _validate_flow_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "flow_map"
    _require_non_empty_string(
        spec,
        "title",
        issues,
        diagram_type=dtype,
        aliases=("topic",),
    )
    _require_string_list(spec, "steps", issues, diagram_type=dtype)
    substeps = spec.get("substeps")
    if substeps is None:
        return
    if not isinstance(substeps, list):
        issues.append(f"Field 'substeps' must be an array for {dtype}")
        return
    for idx, item in enumerate(substeps):
        path = f"substeps[{idx}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object for {dtype}")
            continue
        if not _non_empty_str(item.get("step")):
            issues.append(f"{path}.step must be a non-empty string for {dtype}")
        nested = item.get("substeps")
        if nested is None:
            continue
        if not isinstance(nested, list):
            issues.append(f"{path}.substeps must be an array for {dtype}")
            continue
        for nidx, nested_item in enumerate(nested):
            if not _non_empty_str(nested_item):
                issues.append(f"{path}.substeps[{nidx}] must be a non-empty string for {dtype}")


def _validate_multi_flow_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "multi_flow_map"
    _require_non_empty_string(
        spec,
        "event",
        issues,
        diagram_type=dtype,
        aliases=("topic",),
    )
    _require_string_list(spec, "causes", issues, diagram_type=dtype)
    _require_string_list(spec, "effects", issues, diagram_type=dtype)


def _validate_bridge_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "bridge_map"
    _require_non_empty_string(spec, "relating_factor", issues, diagram_type=dtype)
    analogies = spec.get("analogies")
    if analogies is None:
        issues.append(f"Missing required field 'analogies' for {dtype}")
        return
    if not isinstance(analogies, list):
        issues.append(f"Field 'analogies' must be an array for {dtype}")
        return
    if len(analogies) == 0:
        issues.append(f"Field 'analogies' must be a non-empty array for {dtype}")
        return
    for idx, item in enumerate(analogies):
        path = f"analogies[{idx}]"
        if not isinstance(item, dict):
            issues.append(f"{path} must be an object with left and right for {dtype}")
            continue
        if not _non_empty_str(item.get("left")):
            issues.append(f"{path}.left must be a non-empty string for {dtype}")
        if not _non_empty_str(item.get("right")):
            issues.append(f"{path}.right must be a non-empty string for {dtype}")


def _validate_mind_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "mind_map"
    _require_non_empty_string(spec, "topic", issues, diagram_type=dtype)
    if "children" not in spec:
        issues.append(f"Missing required field 'children' for {dtype}")
        return
    _validate_children_tree(
        spec.get("children"),
        issues,
        path="children",
        diagram_type=dtype,
        require_non_empty=True,
    )


def _validate_concept_map(spec: Dict[str, Any], issues: IssueList) -> None:
    dtype = "concept_map"
    topic = spec.get("topic")
    focus = spec.get("focus_question")
    if not _non_empty_str(topic) and not _non_empty_str(focus):
        issues.append(f"Missing required field 'topic' (or 'focus_question') for {dtype}")

    concepts = spec.get("concepts")
    units = spec.get("concept_units")
    if concepts is None and units is None:
        issues.append(f"Missing required field 'concepts' for {dtype}")
    elif concepts is not None:
        if not isinstance(concepts, list):
            issues.append(f"Field 'concepts' must be an array of strings for {dtype}")
        else:
            for idx, item in enumerate(concepts):
                if not _non_empty_str(item):
                    issues.append(f"Field 'concepts[{idx}]' must be a non-empty string for {dtype}")
    elif not isinstance(units, list):
        issues.append(f"Field 'concept_units' must be an array for {dtype}")
    else:
        for idx, unit in enumerate(units):
            path = f"concept_units[{idx}]"
            label = ""
            if isinstance(unit, dict):
                label = unit.get("label") or unit.get("text") or ""
            if not isinstance(unit, dict) or not _non_empty_str(label):
                issues.append(f"{path} must be an object with label for {dtype}")

    relationships = spec.get("relationships")
    if relationships is None:
        issues.append(f"Missing required field 'relationships' for {dtype}")
        return
    if not isinstance(relationships, list):
        issues.append(f"Field 'relationships' must be an array for {dtype}")
        return
    for idx, rel in enumerate(relationships):
        path = f"relationships[{idx}]"
        if not isinstance(rel, dict):
            issues.append(f"{path} must be an object with from and to for {dtype}")
            continue
        if not _non_empty_str(rel.get("from")):
            issues.append(f"{path}.from must be a non-empty string for {dtype}")
        if not _non_empty_str(rel.get("to")):
            issues.append(f"{path}.to must be a non-empty string for {dtype}")


_VALIDATORS: Dict[str, ValidateFn] = {
    "bubble_map": _validate_bubble_map,
    "circle_map": _validate_circle_map,
    "double_bubble_map": _validate_double_bubble_map,
    "tree_map": _validate_tree_map,
    "brace_map": _validate_brace_map,
    "flow_map": _validate_flow_map,
    "multi_flow_map": _validate_multi_flow_map,
    "bridge_map": _validate_bridge_map,
    "mind_map": _validate_mind_map,
    "concept_map": _validate_concept_map,
}
