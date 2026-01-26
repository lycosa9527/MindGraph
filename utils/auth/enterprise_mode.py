"""
Enterprise Mode Authentication for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Enterprise mode bypasses JWT validation for VPN/SSO deployments.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import datetime

from fastapi import HTTPException, status

from config.database import SessionLocal
from models.domain.auth import User, Organization
from .config import ENTERPRISE_DEFAULT_ORG_CODE, ENTERPRISE_DEFAULT_USER_PHONE
from .password import hash_password

logger = logging.getLogger(__name__)

# Redis modules (optional)
_REDIS_AVAILABLE = False
_org_cache = None
_user_cache = None

try:
    from services.redis.cache.redis_org_cache import org_cache
    from services.redis.cache.redis_user_cache import user_cache
    _REDIS_AVAILABLE = True
    _org_cache = org_cache
    _user_cache = user_cache
except ImportError:
    pass


def get_enterprise_user() -> User:
    """
    Get or create the enterprise mode user.

    Enterprise mode skips JWT validation entirely - this is for deployments
    behind VPN/SSO where network-level authentication is sufficient.

    Returns:
        User object for enterprise mode

    Raises:
        HTTPException: If enterprise organization not found
    """
    db = SessionLocal()
    try:
        # Use cache for org lookup (with SQLite fallback)
        org = None
        if _REDIS_AVAILABLE and _org_cache is not None:
            org = _org_cache.get_by_code(ENTERPRISE_DEFAULT_ORG_CODE)

        if not org:
            org = db.query(Organization).filter(
                Organization.code == ENTERPRISE_DEFAULT_ORG_CODE
            ).first()
            if not org:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Enterprise organization {ENTERPRISE_DEFAULT_ORG_CODE} not found"
                )

        # Use cache for user lookup (with SQLite fallback)
        user = None
        if _REDIS_AVAILABLE and _user_cache:
            user = _user_cache.get_by_phone(ENTERPRISE_DEFAULT_USER_PHONE)

        if not user:
            # Check if user exists in database
            user = db.query(User).filter(
                User.phone == ENTERPRISE_DEFAULT_USER_PHONE
            ).first()

            if not user:
                # Auto-create enterprise user
                user = User(
                    phone=ENTERPRISE_DEFAULT_USER_PHONE,
                    password_hash=hash_password("ent-no-pwd"),
                    name="Enterprise User",
                    organization_id=org.id,
                    created_at=datetime.utcnow()
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info("Created enterprise mode user")

            # Cache the user (non-blocking)
            try:
                if _REDIS_AVAILABLE and _user_cache:
                    _user_cache.cache_user(user)
            except Exception as e:
                logger.warning("Failed to cache enterprise user: %s", e)

        return user
    finally:
        db.close()
