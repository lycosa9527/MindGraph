"""Knowledge Space async repository."""

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.knowledge_space import (
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeSpace,
)

from .base import BaseRepository


class KnowledgeSpaceRepository(BaseRepository[KnowledgeSpace]):
    model = KnowledgeSpace

    async def get_by_user(self, user_id: int) -> Sequence[KnowledgeSpace]:
        result = await self.session.execute(
            select(KnowledgeSpace).where(KnowledgeSpace.user_id == user_id).order_by(KnowledgeSpace.created_at.desc())
        )
        return result.scalars().all()


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    model = KnowledgeDocument

    async def get_by_space(
        self,
        space_id: int,
        *,
        before_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[KnowledgeDocument]:
        """Documents in a space ordered by ``id DESC``.

        Prefer ``before_id`` keyset cursor over ``offset`` for deep pages.
        """
        conditions = [KnowledgeDocument.space_id == space_id]
        if before_id is not None:
            conditions.append(KnowledgeDocument.id < before_id)
        stmt = select(KnowledgeDocument).where(*conditions).order_by(KnowledgeDocument.id.desc()).limit(limit)
        if before_id is None and offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_chunks(self, document_id: int) -> Optional[KnowledgeDocument]:
        result = await self.session.execute(
            select(KnowledgeDocument)
            .options(selectinload(KnowledgeDocument.chunks))
            .where(KnowledgeDocument.id == document_id)
        )
        return result.scalar_one_or_none()

    async def count_by_space(self, space_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(KnowledgeDocument).where(KnowledgeDocument.space_id == space_id)
        )
        return result.scalar_one()


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def get_by_document(self, document_id: int) -> Sequence[DocumentChunk]:
        result = await self.session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == document_id).order_by(DocumentChunk.chunk_index)
        )
        return result.scalars().all()


def get_knowledge_space_repo(
    session: AsyncSession,
) -> KnowledgeSpaceRepository:
    return KnowledgeSpaceRepository(session)


def get_knowledge_doc_repo(
    session: AsyncSession,
) -> KnowledgeDocumentRepository:
    return KnowledgeDocumentRepository(session)


def get_chunk_repo(session: AsyncSession) -> DocumentChunkRepository:
    return DocumentChunkRepository(session)
