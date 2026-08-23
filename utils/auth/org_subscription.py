"""
B2B school subscription expiry: hard-lock teachers and school managers.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import HTTPException, status

from models.domain.auth import Organization
from models.domain.messages import Language, Messages
from utils.auth.datetime_compat import as_utc_aware
from utils.auth.org_subscription_downgrade import downgrade_expired_org_to_trial
from utils.auth.roles import is_platform_level
from utils.auth.school_tier_effective import (
    effective_school_tier_for_org,
    is_org_subscription_expired,
)

ORG_SUBSCRIPTION_EXPIRED_CODE = "organization_expired"


def _expires_at_label(org: object) -> str:
    """ISO date (UTC) for expired-org error payloads."""
    expires_at = getattr(org, "expires_at", None)
    if expires_at is None:
        return ""
    return as_utc_aware(expires_at).date().isoformat()


def org_subscription_expired_detail(org: object, lang: Language) -> dict[str, str]:
    """Structured 403 body so the frontend can open the lockout modal."""
    name = str(getattr(org, "name", "") or "")
    ended = _expires_at_label(org)
    return {
        "code": ORG_SUBSCRIPTION_EXPIRED_CODE,
        "message": Messages.error("organization_expired", lang, name, ended),
        "school_name": name,
        "expires_at": ended,
    }


def should_bypass_org_subscription_lock(user: object | None) -> bool:
    """Platform-tier actors may still sign in to renew a school."""
    if user is None:
        return False
    return is_platform_level(user)


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
    user: object | None = None,
) -> Organization:
    """Raise if org is admin-locked or the school product term has ended."""
    is_active = getattr(org, "is_active", True)
    if not is_active:
        error_msg = Messages.error("organization_locked", lang, org.name)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
    if should_bypass_org_subscription_lock(user):
        return org
    if is_org_subscription_expired(org):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=org_subscription_expired_detail(org, lang),
        )
    return org


__all__ = [
    "ORG_SUBSCRIPTION_EXPIRED_CODE",
    "downgrade_expired_org_to_trial",
    "effective_school_tier_for_org",
    "ensure_org_subscription_current",
    "enforce_org_accessible_or_raise",
    "is_org_subscription_expired",
    "org_subscription_expired_detail",
    "should_bypass_org_subscription_lock",
]
