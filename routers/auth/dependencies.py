"""
Authentication Dependencies
===========================

FastAPI dependencies for authentication endpoints:
- Language detection dependency
- Admin access requirement dependency

Management panel access control (read this before adding admin routes)
-----------------------------------------------------------------------
Canonical capability map: ``utils.auth.admin_panel_permissions`` (backend)
and ``frontend/src/utils/adminCapabilities.ts`` (UI mirror — keep in sync).

When product says …                    Use on API routes …
-------------------                    ---------------------
"super-admin only"                     ``Depends(require_admin)`` for platform
                                       internals (settings, DB, API keys), OR
                                       ``Depends(require_panel_capability(CAP_*))``
                                       for panel tabs/subtabs (preferred — hides
                                       UI and API together via capability keys).
                                       Add the cap to ``_SUPERADMIN_CAPS`` only.

"school manager only"                  ``Depends(require_school_admin)`` (alias
                                       ``require_manager``). Rare alone — most
                                       school flows use capabilities instead.
                                       Add cap to ``_SCHOOL_ADMIN_CAPS`` only.

"super-admin OR school manager"        Prefer ``Depends(require_panel_capability(
                                       CAP_TAB_USERS_EDIT))`` (etc.) — returns
                                       ``AdminScope`` with org scope for managers.
                                       Legacy/shared routes without scope:
                                       ``Depends(require_admin_or_manager_with_rls)``.

"any management panel role"            ``Depends(require_management_panel)`` or
                                       ``Depends(get_admin_scope)`` (roles 1–4:
                                       superadmin, platform_bd, expert,
                                       school_admin).

"global platform read (BD / researcher)"  ``require_global_*`` helpers — capability
                                       plus ``scope.global`` (not school_admin).

"settings / 新功能开发 subtab"          ``require_panel_capability(CAP_SETTINGS_*)``.
                                       Today many subtabs still use ``require_admin``
                                       directly — equivalent for superadmin-only
                                       tabs but inconsistent with UI gating; migrate
                                       when touching those files.

"sensitive feature + FEATURE_* flag"   Thin wrapper like ``require_mindbot_admin_access``
                                       or ``require_mindmate_export_access``: superadmin
                                       gate + ``user_has_feature_access``.

RLS: declare auth deps **before** ``get_async_db`` / use
``get_async_db_with_request_rls`` with ``get_admin_scope``.

Long requests that do **not** use ``Depends(get_async_db)`` in the handler
(PG dump merge, admin log/realtime SSE, etc.) must use
``require_panel_capability_short_lived`` (or call ``release_open_transaction`` before
slow I/O when the handler still needs a session afterward).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, Query, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.messages import Language, Messages, get_request_language
from services.redis.cache.redis_user_cache import user_cache
from services.redis.session.redis_session_manager import get_session_manager
from services.utils.error_types import REDIS_ERRORS
from utils.auth import (
    can_access_workshop_chat,
    decode_access_token,
    get_current_user,
    is_admin_or_manager,
    is_school_admin,
    is_superadmin,
    user_has_feature_access,
)
from utils.auth.admin_panel_permissions import (
    CAP_SCOPE_GLOBAL,
    CAP_SCOPE_INVITED_ORGS,
    CAP_SETTINGS_DATABASE,
    CAP_SETTINGS_COS,
    CAP_SETTINGS_ERRORS,
    CAP_SETTINGS_FEATURES,
    CAP_SETTINGS_GEWE,
    CAP_SETTINGS_KITTY_LLMOPS,
    CAP_SETTINGS_LIBRARY,
    CAP_SETTINGS_PERFORMANCE,
    CAP_SETTINGS_ROLES,
    CAP_SETTINGS_SMART_RESPONSE,
    CAP_SETTINGS_TEACHER_USAGE,
    CAP_SETTINGS_THINKING_COINS,
    CAP_SETTINGS_TOKENS,
    CAP_TAB_BILLING_VIEW,
    CAP_TAB_DATA_CENTER_VIEW,
    CAP_TAB_INVITES_EDIT,
    CAP_TAB_ORGANIZATIONS_EDIT,
    CAP_TAB_ORGANIZATIONS_VIEW,
    CAP_TAB_SCHOOL_DASHBOARD_VIEW,
    CAP_TAB_SETTINGS_EDIT,
    CAP_TAB_SETTINGS_VIEW,
    CAP_TAB_USERS_EDIT,
    CAP_TAB_USERS_VIEW,
)
from utils.auth.admin_scope import AdminScope, build_admin_scope_async
from utils.auth.roles import is_management_panel_user
from utils.db.rls_context import RlsContext, apply_rls_context_async, set_rls_context
from utils.db.rls_request import bind_panel_superadmin_rls

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
    except REDIS_ERRORS as e:
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


# --- Role-based gates (coarse; use when capability keys do not apply) -------------


def require_superadmin(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    Super-admin only (平台超管). Binds panel superadmin RLS.

    Product "super-admin only" → this or ``require_admin`` (alias below).
    """
    if not is_superadmin(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    bind_panel_superadmin_rls(request, current_user)
    return current_user


def require_admin(
    request: Request,
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Alias for ``require_superadmin`` — same gate, shorter name in routers."""
    return require_superadmin(request, current_user, lang)


def require_school_admin(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    School manager only (学校管理员 / ``school_admin`` role).

    Superadmins are NOT school admins. For "super-admin OR school manager" use
    ``require_admin_or_manager`` / ``require_admin_or_manager_with_rls`` or a
    panel capability (preferred).
    """
    if not is_school_admin(current_user):
        error_msg = Messages.error("manager_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def require_manager(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Alias for ``require_school_admin`` — product term "school manager"."""
    return require_school_admin(current_user, lang)


def require_admin_or_manager(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    Super-admin OR school manager (no RLS bind).

    Prefer ``require_admin_or_manager_with_rls`` or ``get_admin_scope`` for new
    panel routes — they set org scope and capabilities correctly.
    """
    if not is_admin_or_manager(current_user):
        error_msg = Messages.error("elevated_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


async def require_admin_or_manager_with_rls(
    request: Request,
    current_user: User = Depends(require_admin_or_manager),
) -> User:
    """
    Super-admin OR school manager with RLS.

    Product "super-admin or school manager" on legacy routes (e.g. quick_register,
    workshop channels). New panel APIs should use ``require_panel_capability`` instead.
    """
    if is_superadmin(current_user):
        bind_panel_superadmin_rls(request, current_user)
    return current_user


async def require_mindbot_admin_access(
    current_user: User = Depends(require_admin),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    Template for superadmin-only + ``FEATURE_*`` gated panel features.

    Pair with ``CAP_SETTINGS_MINDBOT`` in ``admin_panel_permissions`` and UI.
    """
    if not await user_has_feature_access(current_user, "feature_mindbot"):
        error_msg = Messages.error("mindbot_feature_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


async def require_mindmate_export_access(
    current_user: User = Depends(require_admin),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """
    Superadmin-only MindMate export; see ``require_mindbot_admin_access`` template.

    UI cap: ``CAP_SETTINGS_MINDMATE_EXPORT`` (superadmin role only).
    """
    if not await user_has_feature_access(current_user, "feature_mindmate_export"):
        error_msg = Messages.error("elevated_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


async def get_async_db_with_request_rls(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> AsyncSession:
    """
    Apply ``request.state.rls_context`` on the open DB transaction.

    Auth dependencies (``require_admin``, ``require_mindbot_admin_access``,
    ``get_admin_scope``) bind panel scope on ``request.state``. Declare them
    **before** this dependency so ``get_async_db`` opens with the correct context;
    this call refreshes SET LOCAL when ``after_begin`` already ran with a stale context.
    """
    ctx = getattr(request.state, "rls_context", None)
    if ctx is not None:
        await apply_rls_context_async(db, ctx)
    return db


async def require_workshop_chat_access(
    request: Request,
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
    if is_superadmin(current_user):
        bind_panel_superadmin_rls(request, current_user)
    else:
        request.state.rls_context = RlsContext.from_user(
            current_user,
            allow_global_channels=True,
        )
    return current_user


def _assert_global_scope(scope: AdminScope, lang: Language) -> None:
    """Assert global scope."""
    if CAP_SCOPE_GLOBAL not in scope.capabilities:
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


# --- Capability-based gates (preferred for panel tabs; sync with Vue) ------------


def require_management_panel(
    current_user: User = Depends(get_current_user),
    lang: Language = Depends(get_language_dependency),
) -> User:
    """Any management panel role (superadmin, platform_bd, expert, school_admin)."""
    if not is_management_panel_user(current_user):
        error_msg = Messages.error("admin_access_required", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    return current_user


def _assert_invite_org_scope(scope: AdminScope, lang: Language) -> None:
    """Assert invite org scope."""
    if CAP_SCOPE_GLOBAL in scope.capabilities:
        return
    if CAP_SCOPE_INVITED_ORGS in scope.capabilities:
        return
    error_msg = Messages.error("admin_access_required", lang)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)


async def get_admin_scope(
    request: Request,
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_management_panel),
    lang: Language = Depends(get_language_dependency),
    db: AsyncSession = Depends(get_async_db_with_request_rls),
) -> AdminScope:
    """
    Base dependency for panel routes — resolves capabilities, org scope, and RLS.

    Stack ``require_panel_capability(CAP_*)`` on top for tab/subtab checks.
    """
    scope = await build_admin_scope_async(
        current_user,
        organization_id=organization_id,
        lang=lang,
    )
    ctx = RlsContext.from_admin_scope(scope)
    request.state.rls_context = ctx
    set_rls_context(ctx)
    await apply_rls_context_async(db, ctx)
    return scope


async def get_admin_scope_short_lived(
    request: Request,
    organization_id: Optional[int] = Query(None),
    current_user: User = Depends(require_management_panel),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """
    Resolve AdminScope without a request-scoped DB session.

    Use for handlers that run pg_dump/merge/import or other work that keeps the
    HTTP request open past ``idle_in_transaction_session_timeout`` while not
    using the FastAPI ``get_async_db`` session.
    """
    scope = await build_admin_scope_async(
        current_user,
        organization_id=organization_id,
        lang=lang,
    )
    ctx = RlsContext.from_admin_scope(scope)
    request.state.rls_context = ctx
    return scope


def require_panel_capability(capability: str):
    """
    Factory: require one capability key from ``admin_panel_permissions``.

    Primary tool for "who can see this tab/API". Example: school manager user
    CRUD → ``CAP_TAB_USERS_EDIT``; superadmin settings subtab → ``CAP_SETTINGS_*``.
    """

    def _dependency(
        scope: AdminScope = Depends(get_admin_scope),
        lang: Language = Depends(get_language_dependency),
    ) -> AdminScope:
        scope.assert_capability(capability, lang)
        return scope

    return _dependency


def require_panel_capability_short_lived(capability: str):
    """
    Like ``require_panel_capability`` but uses ``get_admin_scope_short_lived``.

    Auth-only gate for long-running routes that do not use ``Depends(get_async_db)``.
    """

    def _dependency(
        scope: AdminScope = Depends(get_admin_scope_short_lived),
        lang: Language = Depends(get_language_dependency),
    ) -> AdminScope:
        scope.assert_capability(capability, lang)
        return scope

    return _dependency


def require_global_users_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Global user list (superadmin read, teaching researcher read-only)."""
    _assert_global_scope(scope, lang)
    return scope


def require_global_users_edit(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_USERS_EDIT)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Require global users edit."""
    _assert_global_scope(scope, lang)
    return scope


def require_global_organizations_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_ORGANIZATIONS_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Require global organizations read."""
    _assert_global_scope(scope, lang)
    return scope


def require_global_organizations_edit(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_ORGANIZATIONS_EDIT)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Require global organizations edit."""
    _assert_global_scope(scope, lang)
    return scope


def require_global_billing_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_BILLING_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Require global billing read."""
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
    """
    Super-admin OR school manager dashboard (and platform_bd data-center view).

    Example of capability composition without a single cap key.
    """
    scope.assert_any_capability(
        frozenset({CAP_TAB_SCHOOL_DASHBOARD_VIEW, CAP_TAB_DATA_CENTER_VIEW}),
        lang,
    )
    return scope


def require_global_data_center_read(
    scope: AdminScope = Depends(require_panel_capability(CAP_TAB_DATA_CENTER_VIEW)),
    lang: Language = Depends(get_language_dependency),
) -> AdminScope:
    """Global platform stats: superadmin or teaching researcher (read-only)."""
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

require_settings_features = require_panel_capability(CAP_SETTINGS_FEATURES)
require_settings_roles = require_panel_capability(CAP_SETTINGS_ROLES)
require_settings_tokens = require_panel_capability(CAP_SETTINGS_TOKENS)
require_settings_library = require_panel_capability(CAP_SETTINGS_LIBRARY)
require_settings_database = require_panel_capability_short_lived(CAP_SETTINGS_DATABASE)
require_settings_cos = require_panel_capability_short_lived(CAP_SETTINGS_COS)
require_settings_performance = require_panel_capability_short_lived(CAP_SETTINGS_PERFORMANCE)
require_settings_errors = require_panel_capability(CAP_SETTINGS_ERRORS)
require_settings_thinking_coins = require_panel_capability(CAP_SETTINGS_THINKING_COINS)
require_settings_gewe = require_panel_capability(CAP_SETTINGS_GEWE)
require_settings_kitty_llmops = require_panel_capability(CAP_SETTINGS_KITTY_LLMOPS)
require_settings_teacher_usage = require_panel_capability(CAP_SETTINGS_TEACHER_USAGE)
require_settings_smart_response = require_panel_capability(CAP_SETTINGS_SMART_RESPONSE)
require_tab_settings_view = require_panel_capability(CAP_TAB_SETTINGS_VIEW)
require_tab_settings_edit = require_panel_capability(CAP_TAB_SETTINGS_EDIT)
