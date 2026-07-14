"""Showcase post deletion (likes cascade + row verification)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.showcase import ShowcasePost, ShowcasePostFavorite, ShowcasePostLike
from services.utils.typing_helpers import result_rowcount


async def delete_showcase_post_rows(db: AsyncSession, post_id: str) -> int:
    """Delete likes, favorites, then post; return number of post rows removed (0 or 1)."""
    await clear_showcase_post_engagement(db, post_id)
    result = await db.execute(delete(ShowcasePost).where(ShowcasePost.id == post_id))
    return result_rowcount(result)


async def clear_showcase_post_engagement(db: AsyncSession, post_id: str) -> None:
    """Remove likes and favorites for a post (delist / hard-delete prep)."""
    await db.execute(delete(ShowcasePostLike).where(ShowcasePostLike.post_id == post_id))
    await db.execute(delete(ShowcasePostFavorite).where(ShowcasePostFavorite.post_id == post_id))


async def showcase_post_still_exists(db: AsyncSession, post_id: str) -> bool:
    """Return True if a Showcase post row with the given id still exists."""
    row = (await db.execute(select(ShowcasePost.id).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    return row is not None
