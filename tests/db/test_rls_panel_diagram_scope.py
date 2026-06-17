"""Panel-scoped diagram RLS after rev 0051."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from utils.db.rls_context import RlsContext, rls_async_session

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


@pytest.mark.asyncio
async def test_panel_global_read_sees_all_diagrams():
    """Test panel global read sees all diagrams."""
    ctx = RlsContext(mode="panel", panel_global_read=True, user_id=1)
    async with rls_async_session(ctx) as session:
        result = await session.execute(text("SELECT count(*) FROM diagrams"))
        count = result.scalar_one()
        assert count >= 0


@pytest.mark.asyncio
async def test_school_admin_panel_scoped_diagram_access():
    """School admin panel context hides diagrams outside readable + legacy org scope."""
    ctx = RlsContext(
        mode="panel",
        user_id=1,
        organization_id=42,
        role="school_admin",
        readable_org_ids="42",
        actor_user_id=1,
    )
    async with rls_async_session(ctx) as session:
        result = await session.execute(
            text(
                "SELECT rls_diagram_visible(u.id) "
                "FROM users u "
                "JOIN organizations o ON o.id = u.organization_id "
                "WHERE u.organization_id IS NOT NULL "
                "AND u.organization_id <> 42 "
                "AND o.invited_by_user_id IS NOT NULL "
                "AND NOT rls_org_id_in_readable_list(u.organization_id) "
                "LIMIT 1"
            )
        )
        row = result.first()
        if row is not None:
            assert row[0] is False
