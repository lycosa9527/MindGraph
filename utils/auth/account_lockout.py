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
from datetime import UTC, datetime, timedelta
from typing import Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from .config import MAX_LOGIN_ATTEMPTS, LOCKOUT_DURATION_MINUTES

logger = logging.getLogger(__name__)

# Redis modules (optional)
_redis_available = False
_user_cache = None

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache

    _redis_available = True
    _user_cache = redis_user_cache
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
    now = datetime.now(UTC)
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=UTC)
        if locked_until > now:
            seconds_left = int((locked_until - now).total_seconds())
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


async def lock_account(user, db: AsyncSession) -> None:
    """
    Lock user account for LOCKOUT_DURATION_MINUTES

    Args:
        user: User model object
        db: Async database session
    """
    user.locked_until = datetime.now(UTC) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Invalidate and re-cache user (lock status changed)
    if _redis_available and _user_cache:
        try:
            _user_cache.invalidate(user.id, user.phone)
            _user_cache.cache_user(user)
        except Exception as e:
            logger.debug("[Auth] Failed to update cache after lock_account: %s", e)

    logger.warning("Account locked: %s", user.phone)


async def reset_failed_attempts(user, db: AsyncSession) -> None:
    """
    Reset failed login attempts on successful login

    Args:
        user: User model object
        db: Async database session
    """
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login = datetime.now(UTC)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Invalidate and re-cache user (lock status and last_login changed)
    if _redis_available and _user_cache:
        try:
            _user_cache.invalidate(user.id, user.phone)
            _user_cache.cache_user(user)
        except Exception as e:
            logger.debug("[Auth] Failed to update cache after reset_failed_attempts: %s", e)


async def increment_failed_attempts(user, db: AsyncSession) -> None:
    """
    Increment failed login attempts

    Args:
        user: User model object
        db: Async database session
    """
    user.failed_login_attempts += 1
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    if user.failed_login_attempts >= MAX_LOGIN_ATTEMPTS:
        await lock_account(user, db)
    else:
        # Invalidate and re-cache user (failed_login_attempts changed)
        if _redis_available and _user_cache:
            try:
                _user_cache.invalidate(user.id, user.phone)
                _user_cache.cache_user(user)
            except Exception as e:
                logger.debug(
                    "[Auth] Failed to update cache after increment_failed_attempts: %s",
                    e,
                )
