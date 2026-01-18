"""
Authentication Configuration for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Configuration constants for authentication, JWT, and security.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import ipaddress
import logging
import os
from typing import Set

logger = logging.getLogger(__name__)

# ============================================================================
# JWT Configuration
# ============================================================================

JWT_ALGORITHM = "HS256"
# Redis key for JWT secret storage
JWT_SECRET_REDIS_KEY = "jwt:secret"
# File path for JWT secret backup (for recovery after Redis flush)
JWT_SECRET_BACKUP_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    ".jwt_secret"
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

TRUSTED_PROXY_IPS = (
    os.getenv("TRUSTED_PROXY_IPS", "").split(",")
    if os.getenv("TRUSTED_PROXY_IPS")
    else []
)

# ============================================================================
# Authentication Mode Configuration
# ============================================================================

# Authentication Mode: standard, enterprise, demo, bayi
AUTH_MODE = os.getenv("AUTH_MODE", "standard").strip().lower()

# Enterprise Mode Configuration
ENTERPRISE_DEFAULT_ORG_CODE = os.getenv("ENTERPRISE_DEFAULT_ORG_CODE", "DEMO-001").strip()
ENTERPRISE_DEFAULT_USER_PHONE = os.getenv(
    "ENTERPRISE_DEFAULT_USER_PHONE", "enterprise@system.com"
).strip()

# Demo Mode Configuration
DEMO_PASSKEY = os.getenv("DEMO_PASSKEY", "888888").strip()
ADMIN_DEMO_PASSKEY = os.getenv("ADMIN_DEMO_PASSKEY", "999999").strip()

# Public Dashboard Configuration
PUBLIC_DASHBOARD_PASSKEY = os.getenv("PUBLIC_DASHBOARD_PASSKEY", "123456").strip()

# ============================================================================
# Bayi Mode Configuration
# ============================================================================

BAYI_DECRYPTION_KEY = os.getenv(
    "BAYI_DECRYPTION_KEY", "v8IT7XujLPsM7FYuDPRhPtZk"
).strip()
BAYI_DEFAULT_ORG_CODE = os.getenv("BAYI_DEFAULT_ORG_CODE", "BAYI-001").strip()
# Allow 10 seconds clock skew tolerance
BAYI_CLOCK_SKEW_TOLERANCE = int(os.getenv("BAYI_CLOCK_SKEW_TOLERANCE", "10"))

# Bayi IP Whitelist Configuration
BAYI_IP_WHITELIST_STR = os.getenv("BAYI_IP_WHITELIST", "").strip()
BAYI_IP_WHITELIST: Set[str] = set()

# ============================================================================
# Admin Configuration
# ============================================================================

ADMIN_PHONES = os.getenv("ADMIN_PHONES", "").split(",")

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


def init_bayi_ip_whitelist() -> None:
    """
    Initialize bayi IP whitelist from environment variable.

    Called during module initialization to parse and validate IP addresses.
    Only logs if in bayi mode to avoid noise in other modes.
    """
    if not BAYI_IP_WHITELIST_STR:
        return

    for ip_entry in BAYI_IP_WHITELIST_STR.split(","):
        ip_entry = ip_entry.strip()
        if not ip_entry:
            continue
        try:
            # Validate and normalize IP address
            ip_addr_obj = ipaddress.ip_address(ip_entry)
            BAYI_IP_WHITELIST.add(str(ip_addr_obj))
            # Only log in bayi mode to avoid noise in other modes
            if AUTH_MODE == "bayi":
                logger.info("Added IP to bayi IP whitelist: %s", ip_entry)
        except ValueError as e:
            if AUTH_MODE == "bayi":
                logger.warning(
                    "Invalid IP entry in BAYI_IP_WHITELIST: %s - %s", ip_entry, e
                )

    if AUTH_MODE == "bayi":
        if BAYI_IP_WHITELIST:
            logger.info("Bayi IP whitelist loaded: %d IP(s)", len(BAYI_IP_WHITELIST))
        else:
            logger.info("Bayi IP whitelist configured but no valid IPs found")


# Initialize IP whitelist on module import
init_bayi_ip_whitelist()
