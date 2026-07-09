"""
Known-but-unsupported diagram type requests for Kitty fallback replies.

Cross-referenced with ``KITTY_CANONICAL_DIAGRAM_TYPES`` in kitty_diagram_vocabulary.
When users ask for these (e.g. fishbone / 鱼骨图), Kitty emits a templated ack
suggesting a supported alternative (default: mind map).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Optional, TypedDict


class UnsupportedDiagramMatch(TypedDict):
    """Slots for unsupported-diagram acknowledgment templates."""

    requested_type: str
    alternative_label: str
    alternative_slug: str
    entry_id: str


class _UnsupportedEntry(TypedDict):
    id: str
    aliases: FrozenSet[str]
    label_zh: str
    label_en: str
    alternative_slug: str
    alternative_zh: str
    alternative_en: str


_UNSUPPORTED_ENTRIES: List[_UnsupportedEntry] = [
    {
        "id": "fishbone",
        "aliases": frozenset(
            {
                "fishbone",
                "fish bone",
                "fish-bone",
                "ishikawa",
                "鱼骨图",
                "鱼骨",
                "石川图",
            }
        ),
        "label_zh": "鱼骨图",
        "label_en": "fishbone diagram",
        "alternative_slug": "mind_map",
        "alternative_zh": "思维导图",
        "alternative_en": "mind map",
    },
    {
        "id": "org_chart",
        "aliases": frozenset(
            {
                "org chart",
                "organization chart",
                "organizational chart",
                "组织架构图",
                "组织图",
                "组织结构图",
            }
        ),
        "label_zh": "组织架构图",
        "label_en": "org chart",
        "alternative_slug": "tree_map",
        "alternative_zh": "树形图",
        "alternative_en": "tree map",
    },
    {
        "id": "gantt",
        "aliases": frozenset(
            {
                "gantt",
                "gantt chart",
                "甘特图",
            }
        ),
        "label_zh": "甘特图",
        "label_en": "Gantt chart",
        "alternative_slug": "flow_map",
        "alternative_zh": "流程图",
        "alternative_en": "flow map",
    },
    {
        "id": "venn",
        "aliases": frozenset(
            {
                "venn",
                "venn diagram",
                "韦恩图",
                "文氏图",
            }
        ),
        "label_zh": "韦恩图",
        "label_en": "Venn diagram",
        "alternative_slug": "double_bubble_map",
        "alternative_zh": "双气泡图",
        "alternative_en": "double bubble map",
    },
    {
        "id": "swot",
        "aliases": frozenset(
            {
                "swot",
                "swot analysis",
                "swot图",
                "swot分析",
            }
        ),
        "label_zh": "SWOT 分析图",
        "label_en": "SWOT diagram",
        "alternative_slug": "mind_map",
        "alternative_zh": "思维导图",
        "alternative_en": "mind map",
    },
]

_ALIAS_TO_ENTRY: Dict[str, _UnsupportedEntry] = {}
for _row in _UNSUPPORTED_ENTRIES:
    for _alias in _row["aliases"]:
        _ALIAS_TO_ENTRY[_alias.lower()] = _row
        _ALIAS_TO_ENTRY[_alias] = _row

_DIAGRAM_INTENT_HINTS_ZH = ("图", "画", "绘制", "新建", "打开", "做一张", "生成")
_DIAGRAM_INTENT_HINTS_EN = ("diagram", "chart", "map", "draw", "create", "open", "make")


def _normalize_lookup_key(raw: str) -> str:
    return str(raw or "").strip().lower().replace("-", " ")


def _match_entry_from_raw(raw: Optional[str]) -> Optional[_UnsupportedEntry]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    direct = _ALIAS_TO_ENTRY.get(text) or _ALIAS_TO_ENTRY.get(text.lower())
    if direct:
        return direct
    lowered = _normalize_lookup_key(text)
    return _ALIAS_TO_ENTRY.get(lowered)


def _text_mentions_diagram_intent(text: str) -> bool:
    lowered = text.lower()
    if any(hint in text for hint in _DIAGRAM_INTENT_HINTS_ZH):
        return True
    return any(hint in lowered for hint in _DIAGRAM_INTENT_HINTS_EN)


def _match_entry_from_text(text: str) -> Optional[_UnsupportedEntry]:
    body = str(text or "").strip()
    if not body:
        return None
    lowered = body.lower()
    for entry in _UNSUPPORTED_ENTRIES:
        for alias in entry["aliases"]:
            alias_lower = alias.lower()
            if len(alias) <= 2:
                continue
            if alias in body or alias_lower in lowered:
                if _text_mentions_diagram_intent(body) or alias in ("鱼骨图", "鱼骨", "甘特图"):
                    return entry
    return None


def _build_match(entry: _UnsupportedEntry, *, lang: str) -> UnsupportedDiagramMatch:
    use_en = str(lang).strip().lower().startswith("en")
    if use_en:
        requested = entry["label_en"]
        alternative = entry["alternative_en"]
    else:
        requested = entry["label_zh"]
        alternative = entry["alternative_zh"]
    return UnsupportedDiagramMatch(
        requested_type=requested,
        alternative_label=alternative,
        alternative_slug=entry["alternative_slug"],
        entry_id=entry["id"],
    )


def resolve_unsupported_diagram_type(
    *,
    text: Optional[str] = None,
    raw_slug: Optional[str] = None,
    lang: str = "zh",
) -> Optional[UnsupportedDiagramMatch]:
    """
    Detect a known unsupported diagram request from user text or a raw diagram_type slug.

    Returns match slots for ack templates, or None when no unsupported type is recognized.
    """
    entry = _match_entry_from_raw(raw_slug)
    if entry is None and text:
        entry = _match_entry_from_text(text)
    if entry is None:
        return None
    return _build_match(entry, lang=lang)


def unsupported_match_from_unknown_slug(raw_slug: str, *, lang: str = "zh") -> UnsupportedDiagramMatch:
    """Fallback slots when diagram_type is unknown but not in the planned registry."""
    label = str(raw_slug or "").strip() or ("diagram" if lang.startswith("en") else "这种图")
    use_en = str(lang).strip().lower().startswith("en")
    return UnsupportedDiagramMatch(
        requested_type=label,
        alternative_label="mind map" if use_en else "思维导图",
        alternative_slug="mind_map",
        entry_id="unknown",
    )
