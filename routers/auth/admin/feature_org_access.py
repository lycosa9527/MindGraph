"""
Admin API for DB-backed per-feature organization and user access rules.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.feature_org_access import FeatureOrgAccessEntry
from routers.auth.dependencies import require_admin
from services.feature_access.repository import (
    load_feature_org_access_session,
    replace_feature_org_access,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/feature-org-access")
async def get_feature_org_access_admin(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Return all feature access rules (admin only)."""
    data = await load_feature_org_access_session(db)
    logger.info("Admin %s read feature org access (%d keys)", current_user.phone, len(data))
    return data


@router.put("/admin/feature-org-access")
async def put_feature_org_access_admin(
    body: Dict[str, FeatureOrgAccessEntry],
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_async_db),
):
    """Replace feature access rules (admin only)."""
    try:
        await replace_feature_org_access(db, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    logger.info(
        "Admin %s updated feature org access (%d keys)",
        current_user.phone,
        len(body),
    )
    return {"message": "Feature org access updated", "keys": list(body.keys())}
