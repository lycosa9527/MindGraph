"""
B2B school subscription expiry: downgrade paid tiers to trial when contract ends.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from utils.auth.org_subscription_downgrade import downgrade_expired_org_to_trial
from utils.auth.school_tier_effective import (
    effective_school_tier_for_org,
    is_org_subscription_expired,
)

logger = logging.getLogger(__name__)


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
