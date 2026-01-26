"""
API Key Management for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Functions for managing API keys for external integrations.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import secrets
from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.domain.auth import APIKey

logger = logging.getLogger(__name__)


def validate_api_key(api_key: str, db: Session) -> bool:
    """
    Validate API key and check quota

    Args:
        api_key: API key string
        db: Database session

    Returns:
        True if valid and within quota

    Raises:
        HTTPException: If quota exceeded or key expired
    """
    if not api_key:
        return False

    # Query database for key
    key_record = db.query(APIKey).filter(
        APIKey.key == api_key,
        APIKey.is_active.is_(True)
    ).first()

    if not key_record:
        logger.warning("Invalid API key attempted: %s...", api_key[:12])
        return False

    # Check expiration
    if key_record.expires_at and key_record.expires_at < datetime.utcnow():
        logger.warning("Expired API key used: %s", key_record.name)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired"
        )

    # Check quota
    if key_record.quota_limit and key_record.usage_count >= key_record.quota_limit:
        logger.warning("API key quota exceeded: %s", key_record.name)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"API key quota exceeded. Limit: {key_record.quota_limit}"
        )

    return True


def track_api_key_usage(api_key: str, db: Session) -> None:
    """
    Increment usage counter for API key

    Args:
        api_key: API key string
        db: Database session
    """
    try:
        key_record = db.query(APIKey).filter(APIKey.key == api_key).first()
        if key_record:
            key_record.usage_count += 1
            key_record.last_used_at = datetime.utcnow()
            db.commit()
            quota_info = key_record.quota_limit or 'unlimited'
            logger.debug(
                "[Auth] API key used: %s (usage: %s/%s)",
                key_record.name, key_record.usage_count, quota_info
            )
        else:
            logger.warning("[Auth] API key usage tracking failed: key record not found")
    except Exception as e:
        logger.error("[Auth] Failed to track API key usage: %s", e, exc_info=True)


def generate_api_key(
    name: str,
    description: str,
    quota_limit: Optional[int],
    db: Session
) -> str:
    """
    Generate a new API key

    Args:
        name: Name for the key (e.g., "Dify Integration")
        description: Description of the key's purpose
        quota_limit: Maximum number of requests (None = unlimited)
        db: Database session

    Returns:
        Generated API key string (mg_...)
    """
    # Generate secure random key with MindGraph prefix
    key = f"mg_{secrets.token_urlsafe(32)}"

    # Create database record
    api_key_record = APIKey(
        key=key,
        name=name,
        description=description,
        quota_limit=quota_limit,
        usage_count=0,
        is_active=True,
        created_at=datetime.utcnow()
    )

    db.add(api_key_record)
    db.commit()
    db.refresh(api_key_record)

    quota_info = quota_limit or 'unlimited'
    logger.info("Generated API key: %s (quota: %s)", name, quota_info)

    return key
