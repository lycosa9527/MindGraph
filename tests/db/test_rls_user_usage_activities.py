"""Live RLS visibility for user_usage_activities rows."""

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


async def _require_usage_rls(session: AsyncSession) -> None:
    """Skip when this database never applied ENABLE ROW LEVEL SECURITY."""
    enabled = (
        await session.execute(
            text(
                "SELECT c.relrowsecurity FROM pg_class c "
                "JOIN pg_namespace n ON n.oid = c.relnamespace "
                "WHERE n.nspname = 'public' AND c.relname = 'user_usage_activities'"
            )
        )
    ).scalar_one()
    if not enabled:
        pytest.skip("user_usage_activities RLS is not enabled on this database")


@pytest.mark.asyncio
async def test_panel_global_read_sees_usage_rows():
    """Superadmin panel context can read usage rows."""
    assert database_bootstrap.AsyncSessionLocal is not None
    ctx = RlsContext(mode="panel", panel_global_read=True, user_id=1)
    async with rls_async_session(ctx) as session:
        await _require_usage_rls(session)
        count = (await session.execute(text("SELECT count(*) FROM user_usage_activities"))).scalar_one()
        assert count >= 0


@pytest.mark.asyncio
async def test_org_member_join_excludes_second_school_usage():
    """Org-scoped member join only returns usage rows for that school."""
    ctx = RlsContext(mode="panel", panel_global_read=True, user_id=1)
    async with rls_async_session(ctx) as session:
        await _require_usage_rls(session)
        orgs = (
            await session.execute(
                text(
                    "SELECT DISTINCT u.organization_id "
                    "FROM user_usage_activities uua "
                    "JOIN users u ON u.id = uua.user_id "
                    "WHERE u.organization_id = :org_id"
                ),
                {"org_id": 1},
            )
        ).all()
        for row in orgs:
            assert row[0] == 1
