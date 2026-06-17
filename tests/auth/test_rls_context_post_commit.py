"""Post-commit RLS context remains panel mode after set_rls_context sync."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from utils.auth.admin_scope import build_admin_scope
from utils.db.rls_context import RlsContext, rls_async_session, set_rls_context

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


@pytest.mark.asyncio
async def test_panel_mode_persists_after_commit():
    """Test panel mode persists after commit."""

    class _User:
        role = "school_admin"
        id = 1
        organization_id = 42

    scope = build_admin_scope(_User(), lang="en")
    ctx = RlsContext.from_admin_scope(scope)
    set_rls_context(ctx)

    async with rls_async_session(ctx) as session:
        mode = (await session.execute(text("SELECT current_setting('app.rls_mode', true)"))).scalar_one()
        assert mode == "panel"
        await session.commit()
        mode_after = (await session.execute(text("SELECT current_setting('app.rls_mode', true)"))).scalar_one()
        assert mode_after == "panel"
