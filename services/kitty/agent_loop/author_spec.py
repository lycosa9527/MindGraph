"""author_spec tool — cookbook mind-map spec → library save.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from services.diagram.generation_library_save import (
    SAVE_LIMIT_REACHED,
    try_save_diagram_to_library,
)
from services.diagram.semantic_spec_validation import validate_semantic_spec
from services.kitty.agent_loop.results import ui_result_content
from services.kitty.session.runtime_state import voice_sessions


def author_spec_tool_schema() -> Dict[str, Any]:
    """Create a new mind map from a topic and branch labels."""
    return {
        "type": "function",
        "function": {
            "name": "author_spec",
            "description": (
                "Create a new mind map in the user's library from a topic and "
                "named branches. Use when the user asks to 新建 / create a map "
                "and already named the topic. Do not use for edits on the "
                "current canvas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Library title (defaults to topic).",
                    },
                    "topic": {
                        "type": "string",
                        "description": "Center topic of the mind map.",
                    },
                    "branches": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Top-level branch labels (at least one).",
                    },
                },
                "required": ["topic"],
            },
        },
    }


def build_mindmap_spec(topic: str, branches: List[str], *, lang: str) -> Dict[str, Any]:
    """Minimal cookbook mind-map spec that passes semantic validation."""
    labels = [item.strip() for item in branches if isinstance(item, str) and item.strip()]
    if not labels:
        labels = ["概述"] if lang != "en" else ["Overview"]
    children: List[Dict[str, Any]] = []
    for label in labels[:12]:
        children.append({"label": label, "text": label, "children": []})
    return {
        "topic": topic.strip(),
        "children": children,
        "_mindmap_theme": "rainbow",
        "_mindmap_diagram_style": "classic",
    }


def _parse_arguments(arguments_json: str) -> Dict[str, Any]:
    try:
        payload = json.loads(arguments_json or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _session_user_id(voice_session_id: str) -> Optional[int]:
    session = voice_sessions.get(voice_session_id) or {}
    raw = session.get("user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _session_org_id(voice_session_id: str) -> Optional[int]:
    session = voice_sessions.get(voice_session_id) or {}
    raw = session.get("organization_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def dispatch_author_spec(
    voice_session_id: str,
    *,
    arguments_json: str,
    lang: str,
) -> Dict[str, Any]:
    """Validate a mind-map spec and save it to the library."""
    args = _parse_arguments(arguments_json)
    topic_raw = args.get("topic")
    topic = topic_raw.strip() if isinstance(topic_raw, str) else ""
    if not topic:
        return ui_result_content(
            status="rejected",
            action="author_spec",
            extra={"error_code": "missing_topic"},
        )
    title_raw = args.get("title")
    title = title_raw.strip() if isinstance(title_raw, str) and title_raw.strip() else topic
    branches_raw = args.get("branches")
    branches = [item for item in branches_raw if isinstance(item, str)] if isinstance(branches_raw, list) else []
    spec = build_mindmap_spec(topic, branches, lang=lang)
    ok, issues, _normalized = validate_semantic_spec("mind_map", spec)
    if not ok:
        return ui_result_content(
            status="failed",
            action="author_spec",
            extra={"error_code": "invalid_diagram_spec", "issues": issues},
        )
    user_id = _session_user_id(voice_session_id)
    saved = await try_save_diagram_to_library(
        user_id,
        title=title,
        diagram_type="mind_map",
        spec=spec,
        language="en" if lang == "en" else "zh",
        organization_id=_session_org_id(voice_session_id),
        log_prefix="kitty_author_spec",
    )
    if saved == SAVE_LIMIT_REACHED:
        return ui_result_content(
            status="failed",
            action="author_spec",
            extra={"error_code": "library_full"},
        )
    if not saved:
        return ui_result_content(
            status="failed",
            action="author_spec",
            extra={"error_code": "save_failed"},
        )
    return ui_result_content(
        status="ok",
        action="author_spec",
        extra={"diagram_id": saved, "title": title, "topic": topic},
    )
