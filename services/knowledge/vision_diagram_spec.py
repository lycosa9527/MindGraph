"""Sanitize a vision diagram JSON spec into a canvas loader shape.

Generation validators demand minimum node counts. A photo may have fewer
nodes, so this only drops empty text.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

_TEXT_LIMIT = 200
_DEPTH_LIMIT = 6

_TYPE_ALIASES = {
    "mind_map": "mindmap",
    "circle": "circle_map",
    "bubble": "bubble_map",
    "double_bubble": "double_bubble_map",
    "tree": "tree_map",
    "brace": "brace_map",
    "flow": "flow_map",
    "multi_flow": "multi_flow_map",
    "multiflow": "multi_flow_map",
    "bridge": "bridge_map",
    "concept": "concept_map",
}

DIAGRAM_IMPORT_TYPES = frozenset(
    {
        "circle_map",
        "bubble_map",
        "double_bubble_map",
        "tree_map",
        "brace_map",
        "flow_map",
        "multi_flow_map",
        "bridge_map",
        "mindmap",
        "concept_map",
    }
)


def normalize_diagram_type(raw: Any) -> str:
    """Map a model type string onto a canvas diagram type, or return empty."""
    text = str(raw or "").strip().lower().replace("-", "_").replace(" ", "_")
    if not text or text in {"null", "none"}:
        return ""
    text = _TYPE_ALIASES.get(text, text)
    if text in DIAGRAM_IMPORT_TYPES:
        return text
    return ""


def _clip(raw: Any) -> str:
    """Trim one label."""
    return str(raw or "").strip()[:_TEXT_LIMIT]


def _string_list(raw: Any) -> List[str]:
    """Keep non-empty labels from a list of strings or ``{text|name|label}``."""
    if not isinstance(raw, list):
        return []
    cleaned: List[str] = []
    for item in raw:
        if isinstance(item, str):
            text = _clip(item)
        elif isinstance(item, dict):
            text = _clip(item.get("text") or item.get("name") or item.get("label"))
        else:
            text = ""
        if text:
            cleaned.append(text)
    return cleaned


def _nested_children(nodes: Any, *, depth: int = 0) -> List[Dict[str, Any]]:
    """Mind-map / tree children: text plus optional nested children."""
    if not isinstance(nodes, list) or depth > _DEPTH_LIMIT:
        return []
    cleaned: List[Dict[str, Any]] = []
    for node in nodes:
        if isinstance(node, str):
            text = _clip(node)
            nested: List[Dict[str, Any]] = []
        elif isinstance(node, dict):
            text = _clip(node.get("text") or node.get("name") or node.get("label"))
            nested = _nested_children(node.get("children"), depth=depth + 1)
        else:
            continue
        if not text:
            continue
        entry: Dict[str, Any] = {"text": text}
        if nested:
            entry["children"] = nested
        cleaned.append(entry)
    return cleaned


def _require_topic_and_list(spec: Dict[str, Any], list_key: str) -> Optional[Dict[str, Any]]:
    """``topic`` plus one non-empty string list."""
    topic = _clip(spec.get("topic"))
    items = _string_list(spec.get(list_key))
    if not topic or not items:
        return None
    return {"topic": topic, list_key: items}


def _sanitize_circle(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Circle map: topic and context lines."""
    return _require_topic_and_list(spec, "context")


