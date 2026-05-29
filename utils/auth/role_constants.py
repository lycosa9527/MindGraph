"""
User role constants and capability scaffolding for MindGraph.

Seven canonical account roles across platform (B2B ops), school org (B2B),
and personal consumer (B2C) tiers. Detailed enforcement of invite codes,
AI quotas, and tiered entitlements is deferred to later phases.
"""

from typing import Final

# Canonical DB role slugs
ROLE_SUPERADMIN: Final[str] = "superadmin"
ROLE_PLATFORM_BD: Final[str] = "platform_bd"
ROLE_EXPERT: Final[str] = "expert"
ROLE_SCHOOL_ADMIN: Final[str] = "school_admin"
ROLE_TEACHER: Final[str] = "teacher"
ROLE_PERSONAL_TRIAL: Final[str] = "personal_trial"
ROLE_PERSONAL_PAID: Final[str] = "personal_paid"

# Legacy role slugs (pre-migration fallback)
LEGACY_ROLE_ADMIN: Final[str] = "admin"
LEGACY_ROLE_MANAGER: Final[str] = "manager"
LEGACY_ROLE_USER: Final[str] = "user"

ALL_USER_ROLES: frozenset[str] = frozenset(
    {
        ROLE_SUPERADMIN,
        ROLE_PLATFORM_BD,
        ROLE_EXPERT,
        ROLE_SCHOOL_ADMIN,
        ROLE_TEACHER,
        ROLE_PERSONAL_TRIAL,
        ROLE_PERSONAL_PAID,
    }
)

VALID_ASSIGNABLE_ROLES: frozenset[str] = ALL_USER_ROLES

PLATFORM_LEVEL_ROLES: frozenset[str] = frozenset(
    {ROLE_SUPERADMIN, ROLE_PLATFORM_BD, ROLE_EXPERT}
)

B2B_ORG_ROLES: frozenset[str] = frozenset({ROLE_SCHOOL_ADMIN, ROLE_TEACHER})

C2C_CONSUMER_ROLES: frozenset[str] = frozenset({ROLE_PERSONAL_TRIAL, ROLE_PERSONAL_PAID})

LEGACY_TO_CANONICAL: dict[str, str] = {
    LEGACY_ROLE_ADMIN: ROLE_SUPERADMIN,
    LEGACY_ROLE_MANAGER: ROLE_SCHOOL_ADMIN,
    LEGACY_ROLE_USER: ROLE_TEACHER,
}

SUPERADMIN_ROLES: frozenset[str] = frozenset({ROLE_SUPERADMIN, LEGACY_ROLE_ADMIN})

SCHOOL_ADMIN_ROLES: frozenset[str] = frozenset({ROLE_SCHOOL_ADMIN, LEGACY_ROLE_MANAGER})

TEACHER_ROLES: frozenset[str] = frozenset({ROLE_TEACHER, LEGACY_ROLE_USER})

# Capability keys — scaffolding for future feature gates
CAPABILITY_PLATFORM_FULL_ADMIN: Final[str] = "platform_full_admin"
CAPABILITY_ORG_CREATE_AND_ASSIGN: Final[str] = "org_create_and_assign"
CAPABILITY_PRIVATE_DEPLOY_CONFIG: Final[str] = "private_deploy_config"
CAPABILITY_GLOBAL_DASHBOARD_READONLY: Final[str] = "global_dashboard_readonly"
CAPABILITY_PERSONAL_TRIAL_INVITE: Final[str] = "personal_trial_invite"
CAPABILITY_SCHOOL_USER_MANAGE: Final[str] = "school_user_manage"
CAPABILITY_SCHOOL_DASHBOARD: Final[str] = "school_dashboard"
CAPABILITY_TIERED_B2B_CONTENT: Final[str] = "tiered_b2b_content"
CAPABILITY_CONSUMER_BASIC: Final[str] = "consumer_basic"
CAPABILITY_CONSUMER_AI_LIMITED: Final[str] = "consumer_ai_limited"
CAPABILITY_CONSUMER_AI_FULL: Final[str] = "consumer_ai_full"

_CAPABILITY_ROLE_MAP: dict[str, frozenset[str]] = {
    CAPABILITY_PLATFORM_FULL_ADMIN: frozenset({ROLE_SUPERADMIN}),
    CAPABILITY_ORG_CREATE_AND_ASSIGN: frozenset({ROLE_SUPERADMIN}),
    CAPABILITY_PRIVATE_DEPLOY_CONFIG: frozenset({ROLE_SUPERADMIN}),
    CAPABILITY_GLOBAL_DASHBOARD_READONLY: frozenset({ROLE_SUPERADMIN, ROLE_PLATFORM_BD}),
    CAPABILITY_PERSONAL_TRIAL_INVITE: frozenset(
        {ROLE_SUPERADMIN, ROLE_PLATFORM_BD, ROLE_EXPERT}
    ),
    CAPABILITY_SCHOOL_USER_MANAGE: frozenset({ROLE_SCHOOL_ADMIN}),
    CAPABILITY_SCHOOL_DASHBOARD: frozenset({ROLE_SCHOOL_ADMIN}),
    CAPABILITY_TIERED_B2B_CONTENT: frozenset({ROLE_TEACHER}),
    CAPABILITY_CONSUMER_BASIC: frozenset({ROLE_PERSONAL_TRIAL, ROLE_PERSONAL_PAID}),
    CAPABILITY_CONSUMER_AI_LIMITED: frozenset({ROLE_PERSONAL_TRIAL}),
    CAPABILITY_CONSUMER_AI_FULL: frozenset({ROLE_PERSONAL_PAID}),
}


def normalize_role(role: str | None) -> str:
    """Map legacy DB role strings to canonical slugs."""
    if not role:
        return ROLE_TEACHER
    if role in ALL_USER_ROLES:
        return role
    return LEGACY_TO_CANONICAL.get(role, role)


def role_in(current_user, roles: frozenset[str]) -> bool:
    """True when the user's stored role is in the given set (with legacy fallbacks)."""
    if not hasattr(current_user, "role"):
        return False
    raw = current_user.role or LEGACY_ROLE_USER
    if raw in roles:
        return True
    canonical = normalize_role(raw)
    return canonical in roles


def user_has_capability(current_user, capability: str) -> bool:
    """Check whether a user role grants a named capability (scaffolding only)."""
    allowed = _CAPABILITY_ROLE_MAP.get(capability)
    if allowed is None:
        return False
    return role_in(current_user, allowed)
