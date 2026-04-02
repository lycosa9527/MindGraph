"""Admin API for DB-backed per-feature organization and user access rules."""

import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from models.domain.auth import User
from models.domain.feature_org_access import FeatureOrgAccessEntry
from services.feature_access.repository import (
    load_feature_org_access_session,
    replace_feature_org_access,
)
from utils.auth import get_current_user, is_admin

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/admin/feature-org-access")
async def get_feature_org_access_admin(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Return all feature access rules (admin only)."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    data = await db.run_sync(load_feature_org_access_session)
    logger.info("Admin %s read feature org access (%d keys)", current_user.phone, len(data))
    return data


@router.put("/admin/feature-org-access")
async def put_feature_org_access_admin(
    body: Dict[str, FeatureOrgAccessEntry],
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """Replace feature access rules (admin only)."""
    if not is_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    try:
        await db.run_sync(lambda session: replace_feature_org_access(session, body))
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
