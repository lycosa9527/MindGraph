"""Shared section key helpers (no imports from section_parser / document_structure)."""

from __future__ import annotations

import re
from typing import Optional

_CN_NUMERAL_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "百": 100,
    "千": 1000,
}


def chinese_numeral_to_int(raw: str) -> Optional[int]:
    """Convert simple Chinese numerals (e.g. ``五``, ``十五``) to an integer."""
    text = (raw or "").strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)

    total = 0
    current = 0
    for char in text:
        if char not in _CN_NUMERAL_MAP:
            return None
        value = _CN_NUMERAL_MAP[char]
        if value >= 10:
            if current == 0:
                current = 1
            total += current * value
            current = 0
        else:
            current = current * 10 + value if current >= 10 else value
    return total + current


def build_section_key(kind: str, number: str, title: str) -> str:
    """Build a stable slug-like key for Qdrant filtering."""
    if kind in {"chapter_en", "chapter_zh_digit", "chapter_zh_cn"}:
        return f"chapter-{number}"
    if kind == "section_en":
        return f"section-{number.replace('.', '-')}"
    slug = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", title.lower()).strip()
    slug = re.sub(r"\s+", "-", slug)[:80]
    return slug or "section"
