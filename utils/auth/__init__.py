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

# Account lockout exports
from .account_lockout import (
    check_account_lockout,
    increment_failed_attempts,
    lock_account,
    reset_failed_attempts,
)

# API key exports
from .api_keys import generate_api_key, track_api_key_usage, validate_api_key

# Authentication exports
from .auth_resolution import AUTH_CONTEXT_USER_ATTR, load_user_from_jwt_session_token
from .authentication import (
    get_current_user,
    get_current_user_or_api_key,
    get_user_from_cookie,
    require_not_mgat_for_token_mint,
)

# Bayi mode exports
from .bayi_mode import decrypt_bayi_token, validate_bayi_token_body

# Configuration exports
from .config import (
    ACCESS_TOKEN_EXPIRY_MINUTES,
    ADMIN_PHONES,
    ADMIN_USER_IDS,
    AUTH_MODE,
    BAYI_CLOCK_SKEW_TOLERANCE,
    BAYI_DECRYPTION_KEY,
    BAYI_DEFAULT_ORG_CODE,
    BAYI_DEFAULT_ORG_ID,
    BAYI_PASSKEY,
    BAYI_SSO_DEFAULT_DISPLAY_NAME,
    BCRYPT_ROUNDS,
    CAPTCHA_SESSION_COOKIE_NAME,
    EMAIL_LOGIN_CN_BLOCK_ENABLED,
    ENTERPRISE_DEFAULT_ORG_CODE,
    ENTERPRISE_DEFAULT_USER_PHONE,
    JWT_ALGORITHM,
    JWT_EXPIRY_HOURS,
    JWT_SECRET_BACKUP_FILE,
    JWT_SECRET_REDIS_KEY,
    LOCKOUT_DURATION_MINUTES,
    MAX_CAPTCHA_ATTEMPTS,
    MAX_LOGIN_ATTEMPTS,
    PUBLIC_DASHBOARD_PASSKEY,
    RATE_LIMIT_WINDOW_MINUTES,
    is_public_dashboard_enabled,
    REFRESH_TOKEN_EXPIRY_DAYS,
    TRUSTED_PROXY_IPS,
)

# Enterprise mode exports
from .enterprise_mode import get_enterprise_user

# Invitation exports
from .invitations import load_invitation_codes, validate_invitation_code

# JWT Secret exports
from .jwt_secret import get_jwt_secret, warmup_jwt_secret_async

# Passkey helpers (Bayi 6-digit login, public dashboard)
from .passkey_utils import (
    verify_bayi_passkey,
    verify_dashboard_passkey,
)

# Password exports
from .password import hash_password, verify_password, verify_password_timing_dummy

# Request helper exports
from .request_helpers import get_client_ip, is_https

# Role exports
from .role_constants import (
    ALL_USER_ROLES,
    VALID_ASSIGNABLE_ROLES,
    normalize_role,
    user_has_capability,
)
from .roles import (
    can_access_workshop_chat,
    can_moderate_workshop_channel,
    get_user_role,
    is_admin,
    is_admin_or_manager,
    is_b2b_org_member,
    is_c2c_consumer,
    is_expert,
    is_management_panel_user,
    is_manager,
    is_personal_paid,
    is_personal_trial,
    is_platform_bd,
    is_platform_level,
    is_school_admin,
    is_superadmin,
    is_teacher,
    user_has_feature_access,
)

# Token exports
from .tokens import (
    api_key_header,
    compute_device_hash,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_refresh_token,
    security,
)
from .user_tokens import validate_user_token

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
    "EMAIL_LOGIN_CN_BLOCK_ENABLED",
    "ENTERPRISE_DEFAULT_ORG_CODE",
    "ENTERPRISE_DEFAULT_USER_PHONE",
    "BAYI_PASSKEY",
    "PUBLIC_DASHBOARD_PASSKEY",
    "is_public_dashboard_enabled",
    "BAYI_DECRYPTION_KEY",
    "BAYI_DEFAULT_ORG_CODE",
    "BAYI_DEFAULT_ORG_ID",
    "BAYI_SSO_DEFAULT_DISPLAY_NAME",
    "BAYI_CLOCK_SKEW_TOLERANCE",
    "ADMIN_PHONES",
    "ADMIN_USER_IDS",
    "MAX_LOGIN_ATTEMPTS",
    "MAX_CAPTCHA_ATTEMPTS",
    "LOCKOUT_DURATION_MINUTES",
    "RATE_LIMIT_WINDOW_MINUTES",
    "CAPTCHA_SESSION_COOKIE_NAME",
    "BCRYPT_ROUNDS",
    # JWT Secret
    "get_jwt_secret",
    "warmup_jwt_secret_async",
    # Password
    "hash_password",
    "verify_password",
    "verify_password_timing_dummy",
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
    "AUTH_CONTEXT_USER_ATTR",
    "load_user_from_jwt_session_token",
    "get_current_user",
    "get_user_from_cookie",
    "get_current_user_or_api_key",
    "require_not_mgat_for_token_mint",
    "validate_user_token",
    # Enterprise mode
    "get_enterprise_user",
    # Passkey auth
    "verify_bayi_passkey",
    "verify_dashboard_passkey",
    # Bayi mode
    "decrypt_bayi_token",
    "validate_bayi_token_body",
    # Invitations
    "load_invitation_codes",
    "validate_invitation_code",
    # Account lockout
    "check_account_lockout",
    "lock_account",
    "reset_failed_attempts",
    "increment_failed_attempts",
    # Roles
    "ALL_USER_ROLES",
    "VALID_ASSIGNABLE_ROLES",
    "normalize_role",
    "user_has_capability",
    "is_admin",
    "is_superadmin",
    "is_platform_bd",
    "is_expert",
    "is_school_admin",
    "is_teacher",
    "is_personal_trial",
    "is_personal_paid",
    "is_c2c_consumer",
    "is_b2b_org_member",
    "is_platform_level",
    "is_manager",
    "is_admin_or_manager",
    "is_management_panel_user",
    "can_moderate_workshop_channel",
    "can_access_workshop_chat",
    "user_has_feature_access",
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
