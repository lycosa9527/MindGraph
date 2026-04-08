"""
User language preferences (UI + prompt output) persisted on the User row.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Messages, Language
from models.requests.requests_auth import LanguagePreferencesUpdate
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import get_current_user

from .dependencies import get_language_dependency

logger = logging.getLogger(__name__)

router = APIRouter()


@router.patch("/language-preferences")
async def update_language_preferences(
    body: LanguagePreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    lang: Language = Depends(get_language_dependency),
):
    """
    Persist interface language, prompt output language, and/or UI version
    for the signed-in user.
    """
    if body.ui_language is None and body.prompt_language is None and body.ui_version is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of ui_language, prompt_language, or ui_version",
        )

    result = await db.execute(select(User).where(User.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if body.ui_language is not None:
        if body.ui_language.lower() == "zh" and not getattr(user, "allows_simplified_chinese", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("ui_language_zh_not_allowed", lang),
            )
        user.ui_language = body.ui_language
    if body.prompt_language is not None:
        if body.prompt_language.lower() == "zh" and not getattr(user, "allows_simplified_chinese", True):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=Messages.error("prompt_language_zh_not_allowed", lang),
            )
        user.prompt_language = body.prompt_language
    if body.ui_version is not None:
        user.ui_version = body.ui_version

    try:
        await db.commit()
        await db.refresh(user)
    except Exception as exc:
        logger.error(
            "Failed to save language preferences for user %s: %s",
            user.id,
            exc,
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save preferences",
        ) from exc

    user_cache.invalidate(user.id, user.phone, getattr(user, "email", None))
    user_cache.cache_user(user)

    return {
        "ui_language": user.ui_language,
        "prompt_language": user.prompt_language,
        "ui_version": user.ui_version,
    }
