"""
Effective school tier after B2B subscription expiry rules.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from utils.auth.datetime_compat import as_utc_aware
from utils.auth.school_tier_defs import SCHOOL_TIER_TRIAL, normalize_school_tier


def is_org_subscription_expired(org: object | None) -> bool:
    """Return True when the org has a subscription end date in the past."""
    if org is None:
        return False
    expires_at = getattr(org, "expires_at", None)
    if expires_at is None:
        return False
    return as_utc_aware(expires_at) < datetime.now(UTC)


def effective_school_tier_for_org(org: object | None) -> str:
    """Tier after applying subscription expiry (expired paid org → trial)."""
    if org is None:
        return SCHOOL_TIER_TRIAL
    if is_org_subscription_expired(org):
        return SCHOOL_TIER_TRIAL
    return normalize_school_tier(getattr(org, "school_tier", None))
