"""Extract document structure (PDF outline, DOCX heading styles) for hierarchical chunking."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from services.knowledge.section_keys import build_section_key, chinese_numeral_to_int

logger = logging.getLogger(__name__)

_pypdf_mod: Any = None
_pypdf_available = False
try:
    import pypdf as _pypdf_import

    _pypdf_mod = _pypdf_import
    _pypdf_available = True
except ImportError:
    pass

_docx_document_cls: Any = None
_docx_available = False
try:
    from docx import Document as _docx_document_import

    _docx_document_cls = _docx_document_import
    _docx_available = True
except ImportError:
    pass

_HEADING_STYLE_PREFIX = "heading"


@dataclass(frozen=True)
class StructureHeading:
    """A heading from PDF outline or DOCX styles."""

    title: str
    level: int
    page: Optional[int] = None
    char_position: Optional[int] = None
    source: str = "regex"


def _normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _infer_section_fields(title: str) -> tuple[str, str, int]:
    """Derive section_key, section_number, and level from a title string."""
    cleaned = _normalize_title(title)
    chapter_en = re.match(r"^(?:Chapter|CHAPTER)\s+(\d+)", cleaned, re.IGNORECASE)
    if chapter_en:
        number = chapter_en.group(1)
        return build_section_key("chapter_en", number, cleaned), number, 1

    chapter_zh = re.match(r"^第(\d+)章", cleaned)
    if chapter_zh:
        number = chapter_zh.group(1)
        return build_section_key("chapter_zh_digit", number, cleaned), number, 1

    chapter_cn = re.match(r"^第([一二三四五六七八九十百千]+)章", cleaned)
    if chapter_cn:
        parsed = chinese_numeral_to_int(chapter_cn.group(1))
        number = str(parsed) if parsed is not None else chapter_cn.group(1)
        return build_section_key("chapter_zh_digit", number, cleaned), number, 1

    section_en = re.match(r"^(?:Section|SECTION)\s+(\d+(?:\.\d+)*)", cleaned, re.IGNORECASE)
    if section_en:
        number = section_en.group(1)
        return build_section_key("section_en", number, cleaned), number, number.count(".") + 1

    numbered = re.match(r"^(\d+(?:\.\d+)*)\s+\S", cleaned)
    if numbered:
        number = numbered.group(1)
        return build_section_key("numbered", number, cleaned), number, number.count(".") + 1

    slug = re.sub(r"[^\w\u4e00-\u9fff\- ]+", "", cleaned.lower())
    slug = re.sub(r"\s+", "-", slug)[:80] or "section"
    return slug, "0", 1


def extract_pdf_outline(file_path: str) -> List[StructureHeading]:
    """Read embedded PDF bookmarks/outline when available."""
    if not _pypdf_available or _pypdf_mod is None:
        logger.debug("[DocumentStructure] pypdf unavailable for outline extraction")
        return []

    headings: List[StructureHeading] = []
    try:
        reader = _pypdf_mod.PdfReader(file_path)

        def walk(items: Any, level: int = 1) -> None:
            if not items:
                return
            for item in items:
                if isinstance(item, list):
                    walk(item, level + 1)
                    continue
                title = getattr(item, "title", None) or str(item)
                title = _normalize_title(title)
                if len(title) < 2:
                    continue
                page_num: Optional[int] = None
                try:
                    page_num = reader.get_destination_page_number(item) + 1
                except (TypeError, ValueError, AttributeError):
                    page_num = None
                headings.append(
                    StructureHeading(
                        title=title,
                        level=level,
                        page=page_num,
                        source="pdf_outline",
                    )
                )

        walk(getattr(reader, "outline", None))
    except (OSError, ValueError, TypeError, AttributeError) as exc:
        logger.warning("[DocumentStructure] PDF outline extraction failed: %s", exc)
        return []

    return headings


def extract_docx_headings(file_path: str) -> tuple[str, List[StructureHeading]]:
    """Extract DOCX text and heading-style paragraph offsets."""
    if not _docx_available or _docx_document_cls is None:
        raise ImportError("python-docx required for DOCX extraction")

    doc = _docx_document_cls(file_path)
    text_parts: List[str] = []
    headings: List[StructureHeading] = []
    current_pos = 0

    for paragraph in doc.paragraphs:
        raw = paragraph.text
        if not raw.strip():
            continue
        style_name = (paragraph.style.name if paragraph.style else "").lower()
        if style_name.startswith(_HEADING_STYLE_PREFIX):
            level_text = style_name.replace(_HEADING_STYLE_PREFIX, "").strip() or "1"
            try:
                level = int(level_text)
            except ValueError:
                level = 1
            headings.append(
                StructureHeading(
                    title=_normalize_title(raw),
                    level=level,
                    char_position=current_pos,
                    source="docx_style",
                )
            )
        text_parts.append(raw)
        current_pos += len(raw) + 2

    return "\n\n".join(text_parts), headings


def extract_document_structure(
    file_path: str,
    file_type: str,
) -> List[StructureHeading]:
    """Return structural headings for supported file types."""
    if file_type == "application/pdf":
        return extract_pdf_outline(file_path)
    if file_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        _, headings = extract_docx_headings(file_path)
        return headings
    return []


def _page_char_offset(page_info: List[Dict[str, Any]], page: int) -> int:
    for entry in page_info:
        if int(entry.get("page", 0)) == page:
            return int(entry.get("start", 0))
    return 0


def find_title_position(text: str, title: str, search_from: int = 0, window: int = 4000) -> int:
    """Locate *title* in *text* near *search_from* (whitespace-tolerant)."""
    if not title or not text:
        return -1

    needle = _normalize_title(title)
    if not needle:
        return -1

    start = max(0, search_from)
    end = min(len(text), start + window)
    haystack = text[start:end]

    exact = haystack.find(needle)
    if exact >= 0:
        return start + exact

    compact_needle = re.sub(r"\s+", "", needle.lower())
    if len(compact_needle) < 3:
        return -1

    for match in re.finditer(r"\S+(?:\s+\S+)*", haystack):
        segment = match.group(0)
        compact_segment = re.sub(r"\s+", "", segment.lower())
        if compact_segment == compact_needle or compact_needle in compact_segment:
            return start + match.start()

    return -1


def resolve_structure_headings(
    text: str,
    headings: List[StructureHeading],
    page_info: Optional[List[Dict[str, Any]]] = None,
) -> List[dict]:
    """Map structure headings to character positions in extracted *text*."""
    if not text or not headings:
        return []

    resolved: List[dict] = []
    search_cursor = 0

    for heading in headings:
        position = heading.char_position
        if position is None and heading.page and page_info:
            position = find_title_position(
                text,
                heading.title,
                search_from=_page_char_offset(page_info, heading.page),
            )
        if position is None or position < 0:
            position = find_title_position(text, heading.title, search_from=search_cursor)
        if position < 0:
            continue

        section_key, section_number, level = _infer_section_fields(heading.title)
        line_end = position + len(heading.title)
        resolved.append(
            {
                "title": heading.title,
                "level": heading.level or level,
                "section_key": section_key,
                "section_number": section_number,
                "position": position,
                "line_end": line_end,
                "source": heading.source,
            }
        )
        search_cursor = line_end

    resolved.sort(key=lambda item: item["position"])
    deduped: List[dict] = []
    seen: set[int] = set()
    for item in resolved:
        pos = int(item["position"])
        if pos in seen:
            continue
        seen.add(pos)
        deduped.append(item)
    return deduped
