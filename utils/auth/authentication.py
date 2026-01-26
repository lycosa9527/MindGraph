"""
Main Authentication Functions for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Core authentication functions for user authentication via JWT tokens.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import time
from datetime import datetime
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config.database import SessionLocal
from models.domain.auth import User, APIKey
from .config import AUTH_MODE, JWT_ALGORITHM
from .jwt_secret import get_jwt_secret
from .tokens import security, api_key_header, decode_access_token
from .api_keys import validate_api_key, track_api_key_usage
from .enterprise_mode import get_enterprise_user

logger = logging.getLogger(__name__)

# Redis modules (optional)
_REDIS_AVAILABLE = False
_get_session_manager = None
_hash_token = None
_user_cache = None
_org_cache = None

try:
    from services.redis.session.redis_session_manager import get_session_manager, _hash_token as redis_hash_token
    from services.redis.cache.redis_user_cache import user_cache
    from services.redis.cache.redis_org_cache import org_cache
    _REDIS_AVAILABLE = True
    _get_session_manager = get_session_manager
    _hash_token = redis_hash_token
    _user_cache = user_cache
    _org_cache = org_cache
except ImportError:
    pass


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> User:
    """
    Get current authenticated user from JWT token (Authorization header or cookie)

    Supports four authentication modes:
    1. standard: Regular JWT authentication (phone/password login)
    2. enterprise: Skip JWT validation (for VPN/SSO deployments)
    3. demo: Regular JWT authentication (passkey login)
    4. bayi: Regular JWT authentication (token-based login via /loginByXz)

    IMPORTANT: Demo and bayi modes still require valid JWT tokens!
    Only enterprise mode bypasses authentication entirely.

    Authentication methods (in order of priority):
    1. Authorization: Bearer <token> header
    2. access_token cookie (for cookie-based authentication)

    Args:
        request: FastAPI Request object
        credentials: HTTP Bearer credentials (injected by FastAPI)

    Returns:
        User object if authenticated

    Raises:
        HTTPException: If authentication fails
    """
    # Enterprise Mode: Skip authentication, return enterprise user
    if AUTH_MODE == "enterprise":
        return get_enterprise_user()

    # Standard, Demo, and Bayi Mode: Validate JWT token
    token = None

    # Priority 1: Check Authorization header
    if credentials:
        token = credentials.credentials
    # Priority 2: Check cookie if no Authorization header
    elif request:
        token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT token required for this endpoint"
        )

    payload = decode_access_token(token)

    user_id = payload.get("sub")
    token_exp = payload.get("exp", 0)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )

    # Session validation: Check if session exists in Redis
    if not _REDIS_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis is required for session validation"
        )
    if _get_session_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Session manager not available"
        )
    if _hash_token is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Token hashing not available"
        )

    session_manager = _get_session_manager()
    token_hash = _hash_token(token)

    # DEBUG: Log session validation attempt
    now = int(time.time())
    exp_info = f"exp={token_exp}, expired_ago={(now - token_exp) if token_exp > 0 else 'unknown'}s"
    logger.debug(
        "[Auth] get_current_user session check: user=%s, token=%s..., %s",
        user_id, token_hash[:8], exp_info
    )

    if not session_manager.is_session_valid(int(user_id), token):
        logger.info(
            "[Auth] get_current_user FAILED: user=%s, token=%s... - session invalid",
            user_id, token_hash[:8]
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalidated. Please login again."
        )

    logger.debug("[Auth] get_current_user session VALID: user=%s", user_id)

    # Use cache for user lookup
    user = None
    if _REDIS_AVAILABLE and _user_cache:
        user = _user_cache.get_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    # Check organization status (locked or expired) using cache
    if user.organization_id:
        org = None
        if _REDIS_AVAILABLE and _org_cache:
            org = _org_cache.get_by_id(user.organization_id)
        if org:
            # Check if organization is locked
            is_active = org.is_active if hasattr(org, 'is_active') else True
            if not is_active:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization account is locked. Please contact support."
                )

            # Check if organization subscription has expired
            if hasattr(org, 'expires_at') and org.expires_at:
                if org.expires_at < datetime.utcnow():
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Organization subscription has expired. Please contact support."
                    )

    return user


def get_user_from_cookie(token: str, db: Session) -> Optional[User]:
    """
    Get user from cookie token without HTTPBearer dependency

    Used for page routes to verify authentication from cookies.
    Returns User if valid token, None if invalid/expired.

    Args:
        token: JWT token string
        db: Database session

    Returns:
        User object if valid, None otherwise
    """
    if not token:
        return None

    try:
        # Decode token - jwt.decode automatically validates expiration
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")

        if not user_id:
            return None

        # Session validation: Check if session exists in Redis
        if not _REDIS_AVAILABLE:
            return None
        if _get_session_manager is None:
            return None

        session_manager = _get_session_manager()
        if not session_manager.is_session_valid(int(user_id), token):
            logger.debug("Session invalid for user %s in get_user_from_cookie", user_id)
            return None

        # Use cache for user lookup (with SQLite fallback)
        user = None
        if _user_cache:
            user = _user_cache.get_by_id(int(user_id))
        if not user:
            # Fallback to DB if not in cache
            user = db.query(User).filter(User.id == int(user_id)).first()
            if user:
                db.expunge(user)
                if _user_cache:
                    _user_cache.cache_user(user)
        return user

    except JWTError as e:
        error_msg = str(e).lower()
        if "expired" in error_msg or "exp" in error_msg:
            logger.debug("Expired cookie token: %s", e)
        else:
            logger.debug("Invalid cookie token: %s", e)
        return None
    except Exception as e:
        logger.error("Error validating cookie token: %s", e, exc_info=True)
        return None


def get_current_user_or_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    api_key: str = Depends(api_key_header)
) -> Optional[User]:
    """
    Get current user from JWT token OR validate API key

    Priority:
    1. JWT token (Authorization header or cookie) - Returns User object
    2. API key (Dify, public API) - Returns None (but validates key)
    3. No auth - Raises 401 error

    Args:
        request: FastAPI Request object
        credentials: HTTP Bearer credentials
        api_key: API key from header

    Returns:
        User object if JWT valid, None if API key valid

    Raises:
        HTTPException(401): If both invalid
    """
    # Priority 1: Try JWT token (for authenticated teachers)
    token = None

    # Check Authorization header first
    if credentials:
        token = credentials.credentials
    # Check cookie if no Authorization header
    elif request:
        token = request.cookies.get("access_token")

    if token:
        try:
            payload = decode_access_token(token)
            user_id = payload.get("sub")

            if user_id:
                # Session validation: Check if session exists in Redis
                if not _REDIS_AVAILABLE:
                    user = None
                elif _get_session_manager is None:
                    user = None
                else:
                    session_manager = _get_session_manager()
                    if session_manager.is_session_valid(int(user_id), token):
                        # Use cache for user lookup (with SQLite fallback)
                        if _user_cache is not None:
                            user = _user_cache.get_by_id(int(user_id))
                        else:
                            user = None
                    else:
                        user = None

                if user:
                    worker_id = os.getenv('UVICORN_WORKER_ID', 'main')
                    endpoint = request.url.path if request else 'unknown'
                    logger.debug(
                        "Authenticated teacher: %s (ID: %d, Phone: %s) [Worker: %s] [%s]",
                        user.name, user.id, user.phone, worker_id, endpoint
                    )
                    return user  # Authenticated teacher - full access
        except HTTPException:
            # Invalid JWT, try API key instead
            pass

    # Priority 2: Try API key (for Dify, public API users)
    if api_key:
        db = SessionLocal()
        try:
            if validate_api_key(api_key, db):
                # Get API key record to store ID in request state
                key_record = db.query(APIKey).filter(APIKey.key == api_key).first()

                if key_record:
                    if request and hasattr(request, 'state'):
                        request.state.api_key_id = key_record.id
                        request.state.api_key_name = key_record.name
                        logger.debug(
                            "[Auth] Stored API key ID %d in request state",
                            key_record.id
                        )
                    else:
                        logger.warning(
                            "[Auth] Request state not available, cannot store api_key_id"
                        )

                    track_api_key_usage(api_key, db)
                    endpoint = request.url.path if request else 'unknown'
                    logger.info(
                        "[Auth] Valid API key access: %s (ID: %d) [%s]",
                        key_record.name, key_record.id, endpoint
                    )
                else:
                    logger.warning(
                        "[Auth] API key validated but record not found in database"
                    )
                    track_api_key_usage(api_key, db)
                    logger.info("[Auth] Valid API key access (record lookup failed)")

                return None  # Valid API key, no user object
        finally:
            db.close()

    # No valid authentication
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required: provide JWT token (Authorization: Bearer) "
               "or API key (X-API-Key header)"
    )
