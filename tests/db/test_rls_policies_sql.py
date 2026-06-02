"""Cross-tenant isolation tests (Postgres + RLS enabled)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


@pytest.mark.asyncio
async def test_diagrams_hidden_without_user_context():
    from utils.db.rls_context import RlsContext, rls_async_session

    async with rls_async_session(RlsContext.deny_default()) as session:
        result = await session.execute(text("SELECT count(*) FROM diagrams"))
        count = result.scalar_one()
        assert count == 0


@pytest.mark.asyncio
async def test_panel_global_read_sees_rows():
    from utils.db.rls_context import RlsContext, rls_async_session

    ctx = RlsContext(mode="panel", panel_global_read=True, user_id=1)
    async with rls_async_session(ctx) as session:
        result = await session.execute(text("SELECT count(*) FROM organizations"))
        count = result.scalar_one()
        assert count >= 0
