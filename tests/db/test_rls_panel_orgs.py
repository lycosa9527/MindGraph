"""Panel readable_org_ids session var parity."""

import os

import pytest
from sqlalchemy import text

from utils.auth.admin_panel_permissions import CAP_SCOPE_INVITED_ORGS
from utils.auth.admin_scope import build_admin_scope
from utils.db.rls_context import RlsContext, rls_async_session
from db_rls.policy_builder import ORGS_EXPR

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


@pytest.mark.asyncio
@pytestmark_rls_db
async def test_expert_panel_insert_org_with_invited_by_self():
    """Test expert panel insert org with invited by self."""
    actor_id = 900_007_163
    ctx = RlsContext(
        mode="panel",
        user_id=actor_id,
        actor_user_id=actor_id,
        role="expert",
        readable_org_ids="1",
    )
    code = f"SCH-RLS-{actor_id}"
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
        await session.execute(text("DELETE FROM organizations WHERE code = :code"), {"code": code})
        await session.commit()
