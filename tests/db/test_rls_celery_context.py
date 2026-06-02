"""Celery-style user context for knowledge tasks."""

from utils.db.rls_context import RlsContext


def test_for_celery_user_sets_authenticated_mode():
    ctx = RlsContext.for_celery_user(42, organization_id=5)
    vars_map = ctx.session_vars()
    assert vars_map["rls_mode"] == "authenticated"
    assert vars_map["user_id"] == "42"
    assert vars_map["organization_id"] == "5"
