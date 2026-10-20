"""
Simplified Chinese policy for overseas email accounts.

Those accounts cannot use Simplified Chinese while OVERSEAS_SIMPLIFIED_CHINESE
is off (the default). Generation then uses Traditional Chinese (``zh-hant``),
and Simplified glyphs in model text are converted with OpenCC s2t. Set the
switch true to restore Simplified Chinese without changing stored accounts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import importlib
import json
import logging
from contextvars import ContextVar
from typing import Any

from config.settings import config

logger = logging.getLogger(__name__)

_SIMPLIFIED_CODES = frozenset({"zh", "zh-cn", "zh-hans", "zh-sg"})
_TRADITIONAL_CODES = frozenset({"zh-hant", "zh-tw", "zh-hk", "zh-mo"})
_GENERATION_TRADITIONAL = "zh-hant"

_forbid_simplified: ContextVar[bool] = ContextVar("forbid_simplified_chinese", default=False)


class _OpenCcConverterState:
    """Lazy OpenCC s2t converter holder."""

    instance: Any = None


def _s2t_converter():
    """Lazy singleton OpenCC s2t (Simplified -> Traditional) for glyph detection."""
    if _OpenCcConverterState.instance is None:
        opencc_mod = importlib.import_module("opencc")
        opencc_cls = getattr(opencc_mod, "OpenCC")
        _OpenCcConverterState.instance = opencc_cls("s2t")
    return _OpenCcConverterState.instance


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


def to_traditional_chinese(text: str) -> str:
    """Convert Simplified glyphs to Traditional. Unchanged when OpenCC finds no delta."""
    if not text or not str(text).strip():
        return text
    stripped = str(text)
    if not text_contains_simplified_chinese_glyphs(stripped):
        return stripped
    try:
        return _s2t_converter().convert(stripped)
    except (OSError, ValueError, TypeError) as exc:
        logger.debug("OpenCC convert failed: %s", exc)
        return stripped


def overseas_simplified_chinese_enabled() -> bool:
    """True when the env switch restores Simplified Chinese for overseas accounts."""
    return bool(config.OVERSEAS_SIMPLIFIED_CHINESE)


def user_allows_simplified_chinese(user: Any) -> bool:
    """True unless this overseas account is still under the Simplified Chinese block."""
    if overseas_simplified_chinese_enabled():
        return True
    if user is None:
        return True
    value = getattr(user, "allows_simplified_chinese", True)
    if value is None:
        return True
    return bool(value)


def bind_simplified_chinese_policy(user: Any) -> None:
    """Pin the current task so later LLM calls follow this account's script policy."""
    _forbid_simplified.set(not user_allows_simplified_chinese(user))


def clear_simplified_chinese_policy() -> None:
    """Allow Simplified Chinese again on this task."""
    _forbid_simplified.set(False)


def simplified_chinese_forbidden() -> bool:
    """True while the bound account cannot use Simplified Chinese."""
    return _forbid_simplified.get()


def canonical_generation_language(language: str) -> str:
    """Map Chinese region tags onto registry codes ``zh`` and ``zh-hant``."""
    normalized = (language or "en").strip().lower().replace("_", "-")
    if normalized in _TRADITIONAL_CODES:
        return _GENERATION_TRADITIONAL
    if normalized in _SIMPLIFIED_CODES:
        return "zh"
    return normalized


def _fragments_have_simplified(*text_fragments: str) -> bool:
    """True when any fragment contains a Simplified-only glyph."""
    combined = " ".join(str(t).strip() for t in text_fragments if t and str(t).strip())
    return bool(combined) and text_contains_simplified_chinese_glyphs(combined)


def _language_without_simplified(lang: str, *text_fragments: str) -> str:
    """Traditional generation code when the request or the text is Simplified."""
    if lang == "zh" or _fragments_have_simplified(*text_fragments):
        return _GENERATION_TRADITIONAL
    return lang


def effective_language_for_thinking_user(
    user: Any,
    requested_language: str,
    *text_fragments: str,
) -> str:
    """
    Generation language for one user.

    Overseas accounts never receive ``zh``. Explicit Simplified and Simplified
    glyphs both become ``zh-hant``.
    """
    lang = canonical_generation_language(requested_language or "en")
    if user_allows_simplified_chinese(user):
        return lang
    return _language_without_simplified(lang, *text_fragments)


def coerce_generation_language(language: str, *text_fragments: str) -> str:
    """Apply the task policy when the route already bound the signed-in user."""
    lang = canonical_generation_language(language or "en")
    if not simplified_chinese_forbidden():
        return lang
    return _language_without_simplified(lang, *text_fragments)


def sse_data(payload: Any) -> str:
    """SSE data line with Simplified glyphs rewritten when the account forbids them."""
    return f"data: {json.dumps(guard_user_visible(payload))}\n\n"


def guard_json_text(payload: str) -> str:
    """Rewrite Simplified glyphs in a JSON string when the account forbids them."""
    if not simplified_chinese_forbidden() or not payload:
        return payload
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError:
        return payload
    return json.dumps(guard_user_visible(parsed), ensure_ascii=False)


def guard_user_visible(value: Any) -> Any:
    """Rewrite Simplified glyphs in returned JSON when the account forbids them."""
    if not simplified_chinese_forbidden():
        return value
    return _traditionalize_tree(value)


def _traditionalize_tree(value: Any) -> Any:
    """Walk JSON-like values and convert Simplified strings."""
    if isinstance(value, str):
        return to_traditional_chinese(value)
    if isinstance(value, dict):
        return {key: _traditionalize_tree(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_traditionalize_tree(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_traditionalize_tree(item) for item in value)
    return value


def _walk_diagram_texts(obj: Any, parts: list[str]) -> None:
    """Walk diagram texts."""
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key in ("text", "label") and isinstance(val, str) and val.strip():
                parts.append(val)
            else:
                _walk_diagram_texts(val, parts)
    elif isinstance(obj, list):
        for item in obj:
            _walk_diagram_texts(item, parts)


def collect_ai_brainstorm_text_blobs(req: Any, center_topic: str) -> tuple[str, ...]:
    """Extract text from AI brainstorm request for SC detection."""
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
