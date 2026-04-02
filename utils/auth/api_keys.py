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


async def validate_api_key(api_key: str, db: AsyncSession) -> bool:
    """
    Validate API key and check quota

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

    return True


async def track_api_key_usage(api_key: str, db: AsyncSession) -> None:
    """
    Increment usage counter for API key

    Args:
        api_key: API key string
        db: Async database session
    """
    try:
        result = await db.execute(select(APIKey).where(APIKey.key == api_key))
        key_record = result.scalar_one_or_none()
        if key_record:
            key_record.usage_count += 1
            key_record.last_used_at = datetime.now(UTC)
            await db.commit()
            quota_info = key_record.quota_limit or "unlimited"
            logger.debug(
                "[Auth] API key used: %s (usage: %s/%s)",
                key_record.name,
                key_record.usage_count,
                quota_info,
            )
        else:
            logger.warning("[Auth] API key usage tracking failed: key record not found")
    except Exception as exc:
        logger.error("[Auth] Failed to track API key usage: %s", exc, exc_info=True)


async def generate_api_key(name: str, description: str, quota_limit: Optional[int], db: AsyncSession) -> str:
    """
    Generate a new API key

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
    await db.commit()
    await db.refresh(api_key_record)

    quota_info = quota_limit or "unlimited"
    logger.info("Generated API key: %s (quota: %s)", name, quota_info)

    return key
