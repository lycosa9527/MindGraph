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

from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
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
from utils.auth.admin_scope import AdminScope, build_admin_scope, build_admin_scope_async
from utils.auth.admin_panel_permissions import (
    CAP_SCOPE_GLOBAL,
    CAP_SCOPE_INVITED_ORGS,
    CAP_TAB_BILLING_VIEW,
    CAP_TAB_DATA_CENTER_VIEW,
    CAP_TAB_INVITES_EDIT,
    CAP_TAB_ORGANIZATIONS_EDIT,
    CAP_TAB_ORGANIZATIONS_VIEW,
    CAP_TAB_SCHOOL_DASHBOARD_VIEW,
    CAP_TAB_USERS_EDIT,
    CAP_TAB_USERS_VIEW,
)
from utils.auth.roles import is_management_panel_user


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
    current_user: User = Depends(require_admin),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    MindBot admin UI/API: superadmin only, plus feature_org_access for MindBot.
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
    """Superadmin, operations (platform_bd), or expert may invite personal trial users."""
    scope = build_admin_scope(current_user, lang=lang)
    scope.assert_capability(CAP_TAB_INVITES_EDIT, lang)
    return current_user


def _assert_global_scope(scope: AdminScope, lang: Language) -> None:
    if CAP_SCOPE_GLOBAL not in scope.capabilities:
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


def require_management_panel(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Require access to the unified management panel (roles 1–4)."""
    if not is_management_panel_user(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def _assert_invite_org_scope(scope: AdminScope, lang: Language) -> None:
    if CAP_SCOPE_GLOBAL in scope.capabilities:
        return
    if CAP_SCOPE_INVITED_ORGS in scope.capabilities:
        return
    error_msg = Messages.error("admin_access_required", lang)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


async def get_admin_scope(
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_management_panel),
    lang: Language = Depends(get_language_dependency),
    db: AsyncSession = Depends(get_async_db),
) -> AdminScope:
    """Resolve AdminScope for management panel API handlers."""
    return await build_admin_scope_async(
        current_user,
        db,
        organization_id=organization_id,
        lang=lang,
    )


def require_panel_capability(capability: str):
    """Factory: dependency requiring a specific panel capability."""

    def _dependency(
        scope: AdminScope = Depends(get_admin_scope),
        lang: Language = Depends(get_language_dependency),
    ) -> AdminScope:
        scope.assert_capability(capability, lang)
        return scope

    return _dependency


def require_global_users_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Global user list (superadmin read, operations read-only)."""
    _assert_global_scope(scope, lang)
    return scope


def require_global_users_edit(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    _assert_global_scope(scope, lang)
    return scope


def require_global_organizations_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_ORGANIZATIONS_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    _assert_global_scope(scope, lang)
    return scope


def require_global_organizations_edit(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_ORGANIZATIONS_EDIT)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    _assert_global_scope(scope, lang)
    return scope


def require_global_billing_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_BILLING_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    _assert_global_scope(scope, lang)
    return scope


def require_invite_org_create(
    scope: AdminScope = Depends(get_admin_scope),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Create organization via invite tab (global or expert invited-org scope)."""
    scope.assert_any_capability(
        frozenset({CAP_TAB_INVITES_EDIT, CAP_TAB_ORGANIZATIONS_EDIT}),
        lang,
    )
    _assert_invite_org_scope(scope, lang)
    return scope


def require_school_dashboard_read(
    scope: AdminScope = Depends(get_admin_scope),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """School dashboard stats: school_admin or global data-center roles."""
    scope.assert_any_capability(
        frozenset({CAP_TAB_SCHOOL_DASHBOARD_VIEW, CAP_TAB_DATA_CENTER_VIEW}),
        lang,
    )
    return scope


def require_global_data_center_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_DATA_CENTER_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Global platform stats: superadmin or operations (read-only)."""
    if CAP_SCOPE_GLOBAL not in scope.capabilities:
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return scope


def require_admin_stats_read(
    scope: AdminScope = Depends(require_global_data_center_read),
) -> AdminScope:
    """Deprecated alias — use require_global_data_center_read."""
    return scope


require_global_dashboard_readonly = require_global_data_center_read
