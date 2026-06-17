"""
Env-configured superadmin detection (ADMIN_PHONES / ADMIN_USER_IDS).

Kept separate from roles.py and admin_panel_permissions.py to avoid import cycles.
"""

from __future__ import annotations

import uuid

from utils.auth.config import ADMIN_PHONES, ADMIN_USER_IDS


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


def is_env_configured_superadmin(current_user) -> bool:
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
