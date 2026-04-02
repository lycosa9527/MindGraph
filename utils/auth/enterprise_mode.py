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

from config.database import SyncSessionLocal
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


def get_enterprise_user() -> User:
    """
    Get or create the enterprise mode user.

    Skips JWT validation entirely. Callers must ensure the service is deployed
    behind network isolation; do not rely on this mode for Internet-facing hosts.

    Returns:
        User object for enterprise mode

    Raises:
        HTTPException: If enterprise organization not found
    """
    db = SyncSessionLocal()
    try:
        org = db.query(Organization).filter(Organization.code == ENTERPRISE_DEFAULT_ORG_CODE).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Enterprise organization {ENTERPRISE_DEFAULT_ORG_CODE} not found",
            )

        user = db.query(User).filter(User.phone == ENTERPRISE_DEFAULT_USER_PHONE).first()

        if not user:
            # Auto-create enterprise user
            user = User(
                phone=ENTERPRISE_DEFAULT_USER_PHONE,
                password_hash=hash_password("ent-no-pwd"),
                name="Enterprise User",
                organization_id=org.id,
                created_at=datetime.now(tz=UTC),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created enterprise mode user")

        return user
    finally:
        db.close()
