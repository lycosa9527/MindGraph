"""Community engagement counters under system RLS.

Post UPDATE policies require author/panel/system; authenticated likers and
commenters must bump counters outside the user session.
"""

from __future__ import annotations

from sqlalchemy import select, update

from models.domain.community import CommunityPost
from utils.db.rls_context import RlsContext, rls_async_session


async def adjust_post_likes_count(post_id: str, delta: int) -> int | None:
    """Adjust likes_count; returns new value or None if post missing."""
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(select(CommunityPost.likes_count).where(CommunityPost.id == post_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        new_count = max(0, int(row) + delta)
        await bump_db.execute(
            update(CommunityPost).where(CommunityPost.id == post_id).values(likes_count=new_count)
        )
        await bump_db.commit()
        return new_count


async def read_post_likes_count(post_id: str) -> int | None:
    """Read likes_count under system RLS."""
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(select(CommunityPost.likes_count).where(CommunityPost.id == post_id))
        ).scalar_one_or_none()
        return None if row is None else int(row)


async def adjust_post_comments_count(post_id: str, delta: int) -> int | None:
    """Adjust comments_count; returns new value or None if post missing."""
    async with rls_async_session(RlsContext.system_bootstrap()) as bump_db:
        row = (
            await bump_db.execute(select(CommunityPost.comments_count).where(CommunityPost.id == post_id))
        ).scalar_one_or_none()
        if row is None:
            return None
        new_count = max(0, int(row) + delta)
        await bump_db.execute(
            update(CommunityPost).where(CommunityPost.id == post_id).values(comments_count=new_count)
        )
        await bump_db.commit()
        return new_count
