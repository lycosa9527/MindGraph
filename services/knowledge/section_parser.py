"""Detect document sections (chapters / headings) for hierarchical semchunk.

Splits long sources on heading boundaries so each chunk carries ``section_title``
and ``section_key`` metadata (e.g. ``chapter-5``) for scoped RAG retrieval.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Pattern, Tuple

from services.knowledge.document_structure import StructureHeading, resolve_structure_headings
from services.knowledge.section_keys import build_section_key, chinese_numeral_to_int

_HEADING_RULES: Tuple[Tuple[Pattern[str], str], ...] = (
    (re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE), "markdown"),
    (re.compile(r"^(?:Chapter|CHAPTER)\s+(\d+)\s*[:\.\-\s]*(.*)$", re.MULTILINE | re.IGNORECASE), "chapter_en"),
    (re.compile(r"^第(\d+)章\s*[：:\s]*(.*)$", re.MULTILINE), "chapter_zh_digit"),
    (re.compile(r"^第([一二三四五六七八九十百千]+)章\s*[：:\s]*(.*)$", re.MULTILINE), "chapter_zh_cn"),
    (
        re.compile(
            r"^(?:Section|SECTION)\s+(\d+(?:\.\d+)*)\s*[:\.\-\s]*(.*)$",
            re.MULTILINE | re.IGNORECASE,
        ),
        "section_en",
    ),
    (re.compile(r"^(\d+(?:\.\d+)*)\s+([A-Z\u4e00-\u9fff].+)$", re.MULTILINE), "numbered"),
    (re.compile(r"^([一二三四五六七八九十百千]+)[、．.]([^\n]{2,50})$", re.MULTILINE), "chapter_zh_enum"),
)


@dataclass(frozen=True)
class DocumentSection:
    """A contiguous span of text under one heading."""

    title: str
    level: int
    section_key: str
    section_number: str
    start: int
    end: int
    body: str


def _parse_heading_match(kind: str, match: re.Match[str]) -> Tuple[str, int, str, str]:
    if kind == "markdown":
        level = len(match.group(1))
        title = match.group(2).strip()
        number = str(level)
        section_key = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", title.lower())
        section_key = re.sub(r"\s+", "-", section_key)[:80] or f"heading-{level}"
        return title, level, section_key, number

    if kind in {"chapter_en", "chapter_zh_digit"}:
        number = match.group(1)
        suffix = (match.group(2) or "").strip()
        title = f"Chapter {number}" + (f": {suffix}" if suffix else "")
        return title, 1, build_section_key(kind, number, title), number

    if kind == "chapter_zh_cn":
        parsed = chinese_numeral_to_int(match.group(1))
        if parsed is None:
            number = match.group(1)
        else:
            number = str(parsed)
        suffix = (match.group(2) or "").strip()
        title = f"第{number}章" + (f" {suffix}" if suffix else "")
        return title, 1, build_section_key("chapter_zh_digit", number, title), number

    if kind == "section_en":
        number = match.group(1)
        suffix = (match.group(2) or "").strip()
        title = f"Section {number}" + (f": {suffix}" if suffix else "")
        level = number.count(".") + 1
        return title, level, build_section_key(kind, number, title), number

    if kind == "chapter_zh_enum":
        numeral = match.group(1)
        parsed = chinese_numeral_to_int(numeral)
        number = str(parsed) if parsed is not None else numeral
        suffix = (match.group(2) or "").strip()
        title = f"{numeral}、{suffix}"
        return title, 1, build_section_key("chapter_zh_digit", number, suffix), number

    number = match.group(1)
    title = match.group(2).strip()
    level = number.count(".") + 1
    return title, level, build_section_key("numbered", number, title), number


def detect_section_headings(text: str) -> List[dict]:
    """Return heading markers sorted by ``position``."""
    headings: List[dict] = []
    seen_positions: set[int] = set()

    for pattern, kind in _HEADING_RULES:
        for match in pattern.finditer(text):
            pos = match.start()
            if pos in seen_positions:
                continue
            title, level, section_key, section_number = _parse_heading_match(kind, match)
            if len(title) < 2:
                continue
            headings.append(
                {
                    "title": title,
                    "level": level,
                    "section_key": section_key,
                    "section_number": section_number,
                    "position": pos,
                    "line_end": match.end(),
                }
            )
            seen_positions.add(pos)

    headings.sort(key=lambda item: item["position"])
    return headings


def split_into_sections(
    text: str,
    structure_headings: Optional[List[StructureHeading]] = None,
    page_info: Optional[List[dict]] = None,
) -> List[DocumentSection]:
    """Split *text* into sections using structure, then regex headings."""
    cleaned = text or ""
    if not cleaned.strip():
        return []

    headings: List[dict] = []
    if structure_headings:
        headings = resolve_structure_headings(cleaned, structure_headings, page_info)
    if not headings:
        headings = detect_section_headings(cleaned)
    if not headings:
        return []

    sections: List[DocumentSection] = []
    for index, heading in enumerate(headings):
        body_start = heading["line_end"]
        body_end = headings[index + 1]["position"] if index + 1 < len(headings) else len(cleaned)
        body = cleaned[body_start:body_end].strip()
        if not body and index + 1 < len(headings):
            continue
        if not body and index == len(headings) - 1:
            body = cleaned[body_start:].strip()
        if not body:
            continue
        sections.append(
            DocumentSection(
                title=heading["title"],
                level=int(heading["level"]),
                section_key=str(heading["section_key"]),
                section_number=str(heading["section_number"]),
                start=int(heading["position"]),
                end=body_end,
                body=body,
            )
        )

    return sections
