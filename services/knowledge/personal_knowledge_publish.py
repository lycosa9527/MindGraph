"""Publish one personal-knowledge file as markdown objects.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument
from services.knowledge.package_rag_scope import PERSONAL_KNOWLEDGE_SOURCES
from services.knowledge.personal_knowledge_log import log_personal_knowledge
from services.knowledge.vibeflow_cut import VibeflowPiece, build_vibeflow_pieces
from services.knowledge.vibeflow_store import (
    delete_document_objects,
    document_prefix,
    upload_pieces,
    vibe_owner_prefix,
)


async def _set_progress(db: AsyncSession, document: KnowledgeDocument, progress: str, percent: int) -> None:
    """Store the stage the application can read while Celery is still running."""
    document.status = "processing"
    document.processing_progress = progress
    document.processing_progress_percent = percent
    await db.commit()


def replace_personal_objects(
    user_id: int,
    package_id: int,
    document_id: int,
    pieces: List[VibeflowPiece],
) -> bool:
    """Replace one document's markdown objects. False when a write fails."""
    delete_document_objects(user_id, package_id, document_id)
    return upload_pieces(user_id, package_id, document_id, pieces)


async def publish_personal_knowledge(
    db: AsyncSession,
    user_id: int,
    document: KnowledgeDocument,
    cleaned_text: str,
    structure_headings: Optional[list],
    page_info: Optional[list] = None,
) -> bool:
    """Store a personal-knowledge file as markdown objects. False for other sources."""
    if document.batch_id is None:
        return False
    batch = await db.get(DocumentBatch, document.batch_id)
    if batch is None or batch.source not in PERSONAL_KNOWLEDGE_SOURCES:
        return False
    await _set_progress(db, document, "splitting", 40)
    log_personal_knowledge(
        "splitting",
        user=user_id,
        package=batch.id,
        document=document.id,
        file=document.file_name,
        source=batch.source,
        chars=len(cleaned_text or ""),
        headings=len(structure_headings or []),
    )
    pieces = build_vibeflow_pieces(
        cleaned_text,
        structure_headings,
        page_info,
        user_id=user_id,
        package_id=batch.id,
        document_id=document.id,
    )
    if not pieces:
        raise ValueError(f"Personal knowledge cut produced no pieces for document {document.id}")
    await _set_progress(db, document, "sending_oss", 70)
    saved = await asyncio.to_thread(
        replace_personal_objects,
        user_id,
        batch.id,
        document.id,
        pieces,
    )
    if not saved:
        raise ValueError(f"Personal knowledge upload failed for document {document.id}")
    await _set_progress(db, document, "embedding", 90)
    log_personal_knowledge(
        "embedding",
        user=user_id,
        package=batch.id,
        document=document.id,
        objects=len(pieces),
        server=vibe_owner_prefix(),
        prefix=document_prefix(user_id, batch.id, document.id),
    )
    metadata = dict(document.doc_metadata or {})
    metadata["vibeflow"] = True
    metadata["local_original_removed"] = True
    document.doc_metadata = metadata
    document.chunk_count = len(pieces)
    document.status = "completed"
    document.processing_progress = None
    document.processing_progress_percent = 100
    if document.file_path and Path(document.file_path).exists():
        Path(document.file_path).unlink()
    document.file_path = ""
    await db.commit()
    log_personal_knowledge(
        "completed",
        user=user_id,
        package=batch.id,
        document=document.id,
        pieces=len(pieces),
    )
    return True
