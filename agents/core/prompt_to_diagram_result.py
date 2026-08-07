"""
Normalize LLM output for prompt-to-diagram endpoints.

Expected shape: {"diagram_type": "...", "spec": {...}}
Some models return a bare spec dict without the wrapper.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_SPEC_SIGNATURES: tuple[tuple[str, frozenset[str]], ...] = (
    ("double_bubble_map", frozenset({"left", "right"})),
    ("bridge_map", frozenset({"analogies"})),
    ("flow_map", frozenset({"steps"})),
    ("multi_flow_map", frozenset({"event"})),
    ("brace_map", frozenset({"whole"})),
    ("circle_map", frozenset({"context"})),
    ("concept_map", frozenset({"concepts"})),
    ("mind_map", frozenset({"topic", "children"})),
    ("tree_map", frozenset({"topic", "children"})),
    ("bubble_map", frozenset({"topic"})),
)

_LLM_ERROR_KEYS = frozenset({"error", "message", "detail", "_error"})


def _infer_diagram_type(spec: Dict[str, Any]) -> Optional[str]:
    keys = frozenset(spec.keys())
    for diagram_type, required in _SPEC_SIGNATURES:
        if required <= keys:
            if diagram_type == "tree_map" and "analogies" in keys:
                continue
            if diagram_type in ("mind_map", "tree_map") and "steps" in keys:
                continue
            return diagram_type
    if "title" in keys and "steps" in keys:
        return "flow_map"
    return None


def normalize_prompt_to_diagram_result(result: Any) -> Optional[Dict[str, Any]]:
    """
    Normalize prompt-to-diagram LLM JSON into {diagram_type, spec}.

    Returns None when result is not a dict or cannot be normalized.
    """
    if not isinstance(result, dict):
        return None

    if result.get("_error") == "non_json_response":
        return result

    if "spec" in result:
        normalized = dict(result)
        if not normalized.get("diagram_type"):
            spec = normalized.get("spec")
            if isinstance(spec, dict):
                inferred = _infer_diagram_type(spec)
                if inferred:
                    normalized["diagram_type"] = inferred
                else:
                    normalized["diagram_type"] = "bubble_map"
        return normalized

    if _LLM_ERROR_KEYS & frozenset(result.keys()) and len(result) <= 3:
        return None

    inferred = _infer_diagram_type(result)
    if inferred:
        return {"diagram_type": inferred, "spec": result}

    return None


def is_llm_clarification_dict(result: Dict[str, Any]) -> bool:
    """True when dict looks like an LLM error/clarification, not a diagram spec."""
    if result.get("_error") == "non_json_response":
        return True
    keys = frozenset(result.keys())
    if keys <= _LLM_ERROR_KEYS and bool(keys):
        return True
    if "error" in result and "spec" not in result:
        return True
    return False


_SCALAR_LABEL_KEYS = frozenset(
    {
        "topic",
        "left",
        "right",
        "whole",
        "event",
        "dimension",
        "title",
        "focus_question",
        "text",
        "label",
        "name",
    }
)

_STRING_LIST_KEYS = frozenset(
    {
        "attributes",
        "context",
        "concepts",
        "similarities",
        "left_differences",
        "right_differences",
        "leftDifferences",
        "rightDifferences",
        "causes",
        "effects",
        "steps",
        "substeps",
    }
)


def _coerce_label_value(value: Any) -> str:
    """Coerce a diagram label field to str (null/None → empty)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        nested = value.get("text", value.get("label", value.get("name")))
        if nested is not None and not isinstance(nested, (dict, list)):
            return _coerce_label_value(nested)
        return str(value)
    if isinstance(value, list):
        return " ".join(_coerce_label_value(item) for item in value if item is not None)
    return str(value)


def _coerce_string_list(value: Any) -> List[Any]:
    """Coerce list items that are labels; keep dict steps/children for nested pass."""
    if not isinstance(value, list):
        if value is None:
            return []
        return [_coerce_label_value(value)]
    coerced: List[Any] = []
    for item in value:
        if isinstance(item, dict):
            coerced.append(coerce_prompt_to_diagram_spec(item, ""))
        else:
            coerced.append(_coerce_label_value(item))
    return coerced


def _coerce_children(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return []
    children: List[Any] = []
    for item in value:
        if isinstance(item, dict):
            children.append(coerce_prompt_to_diagram_spec(item, ""))
        else:
            children.append({"text": _coerce_label_value(item)})
    return children


def _coerce_analogies(value: Any) -> List[Any]:
    if not isinstance(value, list):
        return []
    analogies: List[Any] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        for key in ("left", "right", "a", "b"):
            if key in row:
                row[key] = _coerce_label_value(row.get(key))
        analogies.append(row)
    return analogies


def coerce_prompt_to_diagram_spec(spec: Any, diagram_type: str = "") -> Dict[str, Any]:
    """Coerce LLM label fields to strings so Vue Flow ``.trim`` never sees numbers/objects.

    Safe to call on nested children dicts (``diagram_type`` may be empty).
    """
    _ = diagram_type
    if not isinstance(spec, dict):
        return {}
    out = dict(spec)
    for key in list(out.keys()):
        if key in _SCALAR_LABEL_KEYS:
            out[key] = _coerce_label_value(out.get(key))
        elif key in _STRING_LIST_KEYS:
            out[key] = _coerce_string_list(out.get(key))
        elif key == "children":
            out[key] = _coerce_children(out.get(key))
        elif key == "analogies":
            out[key] = _coerce_analogies(out.get(key))
        elif key == "relationships" and isinstance(out.get(key), list):
            rels: List[Any] = []
            for rel in out[key]:
                if not isinstance(rel, dict):
                    continue
                row = dict(rel)
                for rel_key in ("from", "to", "label", "text"):
                    if rel_key in row:
                        row[rel_key] = _coerce_label_value(row.get(rel_key))
                rels.append(row)
            out[key] = rels
    return out
