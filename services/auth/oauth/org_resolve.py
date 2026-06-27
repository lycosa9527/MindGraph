"""Resolve organization from invitation code for OAuth flows."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import Organization
from services.redis.cache.redis_org_cache import org_cache
from utils.invitations import invitation_code_is_valid


async def resolve_org_by_invitation_code(db: AsyncSession, invite: str) -> Optional[Organization]:
    """Find organization by invitation code or None."""
    provided = (invite or "").strip().upper()
    if not provided or not invitation_code_is_valid(provided):
        return None
    org = await org_cache.get_by_invitation_code(provided)
    if org is not None:
        return org
    result = await db.execute(select(Organization).where(Organization.invitation_code == provided))
    return result.scalar_one_or_none()
