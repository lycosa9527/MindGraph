"""Panel user INSERT RLS (school dashboard member create)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from db_rls.policy_builder import USERS_EXPR
from utils.db.rls_context import RlsContext, rls_async_session

pytestmark_rls_db = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


def test_users_expr_allows_panel_insert_via_organization_id():
    """School member create must pass RLS before user id is assigned."""
    assert "rls_org_visible(organization_id)" in USERS_EXPR


@pytest.mark.asyncio
@pytestmark_rls_db
async def test_school_admin_panel_insert_user_in_own_org():
    """Test school admin panel insert user in own org."""
    actor_id = 900_007_042
    org_id = 900_007_042
    phone = f"199{org_id % 100_000_000:08d}"
    ctx = RlsContext(
        mode="panel",
        user_id=actor_id,
        organization_id=org_id,
        role="school_admin",
        readable_org_ids=str(org_id),
        actor_user_id=actor_id,
    )
    async with rls_async_session(ctx) as session:
        await session.execute(
            text(
                """
                INSERT INTO users (
                    phone, password_hash, name, organization_id, role,
                    created_at, login_password_set
                )
                VALUES (
                    :phone, 'hash', 'RLS panel user test', :org_id, 'teacher',
                    now() AT TIME ZONE 'utc', false
                )
                """
            ),
            {"phone": phone, "org_id": org_id},
        )
        await session.commit()
        row = (
            await session.execute(
                text("SELECT id FROM users WHERE phone = :phone"),
                {"phone": phone},
            )
        ).first()
        assert row is not None
        await session.execute(text("DELETE FROM users WHERE phone = :phone"), {"phone": phone})
        await session.commit()
