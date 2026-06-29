"""Per-source chunking policy for File Center packages.

Resolves the chunking *mode* and *engine* for a single source based on its
file type. The plan for File Center (文件中心) is:

* PDF / DOCX / PPTX (textbooks, reports) → hierarchical semchunk so that
  ``section_title`` metadata is emitted for "Chapter 5"-style branch retrieval.
* Web snapshots and pasted notes (short, no table of contents) → flat semchunk.
* MindChunk (LLM-based) stays opt-in via ``CHUNKING_ENGINE=mindchunk`` until the
  hardening sweep lands; v1 never defaults File Center to MindChunk.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import os
from dataclasses import dataclass
from typing import Optional

from services.knowledge.chat_handoff_platforms import FLAT_TEXT_INGEST_SOURCES

# File types that carry structure worth preserving (TOC, headings, pages).
HIERARCHICAL_FILE_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
        "application/msword",  # .doc
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",  # .pptx
        "application/vnd.ms-powerpoint",  # .ppt
    }
)

# Modes a space's processing_rules may pin explicitly (honoured over defaults).
EXPLICIT_MODES = frozenset({"hierarchical", "custom", "automatic"})


@dataclass(frozen=True)
class ChunkingPolicy:
    """Resolved chunking decision for one source."""

    mode: str  # "hierarchical" | "automatic" | "custom"
    engine: str  # "semchunk" | "mindchunk"


def resolve_chunking_engine() -> str:
    """Return the configured chunking engine (``semchunk`` unless opted in)."""
    return "mindchunk" if os.getenv("CHUNKING_ENGINE", "semchunk").lower() == "mindchunk" else "semchunk"


def resolve_chunking_policy(
    file_type: Optional[str],
    processing_rules: Optional[dict],
    ingest_source: Optional[str] = None,
) -> ChunkingPolicy:
    """Resolve the chunking mode and engine for a File Center source.

    An explicit ``mode`` in ``processing_rules`` always wins; otherwise the mode
    defaults to ``hierarchical`` for document-like file types and ``automatic``
    (flat) for short text such as web snapshots and pasted notes.
    """
    engine = resolve_chunking_engine()

    explicit_mode = (processing_rules or {}).get("mode")
    if explicit_mode in EXPLICIT_MODES:
        return ChunkingPolicy(mode=explicit_mode, engine=engine)

    if ingest_source in FLAT_TEXT_INGEST_SOURCES:
        return ChunkingPolicy(mode="automatic", engine=engine)

    if file_type in HIERARCHICAL_FILE_TYPES:
        return ChunkingPolicy(mode="hierarchical", engine=engine)

    return ChunkingPolicy(mode="automatic", engine=engine)
