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
from utils.auth import (
    can_access_workshop_chat,
    decode_access_token,
    get_current_user,
    is_admin_or_manager,
    is_school_admin,
    is_superadmin,
    user_has_feature_access,
)
from utils.auth.role_constants import (
    CAPABILITY_GLOBAL_DASHBOARD_READONLY,
    CAPABILITY_PERSONAL_TRIAL_INVITE,
    user_has_capability,
)


# Optional security scheme (auto_error=False means no 401 if missing)
security_optional = HTTPBearer(auto_error=False)


async def get_current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_optional),
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
        if not await session_manager.is_session_valid(int(user_id), token):
            logger.debug("[Auth] Session invalid for user %s in optional auth", user_id)
            return None

        # Get user from cache
        user = await user_cache.get_by_id(int(user_id))
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


def get_language_dependency(request: Request, x_language: Optional[str] = Header(None, alias="X-Language")) -> Language:
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


def require_superadmin(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    FastAPI dependency to require superadmin (full platform admin) access.

    Raises HTTPException 403 if user is not superadmin.
    """
    if not is_superadmin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def require_admin(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    FastAPI dependency to require admin access (alias for superadmin).

    Raises HTTPException 403 if user is not superadmin.
    """
    return require_superadmin(current_user, lang)


def require_school_admin(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    FastAPI dependency to require school admin access.

    Raises HTTPException 403 if user is not a school admin.
    Note: Superadmins are NOT school admins — use require_admin_or_manager for shared access.
    """
    if not is_school_admin(current_user):
        error_msg = Messages.error("manager_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def require_manager(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Alias for require_school_admin — legacy name preserved."""
    return require_school_admin(current_user, lang)


def require_admin_or_manager(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


async def require_mindbot_admin_access(
    current_user: User = Depends(require_admin_or_manager),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    MindBot admin UI/API: admin or manager, plus feature_org_access for MindBot.

    Managers are scoped to their ``users.organization_id`` in MindBot routes;
    when ``feature_access_rules`` restricts ``feature_mindbot``, the manager's
    organization (or user id) must appear in the corresponding grants.
    """
    if not await user_has_feature_access(current_user, "feature_mindbot"):
        error_msg = Messages.error("mindbot_feature_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


async def require_workshop_chat_access(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    Require access to Workshop Chat: global flag on, then DB rules or preview org list.

    See ``utils.auth.roles.user_has_feature_access`` / ``can_access_workshop_chat``.
    """
    if not await can_access_workshop_chat(current_user):
        error_msg = Messages.error("elevated_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def require_trial_invite_capability(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Scaffold: superadmin, platform_bd, or expert may invite personal trial users."""
    if not user_has_capability(current_user, CAPABILITY_PERSONAL_TRIAL_INVITE):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def require_global_dashboard_readonly(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Scaffold: superadmin or platform_bd may view read-only global dashboard."""
    if not user_has_capability(current_user, CAPABILITY_GLOBAL_DASHBOARD_READONLY):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user
