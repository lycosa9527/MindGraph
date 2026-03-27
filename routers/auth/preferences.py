"""
User language preferences (UI + prompt output) persisted on the User row.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.domain.auth import User
from models.requests.requests_auth import LanguagePreferencesUpdate
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


@router.patch("/language-preferences")
def update_language_preferences(
    body: LanguagePreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Persist interface language, prompt output language, and/or UI version
    for the signed-in user.
    """
    if (
        body.ui_language is None
        and body.prompt_language is None
        and body.ui_version is None
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one of ui_language, prompt_language, or ui_version",
        )

    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if body.ui_language is not None:
        user.ui_language = body.ui_language
    if body.prompt_language is not None:
        user.prompt_language = body.prompt_language
    if body.ui_version is not None:
        user.ui_version = body.ui_version

    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        logger.error(
            "Failed to save language preferences for user %s: %s",
            user.id,
            exc,
            exc_info=True,
        )
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save preferences",
        ) from exc

    user_cache.invalidate(user.id, user.phone)
    user_cache.cache_user(user)

    return {
        "ui_language": user.ui_language,
        "prompt_language": user.prompt_language,
        "ui_version": user.ui_version,
    }
