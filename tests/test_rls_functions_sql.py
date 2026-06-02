"""RLS function SQL helpers."""

from alembic.rls_functions_sql import (
    build_grant_rls_functions_to_app_sql,
    rls_functions_upgrade_statements,
)


def test_rls_functions_upgrade_includes_helpers():
    names = " ".join(rls_functions_upgrade_statements())
    assert "CREATE OR REPLACE FUNCTION rls_mode()" in names
    assert "CREATE OR REPLACE FUNCTION rls_org_visible(bigint)" in names


def test_grant_sql_targets_rls_helpers_only():
    sql = build_grant_rls_functions_to_app_sql()
    assert "ALL FUNCTIONS IN SCHEMA public" not in sql
    assert "mindgraph_app" in sql
    assert "~ '^rls_'" in sql
