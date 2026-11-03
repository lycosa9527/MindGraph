"""Cut personal-knowledge text for VibeFlow.

A table of contents is used only after its titles are found, in order, across
the extracted text. Otherwise the whole extract is split into token windows.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from services.knowledge.chunking_service import ChunkingService
from services.knowledge.document_structure import StructureHeading, resolve_structure_headings
from services.knowledge.personal_knowledge_log import log_personal_knowledge
from services.knowledge.section_parser import split_into_sections

MIN_TOC_MATCHES = 3
MIN_TOC_RATIO = 0.6
MIN_TOC_SPAN_RATIO = 0.15
EMBED_TOKEN_LIMIT = 32000
CHARS_PER_TOKEN = 4


@dataclass(frozen=True)
class VibeflowPiece:
    """One markdown object to store under a section number."""

    section_number: str
    title: str
    text: str
    index: int


def _safe_number(raw: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z.\-_]", "-", (raw or "").strip())
    cleaned = cleaned.strip(".-")[:80]
    return cleaned or "document"


def _tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _window_bodies(text: str) -> List[str]:
    service = ChunkingService(chunk_size=500, overlap=50, mode="automatic")
    chunks = service.chunk_text(text, extract_structure=False)
    bodies = [chunk.text.strip() for chunk in chunks if chunk.text and chunk.text.strip()]
    return bodies or [text.strip()]


def _split_oversized(body: str) -> List[str]:
    if _tokens(body) <= EMBED_TOKEN_LIMIT:
        return [body.strip()]
    limit_chars = EMBED_TOKEN_LIMIT * CHARS_PER_TOKEN
    parts: List[str] = []
    start = 0
    while start < len(body):
        parts.append(body[start : start + limit_chars].strip())
        start += limit_chars
    return [part for part in parts if part]


def _toc_status(
    text: str,
    headings: Sequence[StructureHeading],
    page_info: Optional[list] = None,
) -> Tuple[bool, str, int]:
    """Return whether the outline is usable, why, and how many titles matched."""
    if not text.strip():
        return False, "empty", 0
    if len(headings) < MIN_TOC_MATCHES:
        return False, "too_few_headings", 0
    resolved = resolve_structure_headings(text, list(headings), page_info)
    matched = len(resolved)
    if matched < MIN_TOC_MATCHES:
        return False, "too_few_matches", matched
    if matched / len(headings) < MIN_TOC_RATIO:
        return False, "low_match_ratio", matched
    positions = [int(item["position"]) for item in resolved]
    span = max(positions) - min(positions)
    if span < max(500, int(len(text) * MIN_TOC_SPAN_RATIO)):
        return False, "narrow_span", matched
    return True, "confirmed", matched


def toc_is_confirmed(
    text: str,
    headings: Sequence[StructureHeading],
    page_info: Optional[list] = None,
) -> bool:
    """True when most bookmark titles are found in order and spread through the text."""
    confirmed, _reason, _matched = _toc_status(text, headings, page_info)
    return confirmed


def build_vibeflow_pieces(
    text: str,
    headings: Optional[Sequence[StructureHeading]] = None,
    page_info: Optional[list] = None,
    *,
    user_id: Optional[int] = None,
    package_id: Optional[int] = None,
    document_id: Optional[int] = None,
) -> List[VibeflowPiece]:
    """Return ordered pieces. A confirmed outline is one piece per entry."""
    cleaned = (text or "").strip()
    outline = list(headings or [])
    fields: dict[str, object] = {}
    if user_id is not None:
        fields["user"] = user_id
    if package_id is not None:
        fields["package"] = package_id
    if document_id is not None:
        fields["document"] = document_id
    if not cleaned:
        log_personal_knowledge("no_toc", reason="empty", **fields)
        return []
    confirmed, reason, matched = _toc_status(cleaned, outline, page_info)
    if confirmed:
        log_personal_knowledge(
            "toc_found",
            headings=len(outline),
            matched=matched,
            **fields,
        )
        pieces = _pieces_from_outline(cleaned, outline, page_info)
        mode = "toc"
    else:
        log_personal_knowledge(
            "no_toc",
            reason=reason,
            headings=len(outline),
            matched=matched,
            **fields,
        )
        pieces = _pieces_from_windows(cleaned)
        mode = "windows"
    log_personal_knowledge(
        "split",
        mode=mode,
        pieces=len(pieces),
        chars=len(cleaned),
        **fields,
    )
    return pieces


def _pieces_from_outline(
    text: str,
    headings: Sequence[StructureHeading],
    page_info: Optional[list] = None,
) -> List[VibeflowPiece]:
    sections = split_into_sections(text, list(headings), page_info)
    pieces: List[VibeflowPiece] = []
    if sections:
        first = min(int(section.start) for section in sections)
        prefix = text[:first].strip()
        if prefix:
            pieces.extend(_pieces_from_windows(prefix))
    seen: dict[str, int] = {}
    for section in sections:
        number = section.section_number if section.section_number and section.section_number != "0" else ""
        folder = _safe_number(number or section.section_key or section.title)
        seen[folder] = seen.get(folder, 0) + 1
        if seen[folder] > 1 and number in {"", "0"}:
            folder = _safe_number(f"{folder}-{seen[folder]}")
        bodies = _split_oversized(section.body)
        for index, body in enumerate(bodies, start=1):
            pieces.append(
                VibeflowPiece(
                    section_number=folder,
                    title=section.title,
                    text=body,
                    index=index,
                )
            )
    return pieces


def _pieces_from_windows(text: str) -> List[VibeflowPiece]:
    pieces: List[VibeflowPiece] = []
    for index, body in enumerate(_window_bodies(text), start=1):
        pieces.append(
            VibeflowPiece(
                section_number="document",
                title="",
                text=body,
                index=index,
            )
        )
    return pieces
