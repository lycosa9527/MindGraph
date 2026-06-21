"""
Normalize LLM output for prompt-to-diagram endpoints.

Expected shape: {"diagram_type": "...", "spec": {...}}
Some models return a bare spec dict without the wrapper.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

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
