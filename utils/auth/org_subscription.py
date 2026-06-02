"""B2B school subscription expiry: downgrade paid tiers to trial when contract ends."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select

from utils.db.session_open import system_rls_session
from models.domain.auth import Organization
from models.domain.messages import Language, Messages

from utils.auth.school_tier_defs import SCHOOL_TIER_TRIAL, normalize_school_tier
from utils.auth.school_tier_effective import (
    effective_school_tier_for_org,
    is_org_subscription_expired,
)

logger = logging.getLogger(__name__)

_org_cache = None

try:
    from services.redis.cache.redis_org_cache import org_cache as _redis_org_cache

    _org_cache = _redis_org_cache
except ImportError:
    pass


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
        except Exception as exc:
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


async def ensure_org_subscription_current(org: Organization | None) -> Organization | None:
    """If org subscription expired, downgrade to trial and return updated org."""
    if org is None:
        return None
    if not is_org_subscription_expired(org):
        return org
    org_id = int(getattr(org, "id", 0) or 0)
    if org_id <= 0:
        return org
    updated = await downgrade_expired_org_to_trial(org_id)
    return updated or org


async def enforce_org_accessible_or_raise(
    org: Organization,
    lang: Language,
) -> Organization:
    """Raise if org locked; downgrade expired subscription to trial."""
    is_active = getattr(org, "is_active", True)
    if not is_active:
        error_msg = Messages.error("organization_locked", lang, org.name)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    updated = await ensure_org_subscription_current(org)
    return updated or org


__all__ = [
    "downgrade_expired_org_to_trial",
    "effective_school_tier_for_org",
    "ensure_org_subscription_current",
    "enforce_org_accessible_or_raise",
    "is_org_subscription_expired",
]
