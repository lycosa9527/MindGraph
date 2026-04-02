"""
Role Checking for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions to check user roles and permissions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from config.settings import config
from services.redis.cache.redis_feature_org_access_cache import get_cached_map as _get_feature_access_map_cached

from .config import AUTH_MODE, ADMIN_PHONES

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
}


def is_admin(current_user) -> bool:
    """
    Check if user is admin (full access to all data)

    Admin access granted if:
    1. User has role='admin' in database
    2. User phone in ADMIN_PHONES env variable (production admins)
    3. User is demo-admin@system.com AND server is in demo mode (demo admin)
    4. User is bayi-admin@system.com AND server is in bayi mode (bayi admin)

    This ensures demo/bayi admin passkey only works in their respective modes
    for security.

    Args:
        current_user: User model object

    Returns:
        True if user is admin, False otherwise
    """
    # Check database role field (admin or superadmin)
    if hasattr(current_user, "role") and current_user.role in ("admin", "superadmin"):
        return True

    # Check ADMIN_PHONES list (production admins)
    admin_phones = [p.strip() for p in ADMIN_PHONES if p.strip()]
    if current_user.phone in admin_phones:
        return True

    # Check demo admin (only in demo mode for security)
    if AUTH_MODE == "demo" and current_user.phone == "demo-admin@system.com":
        return True

    # Check bayi admin (only in bayi mode for security)
    if AUTH_MODE == "bayi" and current_user.phone == "bayi-admin@system.com":
        return True

    return False


def is_manager(current_user) -> bool:
    """
    Check if user is a manager (org-scoped admin access)

    Manager can access admin dashboard but only sees their organization's data.

    Args:
        current_user: User model object

    Returns:
        True if user is manager, False otherwise
    """
    if hasattr(current_user, "role") and current_user.role == "manager":
        return True
    return False


def is_admin_or_manager(current_user) -> bool:
    """
    Check if user has any elevated access (admin or manager)

    Used for routes that both admin and manager can access.

    Args:
        current_user: User model object

    Returns:
        True if user is admin or manager, False otherwise
    """
    return is_admin(current_user) or is_manager(current_user)


def can_moderate_workshop_channel(current_user, channel) -> bool:
    """
    Whether the user may remove or manage others' content in this channel.

    Mirrors Zulip's model: realm administrators and organization-scoped
    managers act as stream administrators; the global announce channel is
    limited to full admins (like a system-wide announcement stream).
    """
    ch_type = getattr(channel, "channel_type", None)
    if ch_type == "announce":
        return is_admin(current_user)
    if is_admin(current_user):
        return True
    if not is_manager(current_user):
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


def user_has_feature_access(current_user, feature_key: str) -> bool:
    """
    Whether the user may use this feature (global FEATURE_* + DB rules).

    Admins and managers pass when the global flag is on. Otherwise rules in
    ``feature_access_*`` tables apply; missing rules fall back to open access
    except Workshop Chat, which uses WORKSHOP_CHAT_PREVIEW_ORG_IDS.
    """
    if not _global_feature_flag_enabled(feature_key):
        return False
    if is_admin_or_manager(current_user):
        return True
    doc = _get_feature_access_map_cached() or {}
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


def can_access_workshop_chat(current_user) -> bool:
    """
    Workshop Chat gate: global flag, then DB rules or WORKSHOP_CHAT_PREVIEW_ORG_IDS.
    """
    return user_has_feature_access(current_user, "feature_workshop_chat")


def get_user_role(current_user) -> str:
    """
    Get the effective role of a user

    Args:
        current_user: User model object

    Returns:
        'admin', 'manager', or 'user'
    """
    if is_admin(current_user):
        return "admin"
    if is_manager(current_user):
        return "manager"
    return "user"
