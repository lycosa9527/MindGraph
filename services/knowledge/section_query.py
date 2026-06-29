"""Parse user queries for chapter/section scope (e.g. ``summary chapter 5``)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from services.knowledge.section_keys import chinese_numeral_to_int

_CHAPTER_EN = re.compile(r"\bchapter\s+(\d+)\b", re.IGNORECASE)
_CHAPTER_ZH_DIGIT = re.compile(r"第(\d+)章")
_CHAPTER_ZH_CN = re.compile(r"第([一二三四五六七八九十百千]+)章")
_SECTION_EN = re.compile(r"\bsection\s+(\d+(?:\.\d+)*)\b", re.IGNORECASE)
_SUMMARY_HINT = re.compile(
    r"\b(summary|summarize|summarise|overview|outline|recap|总结|摘要|概括|概述)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SectionHint:
    """Resolved section scope from a natural-language query."""

    section_key: str
    section_number: str
    label: str


def parse_section_hint(query: str) -> Optional[SectionHint]:
    """Return a section filter hint when the query names a chapter or section."""
    text = (query or "").strip()
    if not text:
        return None

    match = _CHAPTER_EN.search(text)
    if match:
        number = match.group(1)
        return SectionHint(
            section_key=f"chapter-{number}",
            section_number=number,
            label=f"Chapter {number}",
        )

    match = _CHAPTER_ZH_DIGIT.search(text)
    if match:
        number = match.group(1)
        return SectionHint(
            section_key=f"chapter-{number}",
            section_number=number,
            label=f"第{number}章",
        )

    match = _CHAPTER_ZH_CN.search(text)
    if match:
        parsed = chinese_numeral_to_int(match.group(1))
        if parsed is not None:
            number = str(parsed)
            return SectionHint(
                section_key=f"chapter-{number}",
                section_number=number,
                label=f"第{number}章",
            )

    match = _SECTION_EN.search(text)
    if match:
        number = match.group(1)
        return SectionHint(
            section_key=f"section-{number.replace('.', '-')}",
            section_number=number,
            label=f"Section {number}",
        )

    return None


def is_section_summary_query(query: str) -> bool:
    """True when the user asks for a summary/overview of a scoped section."""
    text = (query or "").strip()
    if not text:
        return False
    return _SUMMARY_HINT.search(text) is not None and parse_section_hint(text) is not None
