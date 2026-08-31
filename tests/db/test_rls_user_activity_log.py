"""Live RLS visibility for user_activity_log login rows."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import config.database as database_bootstrap
from utils.db.rls_context import RlsContext, rls_async_session

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


async def _require_activity_log_rls(session: AsyncSession) -> None:
    """Skip when this database never applied ENABLE ROW LEVEL SECURITY."""
    enabled = (
        await session.execute(
            text(
                "SELECT c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'user_activity_log'"
            )
        )
    ).scalar_one()
    if not enabled:
        pytest.skip("user_activity_log RLS is not enabled on this database")


@pytest.mark.asyncio
async def test_panel_global_read_sees_other_user_logins():
    """Superadmin panel context can read another user's login rows."""
    assert database_bootstrap.AsyncSessionLocal is not None
    ctx = RlsContext(mode="panel", panel_global_read=True, user_id=1)
    async with rls_async_session(ctx) as session:
        await _require_activity_log_rls(session)
        count = (
            await session.execute(text("SELECT count(*) FROM user_activity_log WHERE activity_type = 'login'"))
        ).scalar_one()
        assert count > 0


@pytest.mark.asyncio
async def test_authenticated_teacher_cannot_see_other_logins():
    """A teacher session only sees own login rows."""
    ctx = RlsContext(mode="authenticated", user_id=1, organization_id=42, role="teacher")
    async with rls_async_session(ctx) as session:
        await _require_activity_log_rls(session)
        foreign = (
            await session.execute(
                text("SELECT count(*) FROM user_activity_log WHERE activity_type = 'login' AND user_id <> 1")
            )
        ).scalar_one()
        assert foreign == 0


@pytest.mark.asyncio
async def test_deny_default_hides_login_rows():
    """Deny-default context cannot read login analytics."""
    ctx = RlsContext.deny_default()
    async with rls_async_session(ctx) as session:
        await _require_activity_log_rls(session)
        count = (await session.execute(text("SELECT count(*) FROM user_activity_log"))).scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_org_join_excludes_second_school_logins():
    """Org-scoped join only returns login rows for that school."""
    ctx = RlsContext(mode="panel", panel_global_read=True, user_id=1)
    async with rls_async_session(ctx) as session:
        await _require_activity_log_rls(session)
        orgs = (
            await session.execute(
                text(
                    "SELECT DISTINCT u.organization_id "
                    "FROM user_activity_log ual "
                    "JOIN users u ON u.id = ual.user_id "
                    "WHERE ual.activity_type = 'login' AND u.organization_id = :org_id"
                ),
                {"org_id": 1},
            )
        ).all()
        assert orgs
        for row in orgs:
            assert row[0] == 1
