"""
Authentication Dependencies
===========================

FastAPI dependencies for authentication endpoints:
- Language detection dependency
- Admin access requirement dependency

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Optional
from fastapi import Depends, Header, HTTPException, Request, status

from models.messages import Messages, get_request_language, Language
from models.auth import User
from utils.auth import get_current_user, is_admin


def get_language_dependency(
    request: Request,
    x_language: Optional[str] = Header(None, alias="X-Language")
) -> Language:
    """
    FastAPI dependency to detect user language from request headers.
    
    Args:
        request: FastAPI Request object
        x_language: Optional X-Language header
    
    Returns:
        Language code ("en" or "zh")
    """
    accept_language = request.headers.get("Accept-Language", "")
    return get_request_language(x_language, accept_language)


def require_admin(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency)
) -> User:
    """
    FastAPI dependency to require admin access.
    
    Raises HTTPException 403 if user is not admin.
    
    Args:
        current_user: Current authenticated user (from get_current_user)
        lang: User language (from get_language_dependency)
    
    Returns:
        User object (guaranteed to be admin)
    
    Raises:
        HTTPException: 403 if user is not admin
    """
    if not is_admin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    return current_user

