"""Panel readable_org_ids session var parity."""

import os

import pytest
from sqlalchemy import text

import config.database as database_bootstrap
from utils.auth.admin_panel_permissions import CAP_SCOPE_INVITED_ORGS
from utils.auth.admin_scope import build_admin_scope
from utils.db.rls_context import RlsContext, rls_async_session
from utils.db_rls.policy_builder import ORGS_EXPR

pytestmark_rls_db = pytest.mark.skipif(
    os.getenv("RUN_RLS_DB_TESTS", "").lower() not in ("1", "true", "yes"),
    reason="Set RUN_RLS_DB_TESTS=1 with migrated Postgres and mindgraph_app URL",
)


class _User:
    """_User helper."""

    def __init__(self, role: str, user_id: int = 7):
        """init  ."""
        self.role = role
        self.id = user_id
        self.organization_id = None


def test_expert_to_rls_session_vars_includes_readable_org_ids():
    """Test expert to rls session vars includes readable org ids."""
    user = _User("expert")
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map["readable_org_ids"] == "10,20"
    assert CAP_SCOPE_INVITED_ORGS in scope.capabilities


def test_orgs_expr_allows_invited_by_actor_for_panel_insert():
    """Expert org create must pass RLS before id is assigned (INSERT WITH CHECK)."""
    assert "rls_panel_org_invited_by_actor(invited_by_user_id)" in ORGS_EXPR


async def _insert_expert(phone: str) -> int:
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        actor_id = (
            await session.execute(
                text(
                    """
                    INSERT INTO users (
                        phone, password_hash, name, role, created_at, login_password_set,
                        allows_simplified_chinese, email_login_whitelisted_from_cn
                    )
                    VALUES (
                        :phone, 'hash', 'RLS expert test', 'expert',
                        now() AT TIME ZONE 'utc', false, true, false
                    )
                    RETURNING id
                    """
                ),
                {"phone": phone},
            )
        ).scalar_one()
        await session.commit()
        return int(actor_id)


async def _cleanup(phone: str, code: str) -> None:
    async with rls_async_session(RlsContext.system_bootstrap()) as session:
        await session.execute(text("DELETE FROM organizations WHERE code = :code"), {"code": code})
        await session.execute(text("DELETE FROM users WHERE phone = :phone"), {"phone": phone})
        await session.commit()


@pytest.mark.asyncio
@pytestmark_rls_db
async def test_expert_panel_insert_org_with_invited_by_self():
    """An expert panel session can create a school it invites, before the id exists."""
    assert database_bootstrap.AsyncSessionLocal is not None
    phone = "19900007163"
    code = "SCH-RLS-900007163"
    await _cleanup(phone, code)
    actor_id = await _insert_expert(phone)
    ctx = RlsContext(
        mode="panel",
        user_id=actor_id,
        actor_user_id=actor_id,
        role="expert",
        readable_org_ids="",
    )
    try:
        async with rls_async_session(ctx) as session:
            await session.execute(
                text(
                    """
                    INSERT INTO organizations (
                        code, name, invitation_code, invited_by_user_id,
                        created_at, is_active, school_tier
                    )
                    VALUES (
                        :code, 'RLS expert create test', 'TST-RLS', :actor_id,
                        now() AT TIME ZONE 'utc', true, 'trial'
                    )
                    """
                ),
                {"code": code, "actor_id": actor_id},
            )
            await session.commit()
            row = (
                await session.execute(
                    text("SELECT id FROM organizations WHERE code = :code"),
                    {"code": code},
                )
            ).first()
            assert row is not None
    finally:
        await _cleanup(phone, code)
