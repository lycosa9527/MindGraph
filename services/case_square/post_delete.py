"""Case Square post deletion (likes cascade + row verification)."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.case_square import CaseSquarePost, CaseSquarePostFavorite, CaseSquarePostLike
from services.utils.typing_helpers import result_rowcount


async def delete_case_square_post_rows(db: AsyncSession, post_id: str) -> int:
    """Delete likes, favorites, then post; return number of post rows removed (0 or 1)."""
    await db.execute(delete(CaseSquarePostLike).where(CaseSquarePostLike.post_id == post_id))
    await db.execute(delete(CaseSquarePostFavorite).where(CaseSquarePostFavorite.post_id == post_id))
    result = await db.execute(delete(CaseSquarePost).where(CaseSquarePost.id == post_id))
    return result_rowcount(result)


async def case_square_post_still_exists(db: AsyncSession, post_id: str) -> bool:
    row = (await db.execute(select(CaseSquarePost.id).where(CaseSquarePost.id == post_id))).scalar_one_or_none()
    return row is not None
