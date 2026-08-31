"""user_activity_log stays on rls_diagram_visible(user_id)."""

from utils.db_rls.policy_builder import USER_OWNED_EXPR, USER_OWNED_TABLES


def test_user_activity_log_is_user_owned_diagram_visible():
    """Login rows use the same owner visibility helper as diagrams."""
    assert "user_activity_log" in USER_OWNED_TABLES
    assert USER_OWNED_EXPR == "rls_diagram_visible(user_id)"