def _sanitize_bubble(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bubble map: topic and attributes."""
    return _require_topic_and_list(spec, "attributes")


def _sanitize_double_bubble(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Double bubble: two topics plus shared and side-specific lines."""
    left = _clip(spec.get("left"))
    right = _clip(spec.get("right"))
    similarities = _string_list(spec.get("similarities"))
    left_differences = _string_list(spec.get("left_differences") or spec.get("leftDifferences"))
    right_differences = _string_list(spec.get("right_differences") or spec.get("rightDifferences"))
    if not left or not right:
        return None
    if not similarities and not left_differences and not right_differences:
        return None
    return {
        "left": left,
        "right": right,
        "similarities": similarities,
        "left_differences": left_differences,
        "right_differences": right_differences,
    }


def _sanitize_tree(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Tree map: topic and category children."""
    topic = _clip(spec.get("topic"))
    children = _nested_children(spec.get("children"))
    if not topic or not children:
        return None
    return {"topic": topic, "children": children}


def _sanitize_mindmap(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Mind map: topic and nested branches."""
    return _sanitize_tree(spec)


def _brace_subparts(raw: Any) -> List[Dict[str, str]]:
    """One level of brace subparts."""
    names = _string_list(raw)
    return [{"name": name} for name in names]


def _sanitize_brace(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Brace map: whole plus parts. Subparts stay one level deep."""
    whole_raw = spec.get("whole")
    if isinstance(whole_raw, dict):
        whole = _clip(whole_raw.get("text") or whole_raw.get("name"))
    else:
        whole = _clip(whole_raw or spec.get("topic"))
    parts_out: List[Dict[str, Any]] = []
    raw_parts = spec.get("parts")
    if isinstance(raw_parts, list):
        for part in raw_parts:
            if isinstance(part, str):
                name = _clip(part)
                subparts: List[Dict[str, str]] = []
            elif isinstance(part, dict):
                name = _clip(part.get("name") or part.get("text"))
                subparts = _brace_subparts(part.get("subparts") or part.get("parts") or part.get("children"))
            else:
                continue
            if not name:
                continue
            entry: Dict[str, Any] = {"name": name}
            if subparts:
                entry["subparts"] = subparts
            parts_out.append(entry)
    if not whole or not parts_out:
        return None
    return {"whole": whole, "parts": parts_out}


def _flow_step_text(step: Any) -> tuple[str, List[str]]:
    """One flow step label and its substeps."""
    if isinstance(step, str):
        return _clip(step), []
    if not isinstance(step, dict):
        return "", []
    text = _clip(step.get("text") or step.get("name") or step.get("title"))
    substeps = _string_list(step.get("substeps") or step.get("children"))
    return text, substeps


def _sanitize_flow(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Flow map: title, step labels, and substeps keyed by step index."""
    title = _clip(spec.get("title") or spec.get("topic"))
    raw_steps = spec.get("steps")
    steps: List[str] = []
    substeps: List[Dict[str, Any]] = []
    if isinstance(raw_steps, list):
        for step in raw_steps:
            text, children = _flow_step_text(step)
            if not text:
                continue
            steps.append(text)
            substeps.append(
                {
                    "step": text,
                    "stepIndex": len(steps) - 1,
                    "substeps": children,
                }
            )
    if not title or not steps:
        return None
    return {"title": title, "steps": steps, "substeps": substeps}


def _sanitize_multi_flow(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Multi-flow map: event, causes, and effects."""
    event = _clip(spec.get("event") or spec.get("topic"))
    causes = _string_list(spec.get("causes"))
    effects = _string_list(spec.get("effects"))
    if not event or (not causes and not effects):
        return None
    return {"event": event, "causes": causes, "effects": effects}


def _sanitize_bridge(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Bridge map: relating factor and left/right pairs."""
    relating = _clip(spec.get("relating_factor") or spec.get("dimension"))
    raw_pairs = spec.get("analogies") or spec.get("pairs")
    analogies: List[Dict[str, str]] = []
    if isinstance(raw_pairs, list):
        for pair in raw_pairs:
            if not isinstance(pair, dict):
                continue
            left = _clip(pair.get("left"))
            right = _clip(pair.get("right"))
            if left and right:
                analogies.append({"left": left, "right": right})
    if not analogies:
        return None
    return {"relating_factor": relating, "analogies": analogies}


def _sanitize_concept(spec: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Concept map: topic, concept labels, and labeled edges."""
    topic = _clip(spec.get("topic"))
    concepts = _string_list(spec.get("concepts"))
    relationships: List[Dict[str, str]] = []
    raw_rels = spec.get("relationships")
    if isinstance(raw_rels, list):
        for rel in raw_rels:
            if not isinstance(rel, dict):
                continue
            source = _clip(rel.get("from"))
            target = _clip(rel.get("to"))
            if not source or not target:
                continue
            relationships.append(
                {
                    "from": source,
                    "to": target,
                    "label": _clip(rel.get("label"))[:80],
                }
            )
    if not topic or not concepts or not relationships:
        return None
    return {"topic": topic, "concepts": concepts, "relationships": relationships}


_SANITIZERS: Dict[str, Callable[[Dict[str, Any]], Optional[Dict[str, Any]]]] = {
    "circle_map": _sanitize_circle,
    "bubble_map": _sanitize_bubble,
    "double_bubble_map": _sanitize_double_bubble,
    "tree_map": _sanitize_tree,
    "brace_map": _sanitize_brace,
    "flow_map": _sanitize_flow,
    "multi_flow_map": _sanitize_multi_flow,
    "bridge_map": _sanitize_bridge,
    "mindmap": _sanitize_mindmap,
    "concept_map": _sanitize_concept,
}


def sanitize_diagram_spec(diagram_type: str, raw_spec: Any) -> Optional[Dict[str, Any]]:
    """Return a loader-ready spec, or None when the type or text is unusable."""
    if not isinstance(raw_spec, dict):
        return None
    sanitizer = _SANITIZERS.get(diagram_type)
    if sanitizer is None:
        return None
    return sanitizer(raw_spec)


def topic_from_diagram_spec(diagram_type: str, spec: Dict[str, Any]) -> str:
    """Short title for the review dialog and activity log."""
    if diagram_type == "double_bubble_map":
        left = _clip(spec.get("left"))
        right = _clip(spec.get("right"))
        if left and right:
            return f"{left} / {right}"[:_TEXT_LIMIT]
        return left or right
    if diagram_type == "bridge_map":
        relating = _clip(spec.get("relating_factor"))
        if relating:
            return relating
        analogies = spec.get("analogies")
        if isinstance(analogies, list) and analogies and isinstance(analogies[0], dict):
            return _clip(analogies[0].get("left"))
        return ""
    for key in ("topic", "title", "event", "whole"):
        text = _clip(spec.get(key))
        if text:
            return text
    return ""
