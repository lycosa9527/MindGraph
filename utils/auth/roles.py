"""
Role Checking for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions to check user roles and permissions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import uuid

from config.settings import config
from services.redis.cache.redis_feature_org_access_cache import get_cached_map as _get_feature_access_map_cached

from .config import ADMIN_PHONES, ADMIN_USER_IDS
from .role_constants import (
    B2B_ORG_ROLES,
    C2C_CONSUMER_ROLES,
    LEGACY_ROLE_USER,
    PLATFORM_LEVEL_ROLES,
    ROLE_EXPERT,
    ROLE_PERSONAL_PAID,
    ROLE_PERSONAL_TRIAL,
    ROLE_PLATFORM_BD,
    ROLE_SUPERADMIN,
    SCHOOL_ADMIN_ROLES,
    SUPERADMIN_ROLES,
    TEACHER_ROLES,
    normalize_role,
    role_in,
)

FEATURE_KEY_TO_CONFIG_ATTR = {
    "feature_rag_chunk_test": "FEATURE_RAG_CHUNK_TEST",
    "feature_course": "FEATURE_COURSE",
    "feature_template": "FEATURE_TEMPLATE",
    "feature_community": "FEATURE_COMMUNITY",
    "feature_askonce": "FEATURE_ASKONCE",
    "feature_school_zone": "FEATURE_SCHOOL_ZONE",
    "feature_debateverse": "FEATURE_DEBATEVERSE",
    "feature_knowledge_space": "FEATURE_KNOWLEDGE_SPACE",
    "feature_library": "FEATURE_LIBRARY",
    "feature_gewe": "FEATURE_GEWE",
    "feature_smart_response": "FEATURE_SMART_RESPONSE",
    "feature_teacher_usage": "FEATURE_TEACHER_USAGE",
    "feature_workshop_chat": "FEATURE_WORKSHOP_CHAT",
    "feature_markets": "FEATURE_MARKETS",
    "feature_mindbot": "FEATURE_MINDBOT",
    "feature_kitty_agent": "FEATURE_KITTY_AGENT",
}


def phone_matches_admin_env_token(user_phone: str | None, token: str) -> bool:
    """Match env token to user phone by string equality or UUID equality (case-insensitive)."""
    if user_phone is None:
        return False
    u_raw = user_phone.strip()
    t_raw = token.strip()
    if not u_raw or not t_raw:
        return False
    if u_raw == t_raw:
        return True
    try:
        return uuid.UUID(u_raw) == uuid.UUID(t_raw)
    except ValueError:
        return False


def _is_env_superadmin(current_user) -> bool:
    """True when user id or phone matches env-configured superadmin tokens."""
    user_id = getattr(current_user, "id", None)
    if user_id is not None and user_id in ADMIN_USER_IDS:
        return True
    admin_tokens = [p.strip() for p in ADMIN_PHONES if p.strip()]
    user_phone = getattr(current_user, "phone", None)
    for tok in admin_tokens:
        if phone_matches_admin_env_token(user_phone, tok):
            return True
    return False


def is_superadmin(current_user) -> bool:
    """
    Full platform admin (超级管理员).

    Granted when role is superadmin (or legacy admin) or env admin tokens match.
    """
    if role_in(current_user, SUPERADMIN_ROLES):
        return True
    return _is_env_superadmin(current_user)


def is_admin(current_user) -> bool:
    """Alias for is_superadmin — full platform admin access."""
    return is_superadmin(current_user)


def is_platform_bd(current_user) -> bool:
    """Teaching research (教研) — read-only global dashboard."""
    return role_in(current_user, frozenset({ROLE_PLATFORM_BD}))


def is_expert(current_user) -> bool:
    """Platform expert (专家) — B2B school invites (own orgs)."""
    return role_in(current_user, frozenset({ROLE_EXPERT}))


def is_platform_level(current_user) -> bool:
    """Any platform-tier role: superadmin, operations (platform_bd), or expert."""
    if is_superadmin(current_user):
        return True
    return role_in(current_user, PLATFORM_LEVEL_ROLES)


def is_school_admin(current_user) -> bool:
    """School org admin (学校管理员), formerly manager."""
    return role_in(current_user, SCHOOL_ADMIN_ROLES)


def is_manager(current_user) -> bool:
    """Alias for is_school_admin — legacy name preserved for callers."""
    return is_school_admin(current_user)


def is_teacher(current_user) -> bool:
    """B2B school member (教师用户), formerly user."""
    return role_in(current_user, TEACHER_ROLES)


def is_personal_trial(current_user) -> bool:
    """C-end trial account (个人体验账号)."""
    return role_in(current_user, frozenset({ROLE_PERSONAL_TRIAL}))


def is_personal_paid(current_user) -> bool:
    """C-end paid account (个人付费账号)."""
    return role_in(current_user, frozenset({ROLE_PERSONAL_PAID}))


def is_c2c_consumer(current_user) -> bool:
    """Personal consumer account (trial or paid)."""
    return role_in(current_user, C2C_CONSUMER_ROLES)


def is_b2b_org_member(current_user) -> bool:
    """School admin or teacher within a B2B organization."""
    return role_in(current_user, B2B_ORG_ROLES)


def is_admin_or_manager(current_user) -> bool:
    """
    Elevated org/platform admin access for shared admin routes.

    Superadmin and school_admin only — operations (platform_bd) and expert excluded.
    """
    return is_superadmin(current_user) or is_school_admin(current_user)


def is_management_panel_user(current_user) -> bool:
    """True when user may access the unified management panel (roles 1–4)."""
    from utils.auth.admin_panel_permissions import role_has_panel_access

    if not hasattr(current_user, "role"):
        return False
    if is_superadmin(current_user):
        return True
    return role_has_panel_access(current_user.role)


def can_moderate_workshop_channel(current_user, channel) -> bool:
    """
    Whether the user may remove or manage others' content in this channel.

    Superadmins act globally; school admins only within their organization.
    """
    ch_type = getattr(channel, "channel_type", None)
    if ch_type == "announce":
        return is_superadmin(current_user)
    if is_superadmin(current_user):
        return True
    if not is_school_admin(current_user):
        return False
    org_id = getattr(channel, "organization_id", None)
    user_org = getattr(current_user, "organization_id", None)
    return org_id is not None and org_id == user_org


def _global_feature_flag_enabled(feature_key: str) -> bool:
    attr = FEATURE_KEY_TO_CONFIG_ATTR.get(feature_key)
    if not attr:
        return True
    return bool(getattr(config, attr, False))


def _legacy_workshop_preview_or_open(feature_key: str, current_user) -> bool:
    if feature_key != "feature_workshop_chat":
        return True
    org_id = getattr(current_user, "organization_id", None)
    if org_id is None:
        return False
    return org_id in config.WORKSHOP_CHAT_PREVIEW_ORG_IDS


async def user_has_feature_access(current_user, feature_key: str) -> bool:
    """
    Whether the user may use this feature (global FEATURE_* + DB rules).

    Superadmins always pass when the global flag is on. School admins pass for
    every feature except ``feature_mindbot``: for MindBot, school admins are
    subject to ``feature_access_*`` grants (same as regular users).
    """
    if not _global_feature_flag_enabled(feature_key):
        return False
    if is_superadmin(current_user):
        return True
    if is_school_admin(current_user) and feature_key != "feature_mindbot":
        return True
    doc = await _get_feature_access_map_cached() or {}
    entry = doc.get(feature_key)
    if entry is None:
        return _legacy_workshop_preview_or_open(feature_key, current_user)
    if not entry.restrict:
        return True
    uid = getattr(current_user, "id", None)
    org_id = getattr(current_user, "organization_id", None)
    ok_user = uid is not None and uid in entry.user_ids
    ok_org = org_id is not None and org_id in entry.organization_ids
    return ok_user or ok_org


async def can_access_workshop_chat(current_user) -> bool:
    """Workshop Chat gate: global flag, then DB rules or WORKSHOP_CHAT_PREVIEW_ORG_IDS."""
    return await user_has_feature_access(current_user, "feature_workshop_chat")


def get_user_role(current_user) -> str:
    """
    Return the canonical role slug for API responses.

    Env-configured admins resolve as superadmin even if DB role differs.
    """
    if is_superadmin(current_user):
        return ROLE_SUPERADMIN
    raw = getattr(current_user, "role", None) or LEGACY_ROLE_USER
    return normalize_role(raw)
