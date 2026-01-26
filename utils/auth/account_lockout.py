"""
Account Lockout for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions for managing account lockout due to failed login attempts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime, timedelta
from typing import Tuple

from sqlalchemy.orm import Session

from .config import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES

logger = logging.getLogger(__name__)

# Redis modules (optional)
_REDIS_AVAILABLE = False
_USER_CACHE = None

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
    _REDIS_AVAILABLE = True
    _USER_CACHE = redis_user_cache
except ImportError:
    pass


def check_account_lockout(user) -> Tuple[bool, str]:
    """
    Check if user account is locked

    Args:
        user: User model object

    Returns:
        (is_locked, error_message) tuple
    """
    if user.locked_until and user.locked_until > datetime.utcnow():
        seconds_left = int((user.locked_until - datetime.utcnow()).total_seconds())
        minutes_left = (seconds_left // 60) + 1
        if minutes_left == 1:
            return True, (
                f"Account temporarily locked due to too many failed attempts. "
                f"Please try again in {minutes_left} minute."
            )
        return True, (
            f"Account temporarily locked due to too many failed attempts. "
            f"Please try again in {minutes_left} minutes."
        )

    return False, ""


def lock_account(user, db: Session) -> None:
    """
    Lock user account for LOCKOUT_DURATION_MINUTES

    Args:
        user: User model object
        db: Database session
    """
    user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    db.commit()

    # Invalidate and re-cache user (lock status changed)
    if _REDIS_AVAILABLE and _USER_CACHE:
        try:
            _USER_CACHE.invalidate(user.id, user.phone)
            _USER_CACHE.cache_user(user)
        except Exception as e:
            logger.debug("[Auth] Failed to update cache after lock_account: %s", e)

    logger.warning("Account locked: %s", user.phone)


def reset_failed_attempts(user, db: Session) -> None:
    """
    Reset failed login attempts on successful login

    Args:
        user: User model object
        db: Database session
    """
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.utcnow()
    db.commit()

    # Invalidate and re-cache user (lock status and last_login changed)
    if _REDIS_AVAILABLE and _USER_CACHE:
        try:
            _USER_CACHE.invalidate(user.id, user.phone)
            _USER_CACHE.cache_user(user)
        except Exception as e:
            logger.debug(
                "[Auth] Failed to update cache after reset_failed_attempts: %s", e
            )


def increment_failed_attempts(user, db: Session) -> None:
    """
    Increment failed login attempts

    Args:
        user: User model object
        db: Database session
    """
    user.failed_login_attempts += 1
    db.commit()

    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        lock_account(user, db)
    else:
        # Invalidate and re-cache user (failed_login_attempts changed)
        if _REDIS_AVAILABLE and _USER_CACHE:
            try:
                _USER_CACHE.invalidate(user.id, user.phone)
                _USER_CACHE.cache_user(user)
            except Exception as e:
                logger.debug(
                    "[Auth] Failed to update cache after increment_failed_attempts: %s",
                    e
                )
