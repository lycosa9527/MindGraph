"""Gewe tables have app_id only; RLS uses platform admin / system paths."""

from utils.db.alembic_migration import load_rls_policy_builder

builder = load_rls_policy_builder()
GEWE_EXPR = builder.GEWE_EXPR
GEWE_TABLES = builder.GEWE_TABLES


def test_gewe_tables_not_user_owned():
    assert not set(GEWE_TABLES) & set(builder.USER_OWNED_TABLES)


def test_gewe_policy_expr_no_user_id():
    assert "user_id" not in GEWE_EXPR
    assert "rls_platform_admin_only()" in GEWE_EXPR


def test_gewe_tables_list():
    assert GEWE_TABLES == [
        "gewe_messages",
        "gewe_contacts",
        "gewe_group_members",
    ]
