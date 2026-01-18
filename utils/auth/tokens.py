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
from datetime import datetime, timedelta

from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, APIKeyHeader
from jose import JWTError, jwt

from .config import JWT_ALGORITHM, ACCESS_TOKEN_EXPIRY_MINUTES
from .jwt_secret import get_jwt_secret

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
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRY_MINUTES)

    # Generate unique token ID for session tracking
    token_id = str(uuid.uuid4())

    payload = {
        "sub": str(user.id),
        "phone": user.phone,
        "org_id": user.organization_id,
        "jti": token_id,
        "type": "access",
        "exp": expire
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
    token_hash = hashlib.sha256(refresh_token.encode('utf-8')).hexdigest()

    return refresh_token, token_hash


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for lookup"""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def compute_device_hash(request: Request) -> str:
    """
    Compute a device fingerprint hash from request headers.

    Uses multiple signals for more robust device identification:
    - User-Agent: Browser and OS identification
    - Accept-Language: Language preferences
    - Accept-Encoding: Compression support (stable across sessions)
    - Sec-CH-UA-Platform: Client hint for OS platform (if available)
    - Sec-CH-UA-Mobile: Client hint for mobile/desktop (if available)

    Note: We deliberately exclude IP address as it can change frequently
    (e.g., mobile networks, VPN). The goal is to identify the same browser
    on the same device, not the network location.

    Args:
        request: FastAPI Request object

    Returns:
        16-character hash string
    """
    # Core headers (always present)
    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    accept_encoding = request.headers.get("Accept-Encoding", "")

    # Client hints (modern browsers only, more stable than User-Agent)
    sec_ch_platform = request.headers.get("Sec-CH-UA-Platform", "")
    sec_ch_mobile = request.headers.get("Sec-CH-UA-Mobile", "")

    # Build fingerprint from stable signals
    fingerprint_parts = [
        user_agent,
        accept_language,
        accept_encoding,
        sec_ch_platform,
        sec_ch_mobile
    ]

    fingerprint_str = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint_str.encode('utf-8')).hexdigest()[:16]


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
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        # Token expiration is expected behavior when users are inactive
        # Log at DEBUG level to reduce noise, but still log invalid tokens as WARNING
        error_msg = str(e)
        if "expired" in error_msg.lower() or "exp" in error_msg.lower():
            logger.debug("Token expired: %s (expected when user inactive)", e)
        else:
            logger.warning("Invalid token: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        ) from e
