"""
Lock central topic fields on autocomplete specs.

Auto-complete must never rewrite the canvas topic/title. Agents still receive the
topic in the prompt for content generation; after parse we overwrite the central
label field(s) with the client-supplied locked topic.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Optional


def apply_locked_topic_to_spec(
    spec: dict[str, Any],
    locked_topic: str,
    diagram_type: str,
) -> dict[str, Any]:
    """Overwrite central topic-like fields on a generated spec.

    Args:
        spec: Parsed diagram specification (mutated in place and returned).
        locked_topic: Exact canvas topic text to preserve.
        diagram_type: Diagram type string (mind_map / mindmap / tree_map / ...).

    Returns:
        The same spec dict with topic fields locked when applicable.
    """
    topic = locked_topic.strip()
    if not topic or not isinstance(spec, dict):
        return spec

    normalized = diagram_type.strip().lower().replace("-", "_")
    if normalized == "mindmap":
        normalized = "mind_map"

    if normalized in ("mind_map", "bubble_map", "circle_map", "tree_map"):
        _write_locked_field(spec, "topic", topic)
        return spec

    if normalized == "brace_map":
        _write_locked_field(spec, "whole", topic)
        if "topic" in spec:
            _write_locked_field(spec, "topic", topic)
        return spec

    if normalized == "flow_map":
        _write_locked_field(spec, "title", topic)
        return spec

    if normalized == "multi_flow_map":
        _write_locked_field(spec, "event", topic)
        return spec

    return spec


def _write_locked_field(spec: dict[str, Any], field: str, topic: str) -> None:
    """Replace one central label. Drop its gloss when the text actually changes.

    Peel already checked the mirror against the model's topic. Keeping that
    gloss after the canvas text replaces the topic shows a translation of a
    sentence the canvas no longer contains.
    """
    previous = spec.get(field)
    spec[field] = topic
    secondary = spec.get("secondary")
    if isinstance(secondary, dict) and previous != topic:
        secondary.pop(field, None)


def resolve_locked_topic(
    locked_topic: Optional[str],
    *,
    request_type: str,
    user_prompt: str,
) -> str:
    """Return topic to lock for autocomplete, or empty string when not applicable."""
    if (request_type or "").strip() != "autocomplete":
        return ""

    explicit = (locked_topic or "").strip()
    if explicit:
        return explicit

    # Fallback: first non-empty line of the user prompt (before generation instructions).
    for line in (user_prompt or "").splitlines():
        text = line.strip()
        if text:
            return text
    return ""
