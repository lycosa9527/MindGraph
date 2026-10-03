"""
POST /api/auth/avatar/image — crop result stored on COS.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from services.auth.user_avatar_image import (
    AVATAR_MAX_UPLOAD_BYTES,
    AvatarImageError,
    avatar_photos_enabled,
    publish_user_avatar_png,
    release_replaced_avatar,
)
from services.redis.cache.redis_user_cache import user_cache
from services.utils.error_types import DATABASE_ERRORS, REDIS_ERRORS
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_STATUS = {
    "empty": status.HTTP_400_BAD_REQUEST,
    "invalid": status.HTTP_400_BAD_REQUEST,
    "too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "unavailable": status.HTTP_503_SERVICE_UNAVAILABLE,
}


@router.post("/avatar/image")
async def upload_user_avatar_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Replace the signed-in user's avatar with a public COS image URL."""
    if not avatar_photos_enabled():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="unavailable")
    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        raw = await file.read(AVATAR_MAX_UPLOAD_BYTES + 1)
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid") from exc

    try:
        url = await asyncio.to_thread(publish_user_avatar_png, user.id, raw)
    except AvatarImageError as exc:
        code = _STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=code, detail=exc.code) from exc

    previous_avatar = user.avatar
    user.avatar = url
    try:
        await db.commit()
        await db.refresh(user)
        await user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
        await user_cache.cache_user(user)
        logger.info("User %s updated photo avatar", user.id)
    except REDIS_ERRORS as exc:
        await db.rollback()
        logger.error("Failed to cache photo avatar for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update avatar",
        ) from exc
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("Failed to store photo avatar for user %s: %s", current_user.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update avatar",
        ) from exc

    await asyncio.to_thread(release_replaced_avatar, previous_avatar, user.avatar)
    return {"avatar": user.avatar}
