"""
JWT Token Management for MindGraph
Author: lycosa9527
Made by: MindSpring Team

JWT token creation, validation, and utilities.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Request, status
from fastapi.security import APIKeyHeader, HTTPBearer
from jose import JWTError, jwt

from .config import ACCESS_TOKEN_EXPIRY_MINUTES, JWT_ALGORITHM
from .jwt_secret import get_jwt_secret, get_jwt_secret_previous

logger = logging.getLogger(__name__)

# Security schemes for FastAPI dependency injection
security = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_access_token(user) -> str:
    """
    Create JWT access token for user

    Token payload includes:
    - sub: user_id
    - phone: user phone number
    - org_id: organization id
    - jti: JWT ID (unique token identifier for session tracking)
    - exp: expiration timestamp
    - type: token type (access)

    Args:
        user: User model object with id, phone, and organization_id attributes

    Returns:
        JWT token string
    """
    expire = datetime.now(tz=UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES)

    # Generate unique token ID for session tracking
    token_id = str(uuid.uuid4())

    payload = {
        "sub": str(user.id),
        "phone": user.phone or "",
        "email": getattr(user, "email", None) or "",
        "org_id": user.organization_id,
        "jti": token_id,
        "type": "access",
        "exp": expire,
    }

    token = jwt.encode(payload, get_jwt_secret(), algorithm=JWT_ALGORITHM)
    return token


def create_refresh_token(user_id: int) -> tuple[str, str]:
    """
    Create a secure refresh token

    Args:
        user_id: User ID (kept for API compatibility)

    Returns:
        tuple: (refresh_token, token_hash) - the raw token and its hash for storage
    """
    # user_id parameter kept for API compatibility but not used in implementation
    _ = user_id

    # Generate cryptographically secure random token
    refresh_token = secrets.token_urlsafe(32)

    # Hash for storage (never store the raw token)
    token_hash = hashlib.sha256(refresh_token.encode("utf-8")).hexdigest()

    return refresh_token, token_hash


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for lookup"""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


DEVICE_COOKIE_NAME = "mg_device"
_DEVICE_ID_HEX_CHARS = frozenset("0123456789abcdef")


def _is_device_id(value: str) -> bool:
    """True for a hex device id we issued (16-64 chars)."""
    if len(value) < 16 or len(value) > 64:
        return False
    return all(char in _DEVICE_ID_HEX_CHARS for char in value)


def read_device_cookie(request: Request) -> str:
    """Return the httpOnly device cookie, or empty if missing or malformed."""
    try:
        raw = str(request.cookies.get(DEVICE_COOKIE_NAME) or "").strip().lower()
    except (AttributeError, TypeError):
        return ""
    if _is_device_id(raw):
        return raw
    return ""


def header_device_fingerprint(request: Request) -> str:
    """Stable fallback when the device cookie is not on the request yet."""
    user_agent = request.headers.get("User-Agent", "")
    return hashlib.sha256(user_agent.encode("utf-8")).hexdigest()[:16]


def compute_device_hash(request: Request) -> str:
    """
    Identify this browser for refresh binding.

    Prefer the ``mg_device`` cookie (same jar and TTL as the refresh token).
    Header fingerprints are only a migration fallback: Accept-Encoding and
    Sec-CH-UA-* change between Chrome sessions and forced a daily re-login.
    """
    cookie_id = read_device_cookie(request)
    if cookie_id:
        return cookie_id
    return header_device_fingerprint(request)


def assign_device_id(request: Request) -> str:
    """Reuse the device cookie, or mint one on first login in this browser."""
    existing = read_device_cookie(request)
    if existing:
        return existing
    return secrets.token_hex(16)


def device_binding_matches(
    stored_device_hash: str,
    current_device_hash: str,
    stored_user_agent: str,
    current_user_agent: str,
) -> bool:
    """
    True when this refresh request is still the same browser.

    Cookie/hash equality is preferred. If the cookie is not on the request
    yet (deploy or cookie blocked), the stored User-Agent still identifies
    the browser so a 7-day refresh token is not thrown away.
    """
    if not stored_device_hash:
        return True
    if stored_device_hash == current_device_hash:
        return True
    stored_ua = stored_user_agent[:200]
    current_ua = current_user_agent[:200]
    return bool(stored_ua and current_ua and stored_ua == current_ua)


def decode_access_token(token: str) -> dict:
    """
    Decode and validate JWT token

    Args:
        token: JWT token string

    Returns:
        Token payload dict if valid

    Raises:
        HTTPException: If token is invalid or expired
    """
    secrets_to_try = [get_jwt_secret()]
    previous_secret = get_jwt_secret_previous()
    if previous_secret and previous_secret not in secrets_to_try:
        secrets_to_try.append(previous_secret)

    last_error: Optional[JWTError] = None
    for secret in secrets_to_try:
        try:
            payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        except JWTError as decode_error:
            last_error = decode_error
            continue

        if payload.get("type") != "access":
            logger.warning("Invalid token type in access token: %s", payload.get("type"))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return payload

    error = last_error if last_error is not None else JWTError("Invalid token")
    error_msg = str(error)
    if "expired" in error_msg.lower() or "exp" in error_msg.lower():
        logger.debug("Token expired: %s (expected when user inactive)", error)
    else:
        logger.warning("Invalid token: %s", error)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    ) from error
