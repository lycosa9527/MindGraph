"""Library Router Helpers.

Helper functions and dependencies for library API endpoints.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from models.domain.auth import User
from utils.auth import get_current_user
from utils.auth.roles import is_admin
from utils.auth.tokens import security


def serialize_document(document) -> dict:
    """
    Serialize LibraryDocument to response dict.

    Reduces code duplication across endpoints.
    """
    return {
        "id": document.id,
        "title": document.title,
        "description": document.description,
        "cover_image_path": document.cover_image_path,
        "use_images": document.use_images or False,
        "pages_dir_path": document.pages_dir_path,
        "total_pages": document.total_pages,
        "views_count": document.views_count,
        "likes_count": document.likes_count,
        "comments_count": document.comments_count,
        "created_at": document.created_at.isoformat() if document.created_at else "",
        "uploader": {
            "id": document.uploader_id,
            "name": document.uploader.name if document.uploader else None,
        }
    }


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin access."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    Allows public access to certain endpoints.
    """
    # If no credentials provided, user is not authenticated
    if not credentials and not request.cookies.get("access_token"):
        return None

    try:
        return get_current_user(request, credentials)
    except HTTPException:
        # Authentication failed - return None for public access
        return None
