"""
Authentication Helper Functions
================================

Shared helper functions for authentication endpoints:
- Timezone utilities (Beijing timezone)
- Cookie management
- Session management
- User activity tracking
- Database retry logic

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import logging
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Callable, Awaitable

from fastapi import HTTPException, Request, Response, status
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from models.auth import User
from services.redis_session_manager import get_session_manager
from utils.auth import create_access_token, is_https

logger = logging.getLogger(__name__)

# ============================================================================
# TIMEZONE UTILITIES
# ============================================================================

# Beijing timezone (UTC+8)
BEIJING_TIMEZONE = timezone(timedelta(hours=8))


def get_beijing_now() -> datetime:
    """Get current datetime in Beijing timezone (UTC+8)"""
    return datetime.now(BEIJING_TIMEZONE)


def get_beijing_today_start_utc() -> datetime:
    """
    Get today's start (00:00:00) in Beijing timezone, converted to UTC.
    This is used for database queries since timestamps are stored in UTC.
    Example: If it's 2025-01-20 01:00:00 in Beijing, today starts at 2025-01-20 00:00:00 Beijing
    which is 2025-01-19 16:00:00 UTC.
    """
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Convert Beijing time to UTC for database queries
    return beijing_today_start.astimezone(timezone.utc).replace(tzinfo=None)


def utc_to_beijing_iso(utc_dt: Optional[datetime]) -> Optional[str]:
    """
    Convert UTC datetime to Beijing time ISO string.
    
    Args:
        utc_dt: UTC datetime object (naive or timezone-aware)
    
    Returns:
        ISO format string in Beijing timezone, or None if input is None
    """
    if not utc_dt:
        return None
    # Add UTC timezone info if naive, convert to Beijing, then format as ISO
    if utc_dt.tzinfo is None:
        utc_dt_tz = utc_dt.replace(tzinfo=timezone.utc)
    else:
        utc_dt_tz = utc_dt
    beijing_dt = utc_dt_tz.astimezone(BEIJING_TIMEZONE)
    return beijing_dt.isoformat()


# ============================================================================
# USER ACTIVITY TRACKING
# ============================================================================

def track_user_activity(
    user: User,
    activity_type: str,
    details: Optional[dict] = None,
    request: Optional[Request] = None
):
    """
    Track user activity for real-time monitoring.
    
    Args:
        user: User object
        activity_type: Type of activity (login, diagram_generation, etc.)
        details: Optional activity details
        request: Optional request object for IP address
    """
    try:
        from services.redis_activity_tracker import get_activity_tracker
        
        tracker = get_activity_tracker()
        ip_address = None
        if request and request.client:
            ip_address = request.client.host
        
        # For login activities, start a new session (or reuse existing)
        # For other activities, just record (will find/create session automatically)
        if activity_type == 'login':
            session_id = tracker.start_session(
                user_id=user.id,
                user_phone=user.phone,
                user_name=user.name,
                ip_address=ip_address,
                reuse_existing=True  # Reuse existing session if user already has one
            )
        else:
            session_id = None  # Let record_activity find/create session
        
        # Record activity
        tracker.record_activity(
            user_id=user.id,
            user_phone=user.phone,
            activity_type=activity_type,
            details=details or {},
            session_id=session_id,
            user_name=user.name
        )
    except Exception as e:
        # Don't fail the request if tracking fails
        logger.debug(f"Failed to track user activity: {e}")


def _record_city_flag_async(ip_address: str):
    """
    Record city flag asynchronously (fire-and-forget).
    
    This function schedules the city flag recording in a background task
    to avoid blocking the login request.
    """
    try:
        import asyncio
        from services.city_flag_tracker import get_city_flag_tracker
        from services.ip_geolocation import get_geolocation_service
        
        async def _record_flag():
            try:
                geolocation = get_geolocation_service()
                location = await geolocation.get_location(ip_address)
                if location and not location.get('is_fallback'):
                    city = location.get('city', '')
                    province = location.get('province', '')
                    lat = location.get('lat')
                    lng = location.get('lng')
                    if city or province:
                        flag_tracker = get_city_flag_tracker()
                        flag_tracker.record_city_flag(city, province, lat, lng)
            except Exception as e:
                logger.debug(f"Failed to record city flag: {e}")
        
        # Schedule async task (fire-and-forget)
        try:
            # Try to get the current event loop
            try:
                loop = asyncio.get_running_loop()
                # Event loop is running, create a task
                asyncio.create_task(_record_flag())
            except RuntimeError:
                # No running event loop, try to get/create one
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(_record_flag())
                    else:
                        loop.run_until_complete(_record_flag())
                except RuntimeError:
                    # No event loop available, create new one
                    asyncio.run(_record_flag())
        except Exception as e:
            logger.debug(f"Failed to schedule city flag recording: {e}")
    except Exception as e:
        logger.debug(f"Failed to schedule city flag recording: {e}")


# ============================================================================
# DATABASE RETRY LOGIC
# ============================================================================

async def commit_user_with_retry(
    db: Session,
    new_user: User,
    max_retries: int = 5
) -> int:
    """
    Commit user to SQLite with retry logic for database lock errors.
    
    Retries SQLite commits up to max_retries times with exponential backoff
    and jitter if database is locked. This handles transient lock errors during
    high concurrency scenarios (e.g., 500 concurrent registrations).
    
    Args:
        db: SQLAlchemy database session
        new_user: User object to commit
        max_retries: Maximum number of retry attempts (default: 5, increased from 3)
    
    Returns:
        Number of retries performed (0 = no retries, 1+ = retries)
    
    Raises:
        HTTPException: If commit fails after all retries or on non-lock errors
    """
    for attempt in range(max_retries):
        try:
            db.commit()
            db.refresh(new_user)  # Get auto-generated ID
            return attempt  # Return number of retries (0 = first attempt succeeded)
        except OperationalError as e:
            error_msg = str(e).lower()
            if "database is locked" in error_msg or "locked" in error_msg:
                if attempt < max_retries - 1:
                    # Retry with exponential backoff + jitter (prevents thundering herd)
                    base_delay = 0.1 * (2 ** attempt)  # 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
                    jitter = random.uniform(0, 0.05)  # Random jitter up to 50ms
                    delay = base_delay + jitter
                    logger.warning(
                        f"[Auth] SQLite lock on user registration attempt {attempt + 1}/{max_retries}, "
                        f"retrying after {delay:.3f}s delay (base: {base_delay:.3f}s + jitter: {jitter:.3f}s). "
                        f"Phone: {new_user.phone[:3] if new_user.phone and len(new_user.phone) >= 3 else '***'}***"
                    )
                    await asyncio.sleep(delay)  # Non-blocking async sleep
                    continue
                else:
                    # All retries exhausted
                    db.rollback()
                    logger.error(
                        f"[Auth] SQLite lock persists after {max_retries} retries. "
                        f"Phone: {new_user.phone[:3] if new_user.phone and len(new_user.phone) >= 3 else '***'}***"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Database temporarily unavailable due to high load. Please try again in a moment."
                    )
            else:
                # Other OperationalError (not a lock) - don't retry
                db.rollback()
                logger.error(f"[Auth] SQLite operational error during registration: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account"
                )
        except Exception as e:
            # Non-OperationalError - don't retry
            db.rollback()
            logger.error(f"[Auth] Failed to create user in SQLite: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account"
            )
    
    # Should never reach here, but just in case
    db.rollback()
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to create user account"
    )


# ============================================================================
# SESSION MANAGEMENT HELPERS
# ============================================================================

async def create_user_session(
    user: User,
    http_request: Request,
    cache_user_func: Optional[Callable[[], Awaitable[None]]] = None
) -> tuple[str, str]:
    """
    Create a new user session by invalidating old sessions and generating a new token.
    
    Args:
        user: User object
        http_request: FastAPI Request object
        cache_user_func: Optional async function to cache user (for registration)
    
    Returns:
        Tuple of (token, client_ip)
    """
    session_manager = get_session_manager()
    client_ip = http_request.client.host if http_request.client else "unknown"
    old_token_hash = session_manager.get_session_token(user.id)
    session_manager.invalidate_user_sessions(user.id, old_token_hash=old_token_hash, ip_address=client_ip)
    
    # Generate JWT token
    token = create_access_token(user)
    
    # Store new session in Redis
    session_manager.store_session(user.id, token)
    
    # If cache_user_func is provided (for registration), execute it in parallel
    if cache_user_func:
        await asyncio.gather(
            cache_user_func(),
            return_exceptions=True  # Don't fail if cache fails
        )
    
    return token, client_ip


# ============================================================================
# COOKIE MANAGEMENT HELPERS
# ============================================================================

def set_auth_cookies(response: Response, token: str, http_request: Request):
    """
    Set authentication cookies (access_token and show_ai_disclaimer).
    
    Args:
        response: FastAPI Response object
        token: JWT access token
        http_request: FastAPI Request object for HTTPS detection
    """
    # Set token as HTTP-only cookie
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=is_https(http_request),  # SECURITY: Auto-detect HTTPS
        samesite="lax",
        max_age=7 * 24 * 60 * 60  # 7 days
    )
    
    # Set flag cookie to indicate new login session (for AI disclaimer notification)
    response.set_cookie(
        key="show_ai_disclaimer",
        value="true",
        httponly=False,  # Allow JavaScript to read it
        secure=is_https(http_request),
        samesite="lax",
        max_age=60 * 60  # 1 hour (should be cleared after showing notification)
    )

