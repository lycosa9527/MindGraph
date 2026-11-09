"""Panel user INSERT RLS (school dashboard member create)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

import config.database as database_bootstrap
from utils.db_rls.policy_builder import USERS_EXPR
from utils.db.rls_context import RlsContext, rls_async_session

pytestmark_rls_db = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


def test_users_expr_allows_panel_insert_via_organization_id():
    """School member create must pass RLS before user id is assigned."""
    assert "rls_org_visible(organization_id)" in USERS_EXPR


_CODE = "SCH-RLS-900007042"
_PHONE = "19900007042"


async def _insert_org() -> int:
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        org_id = (
            await session.execute(
                text(
                    """
                    INSERT INTO organizations (code, name, created_at, is_active, school_tier)
                    VALUES (:code, 'RLS panel user test', now() AT TIME ZONE 'utc', true, 'trial')
                    RETURNING id
                    """
                ),
                {"code": _CODE},
            )
        ).scalar_one()
        await session.commit()
        return int(org_id)


async def _cleanup() -> None:
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        await session.execute(text("DELETE FROM users WHERE phone = :phone"), {"phone": _PHONE})
        await session.execute(text("DELETE FROM organizations WHERE code = :code"), {"code": _CODE})
        await session.commit()


@pytest.mark.asyncio
@pytestmark_rls_db
async def test_school_admin_panel_insert_user_in_own_org():
    """A school admin panel session can add a teacher to its own school."""
    assert database_bootstrap.AsyncSessionLocal is not None
    await _cleanup()
    org_id = await _insert_org()
    ctx = RlsContext(
        mode="panel",
        user_id=900_007_042,
        organization_id=org_id,
        role="school_admin",
        readable_org_ids=str(org_id),
        actor_user_id=900_007_042,
    )
    try:
        async with rls_async_session(ctx) as session:
            await session.execute(
                text(
                    """
                    INSERT INTO users (
                        phone, password_hash, name, organization_id, role,
                        created_at, login_password_set,
                        allows_simplified_chinese, email_login_whitelisted_from_cn
                    )
                    VALUES (
                        :phone, 'hash', 'RLS panel user test', :org_id, 'teacher',
                        now() AT TIME ZONE 'utc', false, true, false
                    )
                    """
                ),
                {"phone": _PHONE, "org_id": org_id},
            )
            await session.commit()
            row = (
                await session.execute(
                    text("SELECT id FROM users WHERE phone = :phone"),
                    {"phone": _PHONE},
                )
            ).first()
            assert row is not None
    finally:
        await _cleanup()
