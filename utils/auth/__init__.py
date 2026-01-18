"""
Authentication Utilities for MindGraph
Author: lycosa9527
Made by: MindSpring Team

JWT tokens, password hashing, rate limiting, and security functions.

This module provides backward-compatible imports from the refactored auth package.
All functions previously available from utils.auth are re-exported here.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

# Configuration exports
from .config import (
    JWT_ALGORITHM,
    JWT_SECRET_REDIS_KEY,
    JWT_SECRET_BACKUP_FILE,
    ACCESS_TOKEN_EXPIRY_MINUTES,
    REFRESH_TOKEN_EXPIRY_DAYS,
    JWT_EXPIRY_HOURS,
    TRUSTED_PROXY_IPS,
    AUTH_MODE,
    ENTERPRISE_DEFAULT_ORG_CODE,
    ENTERPRISE_DEFAULT_USER_PHONE,
    DEMO_PASSKEY,
    ADMIN_DEMO_PASSKEY,
    PUBLIC_DASHBOARD_PASSKEY,
    BAYI_DECRYPTION_KEY,
    BAYI_DEFAULT_ORG_CODE,
    BAYI_CLOCK_SKEW_TOLERANCE,
    BAYI_IP_WHITELIST_STR,
    BAYI_IP_WHITELIST,
    ADMIN_PHONES,
    MAX_LOGIN_ATTEMPTS,
    MAX_CAPTCHA_ATTEMPTS,
    LOCKOUT_DURATION_MINUTES,
    RATE_LIMIT_WINDOW_MINUTES,
    CAPTCHA_SESSION_COOKIE_NAME,
    BCRYPT_ROUNDS,
)

# JWT Secret exports
from .jwt_secret import get_jwt_secret

# Password exports
from .password import hash_password, verify_password

# Token exports
from .tokens import (
    security,
    api_key_header,
    create_access_token,
    create_refresh_token,
    hash_refresh_token,
    compute_device_hash,
    decode_access_token,
)

# Request helper exports
from .request_helpers import is_https, get_client_ip

# Authentication exports
from .authentication import (
    get_current_user,
    get_user_from_cookie,
    get_current_user_or_api_key,
)

# Enterprise mode exports
from .enterprise_mode import get_enterprise_user

# Demo mode exports
from .demo_mode import (
    display_demo_info,
    verify_demo_passkey,
    is_admin_demo_passkey,
    verify_dashboard_passkey,
)

# Bayi mode exports
from .bayi_mode import decrypt_bayi_token, validate_bayi_token_body

# IP whitelist exports
from .ip_whitelist import is_ip_whitelisted

# Invitation exports
from .invitations import load_invitation_codes, validate_invitation_code

# Account lockout exports
from .account_lockout import (
    check_account_lockout,
    lock_account,
    reset_failed_attempts,
    increment_failed_attempts,
)

# Role exports
from .roles import is_admin, is_manager, is_admin_or_manager, get_user_role

# API key exports
from .api_keys import validate_api_key, track_api_key_usage, generate_api_key

# WebSocket auth exports
from .websocket_auth import get_current_user_ws

# Legacy variable names for backward compatibility
_JWT_SECRET_REDIS_KEY = JWT_SECRET_REDIS_KEY
_JWT_SECRET_BACKUP_FILE = JWT_SECRET_BACKUP_FILE

__all__ = [
    # Configuration
    "JWT_ALGORITHM",
    "JWT_SECRET_REDIS_KEY",
    "JWT_SECRET_BACKUP_FILE",
    "ACCESS_TOKEN_EXPIRY_MINUTES",
    "REFRESH_TOKEN_EXPIRY_DAYS",
    "JWT_EXPIRY_HOURS",
    "TRUSTED_PROXY_IPS",
    "AUTH_MODE",
    "ENTERPRISE_DEFAULT_ORG_CODE",
    "ENTERPRISE_DEFAULT_USER_PHONE",
    "DEMO_PASSKEY",
    "ADMIN_DEMO_PASSKEY",
    "PUBLIC_DASHBOARD_PASSKEY",
    "BAYI_DECRYPTION_KEY",
    "BAYI_DEFAULT_ORG_CODE",
    "BAYI_CLOCK_SKEW_TOLERANCE",
    "BAYI_IP_WHITELIST_STR",
    "BAYI_IP_WHITELIST",
    "ADMIN_PHONES",
    "MAX_LOGIN_ATTEMPTS",
    "MAX_CAPTCHA_ATTEMPTS",
    "LOCKOUT_DURATION_MINUTES",
    "RATE_LIMIT_WINDOW_MINUTES",
    "CAPTCHA_SESSION_COOKIE_NAME",
    "BCRYPT_ROUNDS",
    # JWT Secret
    "get_jwt_secret",
    # Password
    "hash_password",
    "verify_password",
    # Tokens
    "security",
    "api_key_header",
    "create_access_token",
    "create_refresh_token",
    "hash_refresh_token",
    "compute_device_hash",
    "decode_access_token",
    # Request helpers
    "is_https",
    "get_client_ip",
    # Authentication
    "get_current_user",
    "get_user_from_cookie",
    "get_current_user_or_api_key",
    # Enterprise mode
    "get_enterprise_user",
    # Demo mode
    "display_demo_info",
    "verify_demo_passkey",
    "is_admin_demo_passkey",
    "verify_dashboard_passkey",
    # Bayi mode
    "decrypt_bayi_token",
    "validate_bayi_token_body",
    # IP whitelist
    "is_ip_whitelisted",
    # Invitations
    "load_invitation_codes",
    "validate_invitation_code",
    # Account lockout
    "check_account_lockout",
    "lock_account",
    "reset_failed_attempts",
    "increment_failed_attempts",
    # Roles
    "is_admin",
    "is_manager",
    "is_admin_or_manager",
    "get_user_role",
    # API keys
    "validate_api_key",
    "track_api_key_usage",
    "generate_api_key",
    # WebSocket auth
    "get_current_user_ws",
    # Legacy names
    "_JWT_SECRET_REDIS_KEY",
    "_JWT_SECRET_BACKUP_FILE",
]
