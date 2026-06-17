"""Validation for user-scoped API tokens (mgat_ prefix)."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Optional

from fastapi import HTTPException, Request, status
from sqlalchemy import select

from models.domain.auth import User
from models.domain.messages import Messages, get_request_language
from models.domain.user_api_token import UserAPIToken
from services.redis.cache.redis_user_token_cache import user_token_cache
from services.utils.error_types import BACKGROUND_INFRA_ERRORS

try:
    from services.redis.cache.redis_org_cache import org_cache
    from services.redis.cache.redis_user_cache import user_cache
except ImportError:
    org_cache = None
    user_cache = None

from utils.auth.org_subscription import ensure_org_subscription_current
from utils.auth.request_helpers import get_client_ip
from utils.auth.school_tier import TIER_FEATURE_API_TOKEN, user_has_school_tier_feature
from utils.db.session_open import system_rls_session, user_rls_session

logger = logging.getLogger(__name__)

_redis = SimpleNamespace(available=False, user_cache=None, org_cache=None)

if user_cache is not None:
    _redis.available = True
    _redis.user_cache = user_cache
    _redis.org_cache = org_cache


async def _load_user(user_id: int) -> Optional[User]:
    """Load user."""
    if _redis.available and _redis.user_cache:
        user = await _redis.user_cache.get_by_id(int(user_id))
        if user:
            return user
    async with user_rls_session(int(user_id)) as db:
        result = await db.execute(select(User).where(User.id == int(user_id)))
        row = result.scalar_one_or_none()
        if row and _redis.available and _redis.user_cache:
            await _redis.user_cache.cache_user(row)
        return row


async def _check_org_access_async(user: User) -> None:
    """Check org access async."""
    if not user.organization_id:
        return
    if not _redis.available or not _redis.org_cache:
        return
    org_row = await _redis.org_cache.get_by_id(user.organization_id)
    if not org_row:
        return
    is_active = org_row.is_active if hasattr(org_row, "is_active") else True
    if not is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization account is locked. Please contact support.",
        )
    await ensure_org_subscription_current(org_row)


def _log_mgat_audit(request: Optional[Request], user_id: int) -> None:
    """Emit TokenAudit line for mgat_ validation (OpenClaw, Chrome extension, etc.)."""
    if request is None:
        return
    if getattr(request.state, "_mgat_audit_logged", False):
        return
    setattr(request.state, "_mgat_audit_logged", True)
    raw_client = (request.headers.get("X-MG-Client") or "").strip()
    client = raw_client[:64] if raw_client else "unspecified"
    ip = get_client_ip(request)
    path = request.url.path
    logger.info(
        "[TokenAudit] mgat validated: user=%s, ip=%s, client=%s, path=%s",
        user_id,
        ip,
        client,
        path,
    )


async def validate_user_token(
    token: str,
    account_number: str,
    request: Optional[Request] = None,
) -> User:
    """
    Validate mgat_ token + account phone binding.

    Raises HTTPException on any failure (generic 401 for auth failures).
    """
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    account_number = (account_number or "").strip()
    if not account_number:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-MG-Account header required with API token",
        )

    token_hash_full = hashlib.sha256(token.encode("utf-8")).hexdigest()
    user_id: Optional[int] = None
    record: Optional[UserAPIToken] = None

    cached = await user_token_cache.get_by_raw_token(token)
    if cached:
        if user_token_cache.is_expired(cached) or not cached.get("is_active", True):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        user_id = int(cached["user_id"])
    else:
        async with system_rls_session() as db:
            result = await db.execute(
                select(UserAPIToken).where(
                    UserAPIToken.token_hash == token_hash_full,
                    UserAPIToken.is_active.is_(True),
                    UserAPIToken.expires_at > datetime.now(UTC),
                )
            )
            record = result.scalar_one_or_none()
            if not record:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
            user_id = record.user_id
            await user_token_cache.set_from_row(token, record)
            record.last_used_at = datetime.now(UTC)
            try:
                await db.commit()
            except BACKGROUND_INFRA_ERRORS:
                await db.rollback()
                logger.debug("[UserToken] last_used_at update failed", exc_info=True)

    user = await _load_user(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    if user.phone != account_number:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    await _check_org_access_async(user)
    async with user_rls_session(int(user.id), getattr(user, "organization_id", None)) as db:
        allowed = await user_has_school_tier_feature(db, user, TIER_FEATURE_API_TOKEN)
    if not allowed:
        lang = "zh"
        if request is not None:
            lang = get_request_language(
                request.headers.get("X-Language"),
                request.headers.get("Accept-Language", ""),
            )
        error_msg = Messages.error("school_tier_feature_unavailable", lang)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    _log_mgat_audit(request, user.id)
    return user
