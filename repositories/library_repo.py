"""Library async repository."""

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.library import (
    LibraryBookmark,
    LibraryDanmaku,
    LibraryDocument,
)

from .base import BaseRepository


class LibraryDocumentRepository(BaseRepository[LibraryDocument]):
    model = LibraryDocument

    async def list_published(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[LibraryDocument]:
        result = await self.session.execute(
            select(LibraryDocument)
            .where(LibraryDocument.is_active.is_(True))
            .order_by(LibraryDocument.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def get_with_uploader(self, doc_id: int) -> Optional[LibraryDocument]:
        result = await self.session.execute(
            select(LibraryDocument).options(selectinload(LibraryDocument.uploader)).where(LibraryDocument.id == doc_id)
        )
        return result.scalar_one_or_none()


class LibraryDanmakuRepository(BaseRepository[LibraryDanmaku]):
    model = LibraryDanmaku

    async def get_by_document(
        self,
        document_id: int,
        *,
        page: Optional[int] = None,
    ) -> Sequence[LibraryDanmaku]:
        stmt = (
            select(LibraryDanmaku)
            .options(selectinload(LibraryDanmaku.user))
            .where(LibraryDanmaku.document_id == document_id)
        )
        if page is not None:
            stmt = stmt.where(LibraryDanmaku.page_number == page)
        stmt = stmt.order_by(LibraryDanmaku.created_at)
        result = await self.session.execute(stmt)
        return result.scalars().all()


class LibraryBookmarkRepository(BaseRepository[LibraryBookmark]):
    model = LibraryBookmark

    async def get_user_bookmarks(
        self,
        user_id: int,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[LibraryBookmark]:
        result = await self.session.execute(
            select(LibraryBookmark)
            .options(selectinload(LibraryBookmark.document))
            .where(LibraryBookmark.user_id == user_id)
            .order_by(LibraryBookmark.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def has_bookmark(self, user_id: int, document_id: int) -> bool:
        return await self.exists(
            LibraryBookmark.user_id == user_id,
            LibraryBookmark.document_id == document_id,
        )

    async def count_for_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(LibraryBookmark).where(LibraryBookmark.user_id == user_id)
        )
        return result.scalar_one()


def get_library_doc_repo(
    session: AsyncSession,
) -> LibraryDocumentRepository:
    return LibraryDocumentRepository(session)


def get_danmaku_repo(session: AsyncSession) -> LibraryDanmakuRepository:
    return LibraryDanmakuRepository(session)


def get_bookmark_repo(session: AsyncSession) -> LibraryBookmarkRepository:
    return LibraryBookmarkRepository(session)
