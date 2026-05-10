"""
Authentication Configuration for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Configuration constants for authentication, JWT, and security.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# ============================================================================
# JWT Configuration
# ============================================================================

JWT_ALGORITHM = "HS256"
# Redis key for JWT secret storage
JWT_SECRET_REDIS_KEY = "jwt:secret"
# File path for JWT secret backup (for recovery after Redis flush)
JWT_SECRET_BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", ".jwt_secret"
)

# Access token: Short-lived (1 hour default), refreshed automatically
ACCESS_TOKEN_EXPIRY_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRY_MINUTES", "60"))
# Refresh token: Long-lived (7 days default), stored in httpOnly cookie
REFRESH_TOKEN_EXPIRY_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRY_DAYS", "7"))
# Legacy - kept for backward compatibility during transition
JWT_EXPIRY_HOURS = ACCESS_TOKEN_EXPIRY_MINUTES // 60 if ACCESS_TOKEN_EXPIRY_MINUTES >= 60 else 1

# ============================================================================
# Reverse Proxy Configuration
# ============================================================================

TRUSTED_PROXY_IPS = os.getenv("TRUSTED_PROXY_IPS", "").split(",") if os.getenv("TRUSTED_PROXY_IPS") else []

# ============================================================================
# Authentication Mode Configuration
# ============================================================================

# Authentication Mode: standard, enterprise, bayi
# enterprise: disables JWT checks—use only on isolated networks (see utils.auth.enterprise_mode).
AUTH_MODE = os.getenv("AUTH_MODE", "standard").strip().lower()


def _parse_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


# When false, skip MaxMind CN check on email login (emergency off without deploy).
# In AUTH_MODE bayi, login route skips this check for predictable school deployments.
EMAIL_LOGIN_CN_BLOCK_ENABLED = _parse_bool_env("EMAIL_LOGIN_CN_BLOCK_ENABLED", True)

# VPN / CN transition: kick non-mainland-phone users when country flips to CN mid-session.
VPN_CN_KICKOUT_ENABLED = _parse_bool_env("VPN_CN_KICKOUT_ENABLED", False)


def _parse_int_id_allowlist(raw: str) -> set[int]:
    """Comma-separated user IDs for VPN CN kick-out bypass (support / testing)."""
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.add(int(part))
        except ValueError:
            logger.warning("Invalid user id in VPN_CN_KICKOUT_ALLOWLIST_USER_IDS: %s", part)
    return result


VPN_CN_KICKOUT_ALLOWLIST_USER_IDS = _parse_int_id_allowlist(os.getenv("VPN_CN_KICKOUT_ALLOWLIST_USER_IDS", "").strip())

# Invite, SMS/email registration, overseas email signup, quick-register workshop links
REGISTRATION_ENABLED = _parse_bool_env("REGISTRATION_ENABLED", True)

# Enterprise Mode Configuration
ENTERPRISE_DEFAULT_ORG_CODE = os.getenv("ENTERPRISE_DEFAULT_ORG_CODE", "DEMO-001").strip()
ENTERPRISE_DEFAULT_USER_PHONE = os.getenv("ENTERPRISE_DEFAULT_USER_PHONE", "enterprise@system.com").strip()

# Bayi 6-digit passkey (AUTH_MODE=bayi only; separate from vendor SSO /loginByXz).
# Elevated access: include the Bayi login identity (default bayi@system.com) in ADMIN_PHONES.
BAYI_PASSKEY = os.getenv("BAYI_PASSKEY", "888888").strip()

# Public Dashboard Configuration
PUBLIC_DASHBOARD_PASSKEY = os.getenv("PUBLIC_DASHBOARD_PASSKEY", "123456").strip()

# ============================================================================
# Bayi Mode Configuration
# ============================================================================

BAYI_DECRYPTION_KEY = os.getenv("BAYI_DECRYPTION_KEY", "v8IT7XujLPsM7FYuDPRhPtZk").strip()
BAYI_DEFAULT_ORG_CODE = os.getenv("BAYI_DEFAULT_ORG_CODE", "BAYI-001").strip()
# Allow 10 seconds clock skew tolerance
BAYI_CLOCK_SKEW_TOLERANCE = int(os.getenv("BAYI_CLOCK_SKEW_TOLERANCE", "10"))


def _parse_optional_positive_int(env_name: str) -> Optional[int]:
    """Parse a positive int from env, or None if unset/invalid."""
    raw = os.getenv(env_name)
    if raw is None or not str(raw).strip():
        return None
    try:
        value = int(str(raw).strip())
    except ValueError:
        logger.warning("Invalid integer for %s: %r", env_name, raw)
        return None
    if value <= 0:
        logger.warning("%s must be a positive integer, got %r", env_name, raw)
        return None
    return value


BAYI_DEFAULT_ORG_ID = _parse_optional_positive_int("BAYI_DEFAULT_ORG_ID")
_bayi_sso_display_raw = os.getenv("BAYI_SSO_DEFAULT_DISPLAY_NAME", "八一用户")
BAYI_SSO_DEFAULT_DISPLAY_NAME = (
    _bayi_sso_display_raw.strip() if _bayi_sso_display_raw and str(_bayi_sso_display_raw).strip() else "八一用户"
)


def _parse_admin_user_ids(raw: str) -> frozenset[int]:
    """Comma-separated positive user primary keys for env-based admin access."""
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            logger.warning("Invalid user id in ADMIN_USER_IDS: %s", part)
            continue
        if value <= 0:
            logger.warning("ADMIN_USER_IDS entries must be positive integers, got %s", part)
            continue
        result.add(value)
    return frozenset(result)


# ============================================================================
# Admin Configuration
# ============================================================================

ADMIN_PHONES = os.getenv("ADMIN_PHONES", "").split(",")

# Comma-separated users.id values granting admin (alongside ADMIN_PHONES).
ADMIN_USER_IDS = _parse_admin_user_ids(os.getenv("ADMIN_USER_IDS", "").strip())

# ============================================================================
# Security Configuration
# ============================================================================

MAX_LOGIN_ATTEMPTS = 10
MAX_CAPTCHA_ATTEMPTS = 30
LOCKOUT_DURATION_MINUTES = 5
RATE_LIMIT_WINDOW_MINUTES = 15
CAPTCHA_SESSION_COOKIE_NAME = "captcha_session"

# bcrypt configuration
BCRYPT_ROUNDS = 12
