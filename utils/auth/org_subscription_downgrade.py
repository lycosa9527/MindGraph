"""
Persist org subscription trial downgrade (leaf DB write module).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select

from models.domain.auth import Organization
from services.utils.error_types import DATABASE_ERRORS

try:
    from services.redis.cache.redis_org_cache import org_cache as _redis_org_cache
except ImportError:
    _redis_org_cache = None

from utils.auth.school_tier_defs import SCHOOL_TIER_TRIAL, normalize_school_tier
from utils.auth.school_tier_effective import is_org_subscription_expired
from utils.db.session_open import system_rls_session

logger = logging.getLogger(__name__)

_org_cache = _redis_org_cache


async def downgrade_expired_org_to_trial(org_id: int) -> Optional[Organization]:
    """Persist trial downgrade when subscription expired; refresh cache."""
    async with system_rls_session() as db:
        result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = result.scalar_one_or_none()
        if org is None:
            return None
        if not is_org_subscription_expired(org):
            return org
        current_tier = normalize_school_tier(getattr(org, "school_tier", None))
        if current_tier == SCHOOL_TIER_TRIAL:
            return org
        old_code = org.code
        old_invite = org.invitation_code
        org.school_tier = SCHOOL_TIER_TRIAL
        try:
            await db.commit()
            await db.refresh(org)
        except DATABASE_ERRORS as exc:
            await db.rollback()
            logger.error(
                "[OrgSubscription] Failed to downgrade org id=%s to trial: %s",
                org_id,
                exc,
                exc_info=True,
            )
            return org
        logger.info(
            "[OrgSubscription] Downgraded org id=%s from %s to trial (expired %s)",
            org_id,
            current_tier,
            org.expires_at,
        )
        if _org_cache is not None:
            if not await _org_cache.write_through(org, old_code, old_invite):
                logger.warning(
                    "[OrgSubscription] Cache write-through failed after downgrade org id=%s",
                    org_id,
                )
                await _org_cache.recover_after_failed_write_through(org, old_code, old_invite)
        return org
