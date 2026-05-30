"""Personal trial (C2C) invite payload for expert and platform BD panels."""

from __future__ import annotations

import os
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization


def personal_trial_org_code() -> Optional[str]:
    """Organization code used for personal experience registration invites."""
    raw = os.environ.get("PERSONAL_TRIAL_ORG_CODE", "").strip()
    return raw or None


async def build_personal_trial_invite_payload(
    db: AsyncSession,
) -> dict[str, Any]:
    """
    Return invite metadata when PERSONAL_TRIAL_ORG_CODE points to a valid organization.

    Registration still uses the organization's invitation code; assign personal_trial
    role at signup is a separate phase.
    """
    org_code = personal_trial_org_code()
    if not org_code:
        return {"configured": False}

    org = (await db.execute(select(Organization).where(Organization.code == org_code))).scalar_one_or_none()
    if org is None:
        return {"configured": False, "organization_code": org_code, "missing": True}

    invite_raw = getattr(org, "invitation_code", None)
    invitation_code = str(invite_raw).strip() if invite_raw else ""
    return {
        "configured": True,
        "organization_id": int(org.id),
        "organization_code": org.code,
        "organization_name": org.name,
        "invitation_code": invitation_code,
    }
