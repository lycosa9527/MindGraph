"""
Management panel capability keys and role → capability mapping.

Single config source for tab visibility and admin API access scaffolding.
Tune role tab sets here without changing Vue or router components.

Adding a new panel feature (checklist)
--------------------------------------
1. Define ``CAP_*`` constant below (e.g. ``CAP_SETTINGS_FOO``).
2. Add to the right role frozenset:
   - superadmin-only → ``_SUPERADMIN_CAPS`` / ``_ALL_SETTINGS_CAPS``
   - school manager too → also ``_SCHOOL_ADMIN_CAPS``
   - platform BD read-only → ``_PLATFORM_BD_CAPS`` (rare for settings)
3. Mirror the cap in ``frontend/src/utils/adminCapabilities.ts``.
4. Protect API routes with ``require_panel_capability(CAP_*)`` from
   ``routers.auth.dependencies`` (not raw ``is_superadmin()``).
5. Optional ``FEATURE_*`` env flag → add thin dep like ``require_mindbot_admin_access``.

Product term → role slug: super-admin = ``superadmin``; school manager = ``school_admin``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from typing import Final

from utils.auth.env_superadmin import is_env_configured_superadmin
from utils.auth.role_constants import (
    ALL_USER_ROLES,
    ROLE_EXPERT,
    ROLE_PERSONAL_PAID,
    ROLE_PERSONAL_TRIAL,
    ROLE_PLATFORM_BD,
    ROLE_SCHOOL_ADMIN,
    ROLE_SUPERADMIN,
    ROLE_TEACHER,
    SUPERADMIN_ROLES,
    normalize_role,
    role_in,
)

CAP_PANEL_ACCESS: Final[str] = "panel.access"

CAP_TAB_DATA_CENTER_VIEW: Final[str] = "tab.data_center.view"
CAP_TAB_DATA_CENTER_EDIT: Final[str] = "tab.data_center.edit"
CAP_TAB_SCHOOL_DASHBOARD_VIEW: Final[str] = "tab.school_dashboard.view"
CAP_TAB_USERS_VIEW: Final[str] = "tab.users.view"
CAP_TAB_USERS_EDIT: Final[str] = "tab.users.edit"
CAP_TAB_ORGANIZATIONS_VIEW: Final[str] = "tab.organizations.view"
CAP_TAB_ORGANIZATIONS_EDIT: Final[str] = "tab.organizations.edit"
CAP_TAB_INVITES_VIEW: Final[str] = "tab.invites.view"
CAP_TAB_INVITES_EDIT: Final[str] = "tab.invites.edit"
CAP_TAB_BILLING_VIEW: Final[str] = "tab.billing.view"
CAP_TAB_BILLING_EDIT: Final[str] = "tab.billing.edit"
CAP_TAB_SETTINGS_VIEW: Final[str] = "tab.settings.view"
CAP_TAB_SETTINGS_EDIT: Final[str] = "tab.settings.edit"

CAP_SETTINGS_FEATURES: Final[str] = "tab.settings.features"
CAP_SETTINGS_ROLES: Final[str] = "tab.settings.roles"
CAP_SETTINGS_TOKENS: Final[str] = "tab.settings.tokens"
CAP_SETTINGS_LIBRARY: Final[str] = "tab.settings.library"
CAP_SETTINGS_DATABASE: Final[str] = "tab.settings.database"
CAP_SETTINGS_COS: Final[str] = "tab.settings.cos"
CAP_SETTINGS_PERFORMANCE: Final[str] = "tab.settings.performance"
CAP_SETTINGS_GEWE: Final[str] = "tab.settings.gewe"
CAP_SETTINGS_KITTY_LLMOPS: Final[str] = "tab.settings.kitty_llmops"
CAP_SETTINGS_MINDBOT: Final[str] = "tab.settings.mindbot"
CAP_SETTINGS_MINDMATE_EXPORT: Final[str] = "tab.settings.mindmate_export"
CAP_SETTINGS_SMART_RESPONSE: Final[str] = "tab.settings.smart_response"
CAP_SETTINGS_TEACHER_USAGE: Final[str] = "tab.settings.teacher_usage"
CAP_SETTINGS_ERRORS: Final[str] = "tab.settings.errors"
CAP_SETTINGS_THINKING_COINS: Final[str] = "tab.settings.thinking_coins"

CAP_SCOPE_GLOBAL: Final[str] = "scope.global"
CAP_SCOPE_ORG: Final[str] = "scope.org"
CAP_SCOPE_INVITED_ORGS: Final[str] = "scope.invited_orgs"

_ALL_SETTINGS_CAPS: frozenset[str] = frozenset(
    {
        CAP_TAB_SETTINGS_VIEW,
        CAP_TAB_SETTINGS_EDIT,
        CAP_SETTINGS_FEATURES,
        CAP_SETTINGS_ROLES,
        CAP_SETTINGS_TOKENS,
        CAP_SETTINGS_LIBRARY,
        CAP_SETTINGS_DATABASE,
        CAP_SETTINGS_COS,
        CAP_SETTINGS_PERFORMANCE,
        CAP_SETTINGS_GEWE,
        CAP_SETTINGS_KITTY_LLMOPS,
        CAP_SETTINGS_MINDBOT,
        CAP_SETTINGS_MINDMATE_EXPORT,
        CAP_SETTINGS_SMART_RESPONSE,
        CAP_SETTINGS_TEACHER_USAGE,
        CAP_SETTINGS_ERRORS,
        CAP_SETTINGS_THINKING_COINS,
    }
)

_SUPERADMIN_CAPS: frozenset[str] = (
    # Platform super-admin: all panel tabs + every settings / 新功能开发 subtab.
    frozenset(
        {
            CAP_PANEL_ACCESS,
            CAP_TAB_DATA_CENTER_VIEW,
            CAP_TAB_DATA_CENTER_EDIT,
            CAP_TAB_SCHOOL_DASHBOARD_VIEW,
            CAP_TAB_USERS_VIEW,
            CAP_TAB_USERS_EDIT,
            CAP_TAB_ORGANIZATIONS_VIEW,
            CAP_TAB_ORGANIZATIONS_EDIT,
            CAP_TAB_INVITES_VIEW,
            CAP_TAB_INVITES_EDIT,
            CAP_TAB_BILLING_VIEW,
            CAP_TAB_BILLING_EDIT,
            CAP_SCOPE_GLOBAL,
        }
    )
    | _ALL_SETTINGS_CAPS
)

_PLATFORM_BD_CAPS: frozenset[str] = frozenset(
    {
        CAP_PANEL_ACCESS,
        CAP_TAB_DATA_CENTER_VIEW,
        CAP_TAB_DATA_CENTER_EDIT,
        CAP_TAB_SCHOOL_DASHBOARD_VIEW,
        CAP_TAB_USERS_VIEW,
        CAP_TAB_ORGANIZATIONS_VIEW,
        CAP_TAB_INVITES_VIEW,
        CAP_TAB_INVITES_EDIT,
        CAP_TAB_BILLING_VIEW,
        CAP_SCOPE_GLOBAL,
        CAP_SCOPE_INVITED_ORGS,
    }
)

_EXPERT_CAPS: frozenset[str] = frozenset(
    {
        CAP_PANEL_ACCESS,
        # Org management is invite-scoped (created schools only); no global edit.
        CAP_TAB_ORGANIZATIONS_VIEW,
        CAP_TAB_INVITES_VIEW,
        CAP_TAB_INVITES_EDIT,
        CAP_SCOPE_INVITED_ORGS,
    }
)

_SCHOOL_ADMIN_CAPS: frozenset[str] = frozenset(
    {
        # School manager (学校管理员): org-scoped dashboard + member management only.
        CAP_PANEL_ACCESS,
        CAP_TAB_SCHOOL_DASHBOARD_VIEW,
        CAP_TAB_USERS_VIEW,
        CAP_TAB_USERS_EDIT,
        CAP_SCOPE_ORG,
    }
)

ROLE_PANEL_CAPABILITIES: dict[str, frozenset[str]] = {
    ROLE_SUPERADMIN: _SUPERADMIN_CAPS,
    ROLE_PLATFORM_BD: _PLATFORM_BD_CAPS,
    ROLE_EXPERT: _EXPERT_CAPS,
    ROLE_SCHOOL_ADMIN: _SCHOOL_ADMIN_CAPS,
    ROLE_TEACHER: frozenset(),
    ROLE_PERSONAL_TRIAL: frozenset(),
    ROLE_PERSONAL_PAID: frozenset(),
}


def capabilities_for_role(role: str | None) -> frozenset[str]:
    """Return panel capabilities for a canonical or legacy role slug."""
    canonical = normalize_role(role)
    return ROLE_PANEL_CAPABILITIES.get(canonical, frozenset())


def _has_superadmin_panel_access(current_user) -> bool:
    """DB superadmin role or env-configured superadmin (ADMIN_PHONES / ADMIN_USER_IDS)."""
    return role_in(current_user, SUPERADMIN_ROLES) or is_env_configured_superadmin(current_user)


def user_panel_capabilities(current_user) -> frozenset[str]:
    """Capabilities granted to the user for the management panel."""
    if not hasattr(current_user, "role"):
        return frozenset()
    if _has_superadmin_panel_access(current_user):
        return ROLE_PANEL_CAPABILITIES[ROLE_SUPERADMIN]
    return capabilities_for_role(current_user.role)


def role_has_panel_access(role: str | None) -> bool:
    """True when the role may open the management panel."""
    caps = capabilities_for_role(role)
    return CAP_PANEL_ACCESS in caps


def is_management_panel_user(current_user) -> bool:
    """True when user may access the unified management panel (roles 1–4)."""
    if not hasattr(current_user, "role"):
        return False
    if _has_superadmin_panel_access(current_user):
        return True
    return role_has_panel_access(current_user.role)


def all_panel_capability_keys() -> frozenset[str]:
    """Union of every capability key used in panel config."""
    merged: set[str] = set()
    for caps in ROLE_PANEL_CAPABILITIES.values():
        merged.update(caps)
    return frozenset(merged)


def validate_role_panel_config() -> None:
    """Ensure every canonical role has an explicit capability entry."""
    for role in ALL_USER_ROLES:
        if role not in ROLE_PANEL_CAPABILITIES:
            raise ValueError(f"missing ROLE_PANEL_CAPABILITIES entry for {role}")
