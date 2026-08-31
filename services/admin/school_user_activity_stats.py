"""Load org users and login rows, then assemble school activity cards.

Uses the caller's panel-RLS session. Does not open a new engine or system session.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.auth import User
from models.domain.user_activity_log import UserActivityLog
from services.admin.school_user_activity_compute import (
    BEIJING_TIMEZONE,
    build_activity,
    build_frequency,
    build_totals,
    min_activity_year,
    year_bounds,
)
from services.admin.school_user_activity_types import (
    LoginStamp,
    OrgUserStamp,
    SchoolUserActivityPayload,
)

LOGIN_ACTIVITY_TYPE = "login"


def beijing_now() -> datetime:
    """Current instant in Beijing."""
    return datetime.now(BEIJING_TIMEZONE)


async def load_org_users(db: AsyncSession, organization_id: int) -> list[OrgUserStamp]:
    """Load current members of the selected school."""
    rows = (await db.execute(select(User.id, User.created_at).where(User.organization_id == organization_id))).all()
    stamps: list[OrgUserStamp] = []
    for user_id, created_at in rows:
        if created_at is None:
            continue
        stamps.append({"user_id": int(user_id), "created_at": created_at})
    return stamps


async def load_org_logins(
    db: AsyncSession,
    user_ids: list[int],
    year: int,
) -> list[LoginStamp]:
    """Load login events for org members in the selected Beijing year."""
    if not user_ids:
        return []
    year_start, year_end = year_bounds(year)
    start_utc = year_start.astimezone(UTC).replace(tzinfo=None)
    end_utc = year_end.astimezone(UTC).replace(tzinfo=None)
    rows = (
        await db.execute(
            select(UserActivityLog.user_id, UserActivityLog.created_at).where(
                UserActivityLog.activity_type == LOGIN_ACTIVITY_TYPE,
                UserActivityLog.user_id.in_(user_ids),
                UserActivityLog.created_at >= start_utc,
                UserActivityLog.created_at < end_utc,
            )
        )
    ).all()
    logins: list[LoginStamp] = []
    for user_id, created_at in rows:
        if created_at is None:
            continue
        logins.append({"user_id": int(user_id), "created_at": created_at})
    return logins


def assemble_payload(
    users: list[OrgUserStamp],
    logins: list[LoginStamp],
    year: int,
    now_beijing: datetime,
) -> SchoolUserActivityPayload:
    """Assemble the API payload from already-loaded rows."""
    generated = now_beijing.astimezone(UTC)
    return {
        "year": year,
        "min_year": min_activity_year(users, now_beijing.year),
        "generated_at": generated.isoformat().replace("+00:00", "Z"),
        "totals": build_totals(users, year, now_beijing),
        "activity": build_activity(users, logins, year, now_beijing),
        "frequency": build_frequency(users, logins, year, now_beijing),
    }


async def build_school_user_activity(
    db: AsyncSession,
    organization_id: int,
    year: int | None,
) -> SchoolUserActivityPayload:
    """Fetch org-scoped rows and return the activity dashboard payload.

    Raises ValueError with ``invalid_year`` or ``year_out_of_range`` when the
    requested year is not allowed.
    """
    now = beijing_now()
    users = await load_org_users(db, organization_id)
    lowest = min_activity_year(users, now.year)
    selected = now.year if year is None else year
    if selected > now.year:
        raise ValueError("invalid_year")
    if selected < lowest:
        raise ValueError("year_out_of_range")
    user_ids = [row["user_id"] for row in users]
    logins = await load_org_logins(db, user_ids, selected)
    return assemble_payload(users, logins, selected, now)
