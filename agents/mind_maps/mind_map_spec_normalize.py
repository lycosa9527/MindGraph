"""
Give mind-map nodes a text field before hierarchy validation.

Document generation validates the raw model JSON. A child that is a bare
string, or an object keyed by name/title/content, has no text/label, so the
whole map fails even though the label is present. String children are already
wrapped by the shared diagram coerce; this only copies a blank text from those
aliases and does not move or drop nodes.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Any, Dict

from agents.core.prompt_to_diagram_result import coerce_prompt_to_diagram_spec

_ALIAS_KEYS = ("label", "name", "title", "content")


def _promote_alias_text(node: Dict[str, Any]) -> None:
    """Fill a blank text from a known alias. Leave a real text value alone."""
    current = node.get("text")
    if not isinstance(current, str) or not current.strip():
        for key in _ALIAS_KEYS:
            raw = node.get(key)
            if isinstance(raw, str) and raw.strip():
                node["text"] = raw.strip()
                break
    children = node.get("children")
    if not isinstance(children, list):
        return
    for child in children:
        if isinstance(child, dict):
            _promote_alias_text(child)


def canonicalize_mind_map_spec(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy whose child nodes use text when the model used another label field."""
    if not isinstance(spec, dict):
        return spec
    coerced = coerce_prompt_to_diagram_spec(spec, "mind_map")
    children = coerced.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                _promote_alias_text(child)
    return coerced
