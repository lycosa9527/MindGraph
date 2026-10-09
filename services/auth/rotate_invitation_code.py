"""Replace an organization's invitation code and refresh the org cache.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional, cast

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from services.redis.cache.redis_org_cache import org_cache
from services.utils.error_types import DATABASE_ERRORS
from utils.invitations import generate_invitation_code

logger = logging.getLogger(__name__)


async def _invitation_code_taken(db: AsyncSession, org: Organization, code: str) -> bool:
    """True when another organization already uses this invitation code."""
    cached = await org_cache.get_by_invitation_code(code)
    if cached is not None:
        return cast(int, cached.id) != cast(int, org.id)
    other = (
        await db.execute(
            select(Organization).where(
                Organization.invitation_code == code,
                Organization.id != org.id,
            )
        )
    ).scalar_one_or_none()
    return other is not None


async def rotate_organization_invitation_code(
    db: AsyncSession,
    org: Organization,
    lang: Language,
) -> str:
    """Persist a new unique invitation code. The previous code stops working."""
    old_invite = cast(Optional[str], org.invitation_code)
    org_name = cast(Optional[str], org.name)
    org_code = cast(Optional[str], org.code)
    new_code = generate_invitation_code(org_name, org_code)

    attempts = 0
    while await _invitation_code_taken(db, org, new_code) and attempts < 5:
        new_code = generate_invitation_code(org_name, org_code)
        attempts += 1
    if await _invitation_code_taken(db, org, new_code):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_generate_invitation_code", lang),
        )

    setattr(org, "invitation_code", new_code)
    try:
        await db.commit()
        await db.refresh(org)
    except DATABASE_ERRORS as exc:
        await db.rollback()
        logger.error("[Auth] Failed to refresh invitation code for org %s: %s", org.id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=Messages.error("failed_refresh_invitation_code", lang),
        ) from exc

    if not await org_cache.write_through(org, org_code, old_invite):
        logger.warning("[Auth] Cache write-through failed for org ID %s", org.id)
        await org_cache.recover_after_failed_write_through(org, org_code, old_invite)

    return cast(str, org.invitation_code)
