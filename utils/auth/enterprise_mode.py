"""
Enterprise Mode Authentication for MindGraph
Author: lycosa9527
Made by: MindSpring Team

Enterprise mode bypasses JWT validation. Every HTTP request is treated as the same
preconfigured enterprise user. Use only when the deployment is unreachable from
the public Internet (e.g. VPN-only, private LAN, zero-trust with network-level auth).
Misconfiguration on a public host grants full API access to anonymous clients.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select

from config.database import AsyncSessionLocal
from models.domain.auth import User, Organization
from .config import ENTERPRISE_DEFAULT_ORG_CODE, ENTERPRISE_DEFAULT_USER_PHONE
from .password import hash_password

logger = logging.getLogger(__name__)

# Redis modules (optional)
_redis_available = False
_org_cache = None
_user_cache = None

try:
    from services.redis.cache.redis_org_cache import org_cache
    from services.redis.cache.redis_user_cache import user_cache

    _redis_available = True
    _org_cache = org_cache
    _user_cache = user_cache
except ImportError:
    pass


async def get_enterprise_user() -> User:
    """
    Get or create the enterprise mode user.

    Skips JWT validation entirely. Callers must ensure the service is deployed
    behind network isolation; do not rely on this mode for Internet-facing hosts.

    Returns:
        User object for enterprise mode

    Raises:
        HTTPException: If enterprise organization not found
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Organization).where(Organization.code == ENTERPRISE_DEFAULT_ORG_CODE)
        )
        org = result.scalar_one_or_none()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Enterprise organization {ENTERPRISE_DEFAULT_ORG_CODE} not found",
            )

        result = await db.execute(
            select(User).where(User.phone == ENTERPRISE_DEFAULT_USER_PHONE)
        )
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                phone=ENTERPRISE_DEFAULT_USER_PHONE,
                password_hash=hash_password("ent-no-pwd"),
                name="Enterprise User",
                organization_id=org.id,
                created_at=datetime.now(tz=UTC),
            )
            db.add(user)
            try:
                await db.commit()
                await db.refresh(user)
            except Exception:
                await db.rollback()
                raise
            logger.info("Created enterprise mode user")

        return user
