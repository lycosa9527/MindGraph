"""Parse Dify ``user`` strings and resolve to MindGraph ``users.id``."""

from __future__ import annotations

import re
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from repositories.dingtalk_staff_link_repo import DingtalkStaffLinkRepository
from utils.auth import AUTH_MODE

_MG_USER_RE = re.compile(r"^mg_user_(\d+)$")
_MINDBOT_USER_RE = re.compile(r"^mindbot_(\d+)_(.+)$")


def parse_mindbot_dify_key(raw: str) -> tuple[Optional[int], Optional[str]]:
    """Return (organization_id, dingtalk_staff_id) from ``mindbot_{org}_{staff}``."""
    text = (raw or "").strip()
    match = _MINDBOT_USER_RE.match(text)
    if not match:
        return None, None
    try:
        org_id = int(match.group(1))
    except ValueError:
        return None, None
    staff = (match.group(2) or "").strip()
    if not staff or org_id <= 0:
        return None, None
    return org_id, staff[:128]


def parse_mg_user_id(raw: str) -> Optional[int]:
    """Return user pk from ``mg_user_{id}``."""
    text = (raw or "").strip()
    match = _MG_USER_RE.match(text)
    if not match:
        return None
    try:
        uid = int(match.group(1))
    except ValueError:
        return None
    return uid if uid > 0 else None


async def _lookup_user_id_and_org(
    db: AsyncSession,
    user_id: int,
) -> tuple[Optional[int], Optional[int]]:
    stmt = select(User.id, User.organization_id).where(User.id == user_id).limit(1)
    row = (await db.execute(stmt)).first()
    if row is None:
        return None, None
    uid, org_raw = row
    org_id = int(org_raw) if org_raw is not None else None
    return int(uid), org_id


async def resolve_user_and_org_from_dify_key(
    db: AsyncSession,
    dify_user_key: str,
    *,
    fallback_organization_id: Optional[int] = None,
) -> tuple[Optional[int], Optional[int]]:
    """
    Resolve MindGraph ``users.id`` and ``organization_id`` from a Dify user string.

    Supports ``mg_user_{pk}``, Bayi UUID phone, and ``mindbot_{org}_{staff}`` via link table.
    """
    key = (dify_user_key or "").strip()
    if not key:
        return None, None

    mg_uid = parse_mg_user_id(key)
    if mg_uid is not None:
        return await _lookup_user_id_and_org(db, mg_uid)

    if AUTH_MODE == "bayi":
        try:
            uuid_text = str(UUID(key))
        except ValueError:
            uuid_text = None
        if uuid_text:
            stmt = select(User.id, User.organization_id).where(User.phone == uuid_text).limit(1)
            row = (await db.execute(stmt)).first()
            if row is not None:
                uid, org_raw = row
                org_id = int(org_raw) if org_raw is not None else None
                return int(uid), org_id

    org_id, staff_id = parse_mindbot_dify_key(key)
    if org_id is not None and staff_id:
        repo = DingtalkStaffLinkRepository(db)
        linked = await repo.resolve_user_id_for_staff(org_id, staff_id)
        if linked is not None:
            return linked, org_id
        return None, org_id

    if fallback_organization_id is not None and org_id is None:
        fallback_org = int(fallback_organization_id)
        staff_only = key
        if staff_only and not key.startswith("mindbot_"):
            repo = DingtalkStaffLinkRepository(db)
            linked = await repo.resolve_user_id_for_staff(fallback_org, staff_only)
            if linked is not None:
                return linked, fallback_org

    return None, None


async def resolve_user_id_from_dify_key(
    db: AsyncSession,
    dify_user_key: str,
    *,
    fallback_organization_id: Optional[int] = None,
) -> Optional[int]:
    """Resolve MindGraph ``users.id`` from a Dify API user string."""
    user_id, _org_id = await resolve_user_and_org_from_dify_key(
        db,
        dify_user_key,
        fallback_organization_id=fallback_organization_id,
    )
    return user_id
