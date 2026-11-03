"""Lightweight resolver for a diagram's package-scoped RAG document IDs.

Kept dependency-free (models + db only) so the diagram generation workflow can
import it without pulling the heavy ``KnowledgeSpaceService`` import chain.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.diagrams import Diagram
from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument

PERSONAL_KNOWLEDGE_SOURCES = ("knowledge_space", "canvas", "chrome_extension")


@dataclass
class PackageRagScope:
    """Resolved RAG scope for a diagram's linked package."""

    package_id: int
    source: str = ""
    document_ids: List[int] = field(default_factory=list)
    open_count: int = 0

    @property
    def has_corpus(self) -> bool:
        """True when at least one completed source is available for retrieval."""
        return bool(self.document_ids)

    @property
    def is_fully_ready(self) -> bool:
        """True when every file in the folder has finished successfully."""
        return self.has_corpus and self.open_count == 0


def personal_package_id_for_scope(scope: Optional[PackageRagScope]) -> Optional[int]:
    """Folder id for personal-knowledge generation, or None when it must stay off.

    An empty folder, a folder still processing, or a folder with a failed file
    does not change the prompt.
    """
    if scope is None or scope.source not in PERSONAL_KNOWLEDGE_SOURCES or not scope.is_fully_ready:
        return None
    return scope.package_id


async def resolve_diagram_rag_scope(
    db: AsyncSession,
    user_id: int,
    diagram_id: str,
) -> Optional[PackageRagScope]:
    """Resolve completed document IDs scoping RAG for an owned diagram.

    Returns ``None`` when the diagram has no linked package (the caller then
    decides whether to fall back to whole-library retrieval).
    """
    result = await db.execute(
        select(Diagram.knowledge_package_id).where(
            and_(
                Diagram.id == diagram_id,
                Diagram.user_id == user_id,
                Diagram.is_deleted.is_(False),
            )
        )
    )
    package_id = result.scalar_one_or_none()
    if not package_id:
        batch_result = await db.execute(
            select(DocumentBatch.id)
            .where(
                and_(
                    DocumentBatch.diagram_id == diagram_id,
                    DocumentBatch.user_id == user_id,
                )
            )
            .order_by(DocumentBatch.updated_at.desc())
            .limit(1)
        )
        package_id = batch_result.scalar_one_or_none()
    if not package_id:
        return None

    return await _scope_for_package(db, package_id)


async def _scope_for_package(db: AsyncSession, package_id: int) -> PackageRagScope:
    batch = await db.get(DocumentBatch, package_id)
    source = batch.source if batch and batch.source else ""
    doc_result = await db.execute(
        select(KnowledgeDocument.id).where(
            and_(
                KnowledgeDocument.batch_id == package_id,
                KnowledgeDocument.status == "completed",
            )
        )
    )
    document_ids = list(doc_result.scalars().all())
    open_result = await db.execute(
        select(func.count())
        .select_from(KnowledgeDocument)
        .where(
            and_(
                KnowledgeDocument.batch_id == package_id,
                KnowledgeDocument.status != "completed",
            )
        )
    )
    open_count = int(open_result.scalar_one_or_none() or 0)
    return PackageRagScope(
        package_id=package_id,
        source=source,
        document_ids=document_ids,
        open_count=open_count,
    )


async def resolve_package_rag_scope_by_id(
    db: AsyncSession,
    user_id: int,
    package_id: int,
) -> Optional[PackageRagScope]:
    """Resolve completed document IDs for an owned package (by id)."""
    batch_result = await db.execute(
        select(DocumentBatch.id).where(
            and_(
                DocumentBatch.id == package_id,
                DocumentBatch.user_id == user_id,
            )
        )
    )
    if batch_result.scalar_one_or_none() is None:
        return None
    return await _scope_for_package(db, package_id)
