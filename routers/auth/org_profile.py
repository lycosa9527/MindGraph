"""Organization fields embedded in auth user payloads (login, /me, register)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from utils.auth.org_privatization import organization_is_privatized
from utils.auth.org_subscription import (
    effective_school_tier_for_org,
    is_org_subscription_expired,
)
from utils.auth.school_tier import (
    school_tier_features_for_no_org,
    school_tier_features_payload,
)


def _org_mindmate_agent_name(org) -> Optional[str]:
    if not org:
        return None
    raw = getattr(org, "mindmate_agent_name", None)
    if not raw:
        return None
    stripped = str(raw).strip()
    return stripped or None


def _org_mindmate_avatar_url(org) -> Optional[str]:
    if not org:
        return None
    raw = getattr(org, "mindmate_agent_avatar_url", None)
    if not raw:
        return None
    stripped = str(raw).strip()
    return stripped or None


def organization_session_payload(org) -> dict:
    """Build organization object for login, register, and /me responses."""
    if not org:
        return {
            "id": None,
            "code": None,
            "name": None,
            "display_name": None,
            "mindmate_agent_name": None,
            "mindmate_agent_avatar_url": None,
            "school_tier": None,
            "school_tier_features": school_tier_features_for_no_org(),
            "subscription_expired": False,
            "is_privatized": False,
        }
    display_raw = getattr(org, "display_name", None)
    display_stripped = (str(display_raw).strip() if display_raw else "") or None
    tier = effective_school_tier_for_org(org)
    return {
        "id": org.id,
        "code": org.code,
        "name": org.name,
        "display_name": display_stripped,
        "mindmate_agent_name": _org_mindmate_agent_name(org),
        "mindmate_agent_avatar_url": _org_mindmate_avatar_url(org),
        "school_tier": tier,
        "school_tier_features": school_tier_features_payload(tier),
        "subscription_expired": is_org_subscription_expired(org),
        "is_privatized": organization_is_privatized(org),
    }


async def organization_session_payload_async(db: AsyncSession, org) -> dict:
    """Build org payload for login/me.

    Redis org cache omits Dify secrets; re-read PostgreSQL when branding is present
    but the cached snapshot cannot prove privatization.
    """
    payload = organization_session_payload(org)
    if not org or payload.get("is_privatized"):
        return payload
    org_id = getattr(org, "id", None)
    if not org_id:
        return payload
    db_org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if db_org:
        payload["is_privatized"] = organization_is_privatized(db_org)
    return payload
