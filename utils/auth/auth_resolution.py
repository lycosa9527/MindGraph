"""
Resolve authenticated User once per HTTP request for middleware and dependencies.

Populates request.state.auth_context_user in auth_context_middleware when a valid
JWT session or mgat_ token is present. get_current_user prefers this to avoid
duplicate session validation and mgat_ lookups.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Optional

from fastapi import HTTPException, Request, status

from models.domain.auth import User
from services.auth.http_auth_token import extract_bearer_token
from utils.auth.config import AUTH_MODE
from utils.auth.datetime_compat import as_utc_aware
from utils.auth.tokens import decode_access_token
from utils.auth.user_tokens import validate_user_token

AUTH_CONTEXT_USER_ATTR = "auth_context_user"

_redis = SimpleNamespace(
    available=False,
    get_session_manager=None,
    user_cache=None,
)

try:
    from services.redis.session.redis_session_manager import get_session_manager
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache

    _redis.available = True
    _redis.get_session_manager = get_session_manager
    _redis.user_cache = redis_user_cache
except ImportError:
    pass


async def raise_if_org_locked_or_expired_async(user: User) -> None:
    """Raise HTTPException if org is locked or subscription expired."""
    if not user.organization_id:
        return
    org = None
    try:
        from services.redis.cache.redis_org_cache import org_cache

        if org_cache:
            org = await org_cache.get_by_id(user.organization_id)
    except ImportError:
        org = None
    if org:
        is_active = org.is_active if hasattr(org, "is_active") else True
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization account is locked. Please contact support.",
            )
        if hasattr(org, "expires_at") and org.expires_at:
            if as_utc_aware(org.expires_at) < datetime.now(UTC):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Organization subscription has expired. Please contact support.",
                )


async def resolve_authenticated_user_optional(request: Request) -> Optional[User]:
    """
    Return User when Bearer/cookie token is a valid JWT session or mgat_ pair.
    Returns None when unauthenticated, invalid, or enterprise mode (no JWT layer).
    """
    if AUTH_MODE == "enterprise":
        return None
    token = extract_bearer_token(request)
    if not token:
        return None
    if token.startswith("mgat_"):
        account = (request.headers.get("X-MG-Account") or "").strip()
        if not account:
            return None
        try:
            return await validate_user_token(token, account, request=request)
        except HTTPException:
            return None
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    if not _redis.available or _redis.get_session_manager is None:
        return None
    session_manager = _redis.get_session_manager()
    if not await session_manager.is_session_valid(int(user_id), token):
        return None
    if _redis.user_cache is None:
        return None
    return await _redis.user_cache.get_by_id(int(user_id))


async def load_user_from_jwt_session_token(token: str) -> Optional[User]:
    """
    Resolve User from a JWT access token (session + user cache). Not for mgat_.
    Returns None when invalid, expired, or cache miss.
    """
    try:
        payload = decode_access_token(token)
    except HTTPException:
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None
    if not _redis.available or _redis.get_session_manager is None:
        return None
    session_manager = _redis.get_session_manager()
    if not await session_manager.is_session_valid(int(user_id), token):
        return None
    if _redis.user_cache is None:
        return None
    return await _redis.user_cache.get_by_id(int(user_id))
