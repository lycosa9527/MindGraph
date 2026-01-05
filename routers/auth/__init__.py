"""
Authentication Router Module
============================

Aggregates all authentication sub-routers into a single router for easy inclusion in the main app.
Exports router and utilities for use throughout the application.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from fastapi import APIRouter

# Import all sub-routers
from . import registration, login, sms, captcha, password, session, public, avatar, phone
from .admin import admin_router

# Import utilities
from .helpers import (
    BEIJING_TIMEZONE,
    get_beijing_now,
    get_beijing_today_start_utc,
    utc_to_beijing_iso,
    track_user_activity,
    set_auth_cookies,
    commit_user_with_retry,
)
from .dependencies import (
    get_language_dependency,
    require_admin,
    require_admin_or_manager,
    require_manager,
)

# Create main auth router
router = APIRouter()

# Include all sub-routers
router.include_router(public.router)
router.include_router(registration.router)
router.include_router(login.router)
router.include_router(sms.router)
router.include_router(captcha.router)
router.include_router(password.router)
router.include_router(session.router)
router.include_router(avatar.router)
router.include_router(phone.router)
router.include_router(admin_router)

# Export router and utilities
__all__ = [
    'router',
    'BEIJING_TIMEZONE',
    'get_beijing_now',
    'get_beijing_today_start_utc',
    'utc_to_beijing_iso',
    'track_user_activity',
    'set_auth_cookies',
    'commit_user_with_retry',
    'get_language_dependency',
    'require_admin',
    'require_admin_or_manager',
    'require_manager',
]

