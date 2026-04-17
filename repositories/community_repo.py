"""Community async repository."""

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.domain.auth import User
from models.domain.community import (
    CommunityPost,
    CommunityPostComment,
    CommunityPostLike,
)

from .base import BaseRepository


class CommunityPostRepository(BaseRepository[CommunityPost]):
    model = CommunityPost

    async def list_recent(
        self,
        *,
        before_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[CommunityPost]:
        """List recent community posts ordered by ``id DESC``.

        For high-traffic feeds prefer ``before_id`` (keyset cursor) over
        ``offset`` so deep pagination stays cheap (covered by the primary
        key index).  ``offset`` is kept for backwards compatibility.
        """
        stmt = (
            select(CommunityPost)
            .options(selectinload(CommunityPost.author).selectinload(User.organization))
            .order_by(CommunityPost.id.desc())
            .limit(limit)
        )
        if before_id is not None:
            stmt = stmt.where(CommunityPost.id < before_id)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_with_author(self, post_id: int) -> Optional[CommunityPost]:
        result = await self.session.execute(
            select(CommunityPost)
            .options(selectinload(CommunityPost.author).selectinload(User.organization))
            .where(CommunityPost.id == post_id)
        )
        return result.scalar_one_or_none()

    async def count_total(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(CommunityPost))
        return result.scalar_one()


class CommunityPostLikeRepository(BaseRepository[CommunityPostLike]):
    model = CommunityPostLike

    async def has_liked(self, post_id: int, user_id: int) -> bool:
        return await self.exists(
            CommunityPostLike.post_id == post_id,
            CommunityPostLike.user_id == user_id,
        )

    async def count_for_post(self, post_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(CommunityPostLike).where(CommunityPostLike.post_id == post_id)
        )
        return result.scalar_one()


class CommunityCommentRepository(BaseRepository[CommunityPostComment]):
    model = CommunityPostComment

    async def get_by_post(
        self,
        post_id: int,
        *,
        after_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[CommunityPostComment]:
        """Comments for a post in chronological order (``id ASC``).

        Use ``after_id`` (keyset cursor) for the next page; falls back to
        ``offset`` when no cursor is supplied for backwards compatibility.
        """
        stmt = (
            select(CommunityPostComment)
            .options(selectinload(CommunityPostComment.user))
            .where(CommunityPostComment.post_id == post_id)
            .order_by(CommunityPostComment.id.asc())
            .limit(limit)
        )
        if after_id is not None:
            stmt = stmt.where(CommunityPostComment.id > after_id)
        elif offset:
            stmt = stmt.offset(offset)
        result = await self.session.execute(stmt)
        return result.scalars().all()


def get_post_repo(session: AsyncSession) -> CommunityPostRepository:
    return CommunityPostRepository(session)


def get_like_repo(session: AsyncSession) -> CommunityPostLikeRepository:
    return CommunityPostLikeRepository(session)


def get_comment_repo(session: AsyncSession) -> CommunityCommentRepository:
    return CommunityCommentRepository(session)
