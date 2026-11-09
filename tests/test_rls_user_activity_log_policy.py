"""user_activity_log: teachers read only their own rows; panel and system read across users."""

from utils.db_rls.policy_builder import (
    USER_ACTIVITY_LOG_EXPR,
    USER_OWNED_TABLES,
    all_rls_tables,
    iter_all_table_policies,
)


def test_user_activity_log_is_not_school_visible():
    """The diagram rule shows schoolmates' rows; login history must not."""
    assert "user_activity_log" not in USER_OWNED_TABLES
    assert "user_activity_log" in all_rls_tables()
    assert dict(iter_all_table_policies())["user_activity_log"] == USER_ACTIVITY_LOG_EXPR


def test_user_activity_log_expr_keeps_admin_and_own_access():
    """Same-school access only goes through the panel branch."""
    assert "rls_is_system_mode()" in USER_ACTIVITY_LOG_EXPR
    assert "rls_is_panel_mode() AND rls_diagram_visible(user_id)" in USER_ACTIVITY_LOG_EXPR
    assert "user_id = rls_current_user_id()" in USER_ACTIVITY_LOG_EXPR
    assert "NOT rls_is_deny_mode()" in USER_ACTIVITY_LOG_EXPR
