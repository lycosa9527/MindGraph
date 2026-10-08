"""RLS function SQL helpers."""

from utils.db_rls.functions_sql import (
    build_grant_rls_functions_to_app_sql,
    rls_functions_upgrade_statements,
)
from utils.db_rls.policy_builder import DIRECT_MESSAGE_EXPR, USERS_EXPR


def test_rls_functions_upgrade_includes_helpers():
    """Test rls functions upgrade includes helpers."""
    names = " ".join(rls_functions_upgrade_statements())
    assert "CREATE OR REPLACE FUNCTION rls_mode()" in names
    assert "CREATE OR REPLACE FUNCTION rls_org_visible(target_org_id bigint)" in names
    assert "CREATE OR REPLACE FUNCTION rls_panel_org_invited_by_actor(invited_by bigint)" in names
    assert "CREATE OR REPLACE FUNCTION rls_user_bound_to_org(target_user_id bigint, target_org_id bigint)" in names


def test_same_org_users_stays_on_membership():
    """Diagrams and knowledge stay on real organization membership.

    Expert bindings are not part of rls_same_org_users. That function is what
    rls_diagram_visible uses, so a school must not receive an expert's files.
    """
    same_org = next(
        statement for statement in rls_functions_upgrade_statements() if "FUNCTION rls_same_org_users" in statement
    )
    assert "organization_expert_bindings" not in same_org
    assert "rls_user_bound_to_org" not in same_org


def test_users_policy_shows_bound_experts_without_opening_dms():
    """Teachers can read a bound expert's profile, not that expert's other DMs."""
    assert "rls_user_bound_to_org(id, rls_current_org_id())" in USERS_EXPR
    assert "rls_users_share_bound_org" in USERS_EXPR
    assert "rls_user_bound_to_org" not in DIRECT_MESSAGE_EXPR
    assert DIRECT_MESSAGE_EXPR == "rls_user_visible(sender_id) OR rls_user_visible(recipient_id)"


def test_grant_sql_targets_rls_helpers_only():
    """Test grant sql targets rls helpers only."""
    sql = build_grant_rls_functions_to_app_sql()
    assert "ALL FUNCTIONS IN SCHEMA public" not in sql
    assert "mindgraph_app" in sql
    assert "~ '^rls_'" in sql
