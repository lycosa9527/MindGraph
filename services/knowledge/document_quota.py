"""Which stored files consume the per-user document cap.

Every file that still has a folder shares one pool, except a Document Summary
extract. A file whose folder row is gone cannot be deleted from settings, so
it does not consume the cap.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from sqlalchemy import Select, func, or_, select

from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument

_DOC_SUMMARY_SOURCE = "doc_summary"


def documents_toward_cap_stmt(space_id: int) -> Select[tuple[int]]:
    """Count files that still belong to a folder other than Document Summary.

    An inner join drops a file whose folder row is gone. Those rows are
    invisible in settings, so they must not fill the library.
    """
    not_doc_summary = or_(
        DocumentBatch.source.is_(None),
        DocumentBatch.source != _DOC_SUMMARY_SOURCE,
    )
    return (
        select(func.count(KnowledgeDocument.id))
        .select_from(KnowledgeDocument)
        .join(DocumentBatch, KnowledgeDocument.batch_id == DocumentBatch.id)
        .where(KnowledgeDocument.space_id == space_id, not_doc_summary)
    )


def over_quota_message(max_documents: int, count: int) -> str:
    """Rejection text. The stored count is included so an empty folder is explainable."""
    return f"Maximum {max_documents} documents allowed ({count} already stored). Please delete a document first."
