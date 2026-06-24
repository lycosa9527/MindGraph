"""Lightweight resolver for a diagram's package-scoped RAG document IDs.

Kept dependency-free (models + db only) so the diagram generation workflow can
import it without pulling the heavy ``KnowledgeSpaceService`` import chain.
"""

from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.diagrams import Diagram
from models.domain.knowledge_space import KnowledgeDocument


@dataclass
class PackageRagScope:
    """Resolved RAG scope for a diagram's linked package."""

    package_id: int
    document_ids: List[int] = field(default_factory=list)

    @property
    def has_corpus(self) -> bool:
        """True when at least one completed source is available for retrieval."""
        return bool(self.document_ids)


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
        return None

    doc_result = await db.execute(
        select(KnowledgeDocument.id).where(
            and_(
                KnowledgeDocument.batch_id == package_id,
                KnowledgeDocument.status == "completed",
            )
        )
    )
    document_ids = list(doc_result.scalars().all())
    return PackageRagScope(package_id=package_id, document_ids=document_ids)
