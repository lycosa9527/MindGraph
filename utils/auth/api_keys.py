"""
API Key Management for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions for managing API keys for external integrations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import hashlib
import logging
import secrets
from datetime import UTC, datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import APIKey

logger = logging.getLogger(__name__)

# API key cache (optional — gracefully degrades if Redis is unavailable)
_api_key_cache = None

try:
    from services.redis.cache.redis_api_key_cache import api_key_cache as _api_key_cache_instance

    _api_key_cache = _api_key_cache_instance
except ImportError:
    pass


async def validate_api_key(api_key: str, db: AsyncSession) -> bool:
    """
    Validate API key and check quota.

    Tries Redis cache first (TTL 5 min); falls back to Postgres on miss.
    Populates the cache on every DB read so subsequent requests skip the DB.

    Args:
        api_key: API key string
        db: Async database session

    Returns:
        True if valid and within quota

    Raises:
        HTTPException: If quota exceeded or key expired
    """
    if not api_key:
        return False

    # Redis-first: skip DB entirely on cache hit.
    if _api_key_cache:
        cached = _api_key_cache.get(api_key)
        if cached is not None:
            if not cached.get("is_active"):
                fp = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
                logger.warning("Invalid (inactive) cached API key (sha256_16=%s)", fp)
                return False
            if _api_key_cache.is_expired(cached):
                logger.warning("Expired cached API key used: %s", cached.get("name"))
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="API key has expired",
                )
            quota_limit = cached.get("quota_limit")
            usage_count = cached.get("usage_count", 0)
            if quota_limit and usage_count >= quota_limit:
                logger.warning("Cached API key quota exceeded: %s", cached.get("name"))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"API key quota exceeded. Limit: {quota_limit}",
                )
            return True

    # Cache miss: fall through to Postgres.
    result = await db.execute(select(APIKey).where(APIKey.key == api_key, APIKey.is_active.is_(True)))
    key_record = result.scalar_one_or_none()

    if not key_record:
        fp = hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]
        logger.warning("Invalid API key attempted (sha256_16=%s)", fp)
        return False

    if key_record.expires_at and key_record.expires_at < datetime.now(UTC):
        logger.warning("Expired API key used: %s", key_record.name)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key has expired")

    if key_record.quota_limit and key_record.usage_count >= key_record.quota_limit:
        logger.warning("API key quota exceeded: %s", key_record.name)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API key quota exceeded. Limit: {key_record.quota_limit}",
        )

    # Populate cache for future requests.
    if _api_key_cache:
        _api_key_cache.set(api_key, key_record)

    return True


async def get_api_key_record(api_key: str, db: AsyncSession) -> Optional[APIKey]:
    """
    Return the APIKey ORM record for ``api_key``.

    Uses the Redis cache when available so callers (e.g. authentication.py)
    do not need a second DB query after validate_api_key().

    Args:
        api_key: API key string
        db: Async database session

    Returns:
        APIKey record or None
    """
    if _api_key_cache:
        cached = _api_key_cache.get(api_key)
        if cached is not None:
            # Reconstruct a lightweight object from cached data so callers can
            # read .id and .name without hitting the DB again.
            record = APIKey()
            record.id = cached["id"]
            record.key = cached["key"]
            record.name = cached["name"]
            record.is_active = cached["is_active"]
            record.quota_limit = cached["quota_limit"]
            record.usage_count = cached["usage_count"]
            return record

    result = await db.execute(select(APIKey).where(APIKey.key == api_key))
    return result.scalar_one_or_none()


async def track_api_key_usage(api_key: str, db: AsyncSession) -> None:
    """
    Increment usage counter for API key.

    Uses Redis INCR (O(1), non-blocking) when available so the hot path never
    blocks on a DB write.  Falls back to a direct Postgres update if Redis is
    unavailable or the cache module is not installed.

    Args:
        api_key: API key string
        db: Async database session
    """
    if _api_key_cache:
        # Attempt to get the key ID from cache to avoid a DB lookup.
        cached = _api_key_cache.get(api_key)
        if cached is not None:
            key_id = cached["id"]
            _api_key_cache.incr_usage(key_id)
            logger.debug("[Auth] API key usage tracked via Redis INCR: id=%s", key_id)
            return

    # Redis unavailable or cache miss: fall back to direct DB update.
    try:
        result = await db.execute(select(APIKey).where(APIKey.key == api_key))
        key_record = result.scalar_one_or_none()
        if key_record:
            key_record.usage_count += 1
            key_record.last_used_at = datetime.now(UTC)
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                raise
            logger.debug(
                "[Auth] API key used: %s (usage: %s/%s)",
                key_record.name,
                key_record.usage_count,
                key_record.quota_limit or "unlimited",
            )
        else:
            logger.warning("[Auth] API key usage tracking failed: key record not found")
    except Exception as exc:
        logger.error("[Auth] Failed to track API key usage: %s", exc, exc_info=True)


async def generate_api_key(
    name: str, description: str, quota_limit: Optional[int], db: AsyncSession
) -> str:
    """
    Generate a new API key.

    Args:
        name: Name for the key (e.g., "Dify Integration")
        description: Description of the key's purpose
        quota_limit: Maximum number of requests (None = unlimited)
        db: Async database session

    Returns:
        Generated API key string (mg_...)
    """
    key = f"mg_{secrets.token_urlsafe(32)}"

    api_key_record = APIKey(
        key=key,
        name=name,
        description=description,
        quota_limit=quota_limit,
        usage_count=0,
        is_active=True,
        created_at=datetime.now(UTC),
    )

    db.add(api_key_record)
    try:
        await db.commit()
        await db.refresh(api_key_record)
    except Exception:
        await db.rollback()
        raise

    quota_info = quota_limit or "unlimited"
    logger.info("Generated API key: %s (quota: %s)", name, quota_info)

    return key
