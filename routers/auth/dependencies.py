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
import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError

from models.domain.auth import User
from models.domain.messages import Messages, get_request_language, Language
from services.redis.session.redis_session_manager import get_session_manager
from services.redis.cache.redis_user_cache import user_cache
from utils.auth import decode_access_token, get_current_user, is_admin, is_admin_or_manager, is_manager



# Optional security scheme (auto_error=False means no 401 if missing)
security_optional = HTTPBearer(auto_error=False)


def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_optional)
) -> Optional[User]:
    """
    Get current user if authenticated, return None if not.

    This is for endpoints that work for both authenticated and anonymous users.
    Unlike get_current_user, this does NOT raise HTTPException if no token.

    Args:
        request: FastAPI Request object
        credentials: Optional Bearer token credentials

    Returns:
        User object if authenticated, None if not authenticated or token invalid
    """
    logger = logging.getLogger(__name__)

    # Try to get token from Authorization header or cookie
    token = None

    if credentials:
        token = credentials.credentials
    elif request:
        token = request.cookies.get("access_token")

    if not token:
        return None  # No authentication provided - that's OK for optional auth

    try:
        # Decode token
        payload = decode_access_token(token)
        user_id = payload.get("sub")

        if not user_id:
            return None

        # Check session validity
        session_manager = get_session_manager()
        if not session_manager.is_session_valid(int(user_id), token):
            logger.debug("[Auth] Session invalid for user %s in optional auth", user_id)
            return None

        # Get user from cache
        user = user_cache.get_by_id(int(user_id))
        return user

    except HTTPException:
        # Token validation failed
        return None
    except JWTError:
        # Token decode failed
        return None
    except Exception as e:
        logger.debug("[Auth] Optional auth failed: %s", e)
        return None


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


def require_manager(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency)
) -> User:
    """
    FastAPI dependency to require manager access.

    Raises HTTPException 403 if user is not a manager.
    Note: Admins are NOT managers - use require_admin_or_manager for shared access.

    Args:
        current_user: Current authenticated user (from get_current_user)
        lang: User language (from get_language_dependency)

    Returns:
        User object (guaranteed to be manager)

    Raises:
        HTTPException: 403 if user is not manager
    """
    if not is_manager(current_user):
        error_msg = Messages.error("manager_access_required", lang)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    return current_user


def require_admin_or_manager(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency)
) -> User:
    """
    FastAPI dependency to require admin OR manager access.

    Used for routes that both admin and manager can access.
    Admin sees all data, manager sees org-scoped data.

    Args:
        current_user: Current authenticated user (from get_current_user)
        lang: User language (from get_language_dependency)

    Returns:
        User object (guaranteed to be admin or manager)

    Raises:
        HTTPException: 403 if user is neither admin nor manager
    """
    if not is_admin_or_manager(current_user):
        error_msg = Messages.error("elevated_access_required", lang)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    return current_user
