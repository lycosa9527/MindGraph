"""Showcase routes: withdraw, delist, delete, engagement, and review."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import count as sa_count

from config.database import get_async_db
from models.domain.auth import User
from models.domain.showcase import ShowcasePost, ShowcasePostFavorite, ShowcasePostLike
from routers.features.showcase_common import (
    CaseReviewBody,
    _adjust_approved_post_likes_count,
    _format_post,
    _load_post_for_format,
    _read_approved_post_likes_count,
    _review_case_post_handler,
    _validate_post_id,
)
from routers.features.showcase_permissions import (
    can_expert_recommend,
    can_review_case,
)
from services.utils.error_types import DATABASE_ERRORS
from utils.auth import get_current_user
from utils.db.rls_context import RlsContext, apply_rls_context_async

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle like on an approved case and return updated count."""
    _validate_post_id(post_id)
    approved = (
        await db.execute(
            select(ShowcasePost.id).where(
                ShowcasePost.id == post_id,
                ShowcasePost.status == "approved",
            )
        )
    ).scalar_one_or_none()
    if not approved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    existing = (
        await db.execute(
            select(ShowcasePostLike).where(
                ShowcasePostLike.post_id == post_id,
                ShowcasePostLike.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    liked = False
    delta = 0
    if existing:
        await db.delete(existing)
        liked = False
        delta = -1
    else:
        db.add(ShowcasePostLike(post_id=post_id, user_id=current_user.id))
        liked = True
        delta = 1

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        liked = True
        delta = 0

    if delta != 0:
        likes_count = await _adjust_approved_post_likes_count(post_id, delta)
    else:
        likes_count = await _read_approved_post_likes_count(post_id)

    if likes_count is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    return {"liked": liked, "likes_count": likes_count}


@router.post("/posts/{post_id}/favorite")
async def toggle_favorite(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle favorite on an approved case."""
    _validate_post_id(post_id)
    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post or post.status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    existing = (
        await db.execute(
            select(ShowcasePostFavorite).where(
                ShowcasePostFavorite.post_id == post_id,
                ShowcasePostFavorite.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        favorited = False
    else:
        db.add(ShowcasePostFavorite(post_id=post_id, user_id=current_user.id))
        favorited = True

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        favorited = True
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.exception("[Showcase] Failed to toggle favorite for post %s", post_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update favorite",
        ) from exc

    return {"favorited": favorited}


@router.post("/posts/{post_id}/recommend")
async def toggle_expert_recommend(
    post_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Toggle expert-recommended flag on an approved case."""
    _validate_post_id(post_id)
    if not await can_expert_recommend(db, current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot recommend cases")

    post = (await db.execute(select(ShowcasePost).where(ShowcasePost.id == post_id))).scalar_one_or_none()
    if not post or post.status != "approved":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    now = datetime.now(UTC)
    panel_ctx = RlsContext.panel_superadmin(current_user)
    await apply_rls_context_async(db, panel_ctx)

    if post.is_expert_recommended:
        post.is_expert_recommended = False
        post.expert_recommended_by = None
        post.expert_recommended_at = None
    else:
        post.is_expert_recommended = True
        post.expert_recommended_by = current_user.id
        post.expert_recommended_at = now

    try:
        await db.commit()
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Showcase] Expert recommend toggle failed for %s: %s", post_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update recommendation",
        ) from exc

    with db.no_autoflush:
        refreshed = await _load_post_for_format(db, post_id)
        payload_post = await _format_post(refreshed, current_user, db)
    return {
        "is_expert_recommended": refreshed.is_expert_recommended,
        "post": payload_post,
    }


@router.post("/posts/{post_id}/review")
async def review_post(
    post_id: str,
    body: CaseReviewBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Approve or reject a pending case (reviewer endpoint)."""
    return await _review_case_post_handler(post_id, body, current_user, db)


@router.get("/pending/count")
async def pending_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return pending and rejected case counts for reviewers."""
    if not await can_review_case(db, current_user):
        return {"count": 0, "pending": 0, "rejected": 0}
    pending = (
        await db.execute(select(sa_count()).select_from(ShowcasePost).where(ShowcasePost.status == "pending"))
    ).scalar_one()
    rejected = (
        await db.execute(select(sa_count()).select_from(ShowcasePost).where(ShowcasePost.status == "rejected"))
    ).scalar_one()
    return {"count": pending, "pending": pending, "rejected": rejected}
