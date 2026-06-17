"""EXPLAIN gate for RLS policy columns (mindgraph_app, PG 18.3)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from utils.db.rls_context import RlsContext, rls_async_session

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with mindgraph_app DATABASE_URL",
)


def _plan_uses_seq_scan(explain_lines: list[str], table: str) -> bool:
    """Plan uses seq scan."""
    joined = "\n".join(explain_lines).lower()
    return f"seq scan on {table}" in joined


@pytest.mark.asyncio
async def test_diagrams_list_uses_user_id_index():
    """Test diagrams list uses user id index."""
    user_id = int(os.getenv("RLS_TEST_USER_ID", "1"))
    ctx = RlsContext.for_celery_user(user_id)
    async with rls_async_session(ctx) as session:
        result = await session.execute(
            text("EXPLAIN (FORMAT TEXT) SELECT id FROM diagrams WHERE user_id = rls_current_user_id() LIMIT 10")
        )
        lines = [row[0] for row in result.fetchall()]
        assert not _plan_uses_seq_scan(lines, "diagrams"), lines
