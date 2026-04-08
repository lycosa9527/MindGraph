"""
Simplified Chinese detection and thinking-mode language overrides.

Overseas accounts with allows_simplified_chinese=False use Traditional Chinese (zh-tw)
for generation when Simplified glyphs are clearly detected (OpenCC s2t delta).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

_OPENCC_CONVERTER = None


def _s2t_converter():
    """Lazy singleton OpenCC s2t (Simplified -> Traditional) for glyph detection."""
    global _OPENCC_CONVERTER
    if _OPENCC_CONVERTER is None:
        opencc_mod = importlib.import_module("opencc")
        opencc_cls = getattr(opencc_mod, "OpenCC")
        _OPENCC_CONVERTER = opencc_cls("s2t")
    return _OPENCC_CONVERTER


def text_contains_simplified_chinese_glyphs(text: str) -> bool:
    """
    True if converting Simplified->Traditional changes the string (OpenCC s2t delta).

    Shared Hanzi with no SC-specific forms yield False (detect-only policy).
    """
    if not text or not str(text).strip():
        return False
    stripped = str(text).strip()
    try:
        converted = _s2t_converter().convert(stripped)
    except (OSError, ValueError, TypeError) as exc:
        logger.debug("OpenCC convert failed: %s", exc)
        return False
    return converted != stripped


def effective_language_for_thinking_user(
    user: Any,
    requested_language: str,
    *text_fragments: str,
) -> str:
    """
    Effective generation language for thinking-mode APIs.

    If the user cannot use Simplified Chinese:
    - explicit ``zh`` maps to ``zh-tw``;
    - otherwise, if SC glyphs are detected in text fragments, return ``zh-tw``;
    - else return the requested language unchanged.
    """
    lang = (requested_language or "en").strip().lower()
    allows = True
    if user is not None:
        allows = bool(getattr(user, "allows_simplified_chinese", True))
    if allows:
        return lang
    if lang == "zh":
        return "zh-tw"
    combined = " ".join(str(t).strip() for t in text_fragments if t and str(t).strip())
    if combined and text_contains_simplified_chinese_glyphs(combined):
        return "zh-tw"
    return lang


def _walk_diagram_texts(obj: Any, parts: list[str]) -> None:
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in ("text", "label") and isinstance(val, str) and val.strip():
                parts.append(val)
            else:
                _walk_diagram_texts(val, parts)
    elif isinstance(obj, list):
        for item in obj:
            _walk_diagram_texts(item, parts)


def collect_node_palette_text_blobs(req: Any, center_topic: str) -> tuple[str, ...]:
    """Extract text from node palette request for SC detection."""
    parts: list[str] = []
    if center_topic and str(center_topic).strip():
        parts.append(str(center_topic))
    diagram_data = getattr(req, "diagram_data", None)
    if isinstance(diagram_data, dict):
        _walk_diagram_texts(diagram_data, parts)
    edu = getattr(req, "educational_context", None)
    if isinstance(edu, dict):
        for key in ("raw_message", "topic", "grade_level", "subject"):
            val = edu.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val)
    return tuple(parts)


def collect_inline_recommendation_text_blobs(req: Any) -> tuple[str, ...]:
    """Extract text from inline recommendation request for SC detection."""
    parts: list[str] = []
    for node in getattr(req, "nodes", None) or []:
        if not isinstance(node, dict):
            continue
        text = node.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)
            continue
        data = node.get("data")
        if isinstance(data, dict):
            label = data.get("label")
            if isinstance(label, str) and label.strip():
                parts.append(label)
    edu = getattr(req, "educational_context", None)
    if isinstance(edu, dict):
        for key in ("raw_message", "topic"):
            val = edu.get(key)
            if isinstance(val, str) and val.strip():
                parts.append(val)
    return tuple(parts)


def collect_relationship_label_text_blobs(req: Any) -> tuple[str, ...]:
    """Extract concept/topic strings for SC detection."""
    parts: list[str] = []
    for attr in ("concept_a", "concept_b", "topic"):
        val = getattr(req, attr, None)
        if isinstance(val, str) and val.strip():
            parts.append(val)
    return tuple(parts)


def is_chinese_ui_error_language(language_code: str) -> bool:
    """Use Chinese SSE error strings for zh, zh-tw, zh-hant."""
    lo = (language_code or "").strip().lower()
    return lo == "zh" or lo == "zh-tw" or lo.startswith("zh-")
