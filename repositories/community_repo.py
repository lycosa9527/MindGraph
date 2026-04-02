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
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[CommunityPost]:
        stmt = (
            select(CommunityPost)
            .options(selectinload(CommunityPost.author).selectinload(User.organization))
            .order_by(CommunityPost.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
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
        offset: int = 0,
        limit: int = 50,
    ) -> Sequence[CommunityPostComment]:
        result = await self.session.execute(
            select(CommunityPostComment)
            .options(selectinload(CommunityPostComment.user))
            .where(CommunityPostComment.post_id == post_id)
            .order_by(CommunityPostComment.created_at)
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()


def get_post_repo(session: AsyncSession) -> CommunityPostRepository:
    return CommunityPostRepository(session)


def get_like_repo(session: AsyncSession) -> CommunityPostLikeRepository:
    return CommunityPostLikeRepository(session)


def get_comment_repo(session: AsyncSession) -> CommunityCommentRepository:
    return CommunityCommentRepository(session)
