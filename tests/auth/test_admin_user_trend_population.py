"""User trend totals match the dashboard population and Beijing calendar days."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast

import pytest
from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import engine
from models.domain.auth import Organization, User
from routers.auth.admin.stats_trends import get_stats_trends_admin
from routers.auth.helpers import get_beijing_now, get_beijing_today_start_utc
from services.utils.error_types import DATABASE_ERRORS
from utils.auth.admin_scope import AdminScope
from utils.auth.role_constants import ROLE_STUDENT, ROLE_TEACHER
from utils.db.rls_context import RlsContext, rls_async_session


def _users_table_ready() -> bool:
    """Users table is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM users LIMIT 0"))
        return True
    except DATABASE_ERRORS:
        return False


pytestmark = pytest.mark.skipif(not _users_table_ready(), reason="users table is not reachable")


def _boundary_created_at() -> datetime:
    """One hour after the all-time window opens: previous UTC date, first Beijing day."""
    beijing_now = get_beijing_now()
    beijing_today_start = beijing_now.replace(hour=0, minute=0, second=0, microsecond=0)
    window_start = beijing_today_start - timedelta(days=365)
    return window_start.astimezone(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)


async def _expected_user_totals(session: AsyncSession, date_keys: list[str]) -> list[int]:
    """Cumulative non-student counts on each Beijing day, including users before the window."""
    beijing_day = func.date(User.created_at + timedelta(hours=8))
    grouped = (
        await session.execute(
            select(beijing_day.label("day"), func.count(User.id)).where(User.role != ROLE_STUDENT).group_by(beijing_day)
        )
    ).all()
    by_day: dict[str, int] = {}
    before_window = 0
    first_day = date_keys[0]
    for day, count in grouped:
        key = str(day.date() if isinstance(day, datetime) else day)[:10]
        if key < first_day:
            before_window += int(count)
        else:
            by_day[key] = by_day.get(key, 0) + int(count)
    cumulative = before_window
    series: list[int] = []
    for key in date_keys:
        cumulative += by_day.get(key, 0)
        series.append(cumulative)
    return series


@pytest.mark.asyncio
async def test_user_trend_excludes_students_and_keeps_beijing_boundary() -> None:
    """今日 and 全部 follow non-student totals, including the first Beijing day of the window."""
    marker = uuid.uuid4().hex
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        session.add(
            User(
                email=f"trend-boundary-{marker}@example.com",
                password_hash="x",
                role=ROLE_TEACHER,
                created_at=_boundary_created_at(),
            )
        )
        session.add(
            User(
                email=f"trend-student-{marker}@example.com",
                password_hash="x",
                role=ROLE_STUDENT,
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )
        await session.flush()
        try:
            payload = await get_stats_trends_admin(
                cast(Request, SimpleNamespace()),
                "users",
                0,
                None,
                cast(AdminScope, SimpleNamespace()),
                session,
                "en",
            )
            points = payload["data"]
            assert points
            expected = await _expected_user_totals(session, [point["date"] for point in points])
            assert [point["value"] for point in points] == expected
            non_student_total = int(
                (await session.execute(select(func.count(User.id)).where(User.role != ROLE_STUDENT))).scalar_one()
            )
            assert points[-1]["value"] == non_student_total

            registrations = await get_stats_trends_admin(
                cast(Request, SimpleNamespace()),
                "registrations",
                0,
                None,
                cast(AdminScope, SimpleNamespace()),
                session,
                "en",
            )
            registration_points = registrations["data"]
            assert registrations["total"] == non_student_total
            today_start = get_beijing_today_start_utc()
            beijing_today = get_beijing_now().replace(hour=0, minute=0, second=0, microsecond=0)
            week_start = (beijing_today - timedelta(days=7)).astimezone(timezone.utc).replace(tzinfo=None)
            month_start = (beijing_today - timedelta(days=30)).astimezone(timezone.utc).replace(tzinfo=None)

            async def _registered_since(start: datetime) -> int:
                return int(
                    (
                        await session.execute(
                            select(func.count(User.id)).where(
                                User.created_at >= start,
                                User.role != ROLE_STUDENT,
                            )
                        )
                    ).scalar_one()
                )

            assert registration_points[-1]["value"] == await _registered_since(today_start)
            assert sum(point["value"] for point in registration_points[-8:]) == await _registered_since(week_start)
            assert sum(point["value"] for point in registration_points[-31:]) == await _registered_since(month_start)

            organizations = await get_stats_trends_admin(
                cast(Request, SimpleNamespace()),
                "organizations",
                0,
                None,
                cast(AdminScope, SimpleNamespace()),
                session,
                "en",
            )
            organization_total = int((await session.execute(select(func.count(Organization.id)))).scalar_one())
            assert organizations["data"][-1]["value"] == organization_total
        finally:
            await session.rollback()
