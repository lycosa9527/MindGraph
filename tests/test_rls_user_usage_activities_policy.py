"""user_usage_activities stays on rls_diagram_visible(user_id)."""

from utils.db_rls.policy_builder import USER_OWNED_EXPR, USER_OWNED_TABLES


def test_user_usage_activities_is_user_owned_diagram_visible():
    """Feature-usage rows use the same owner visibility helper as diagrams."""
    assert "user_usage_activities" in USER_OWNED_TABLES
    assert USER_OWNED_EXPR == "rls_diagram_visible(user_id)"
