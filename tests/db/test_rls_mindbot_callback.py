"""MindBot service RLS session vars."""

from utils.db.rls_context import RlsContext


def test_mindbot_service_sets_org_and_token():
    ctx = RlsContext.for_mindbot_service(organization_id=99, callback_token="secret-token")
    vars_map = ctx.session_vars()
    assert vars_map["rls_mode"] == "mindbot_service"
    assert vars_map["organization_id"] == "99"
    assert vars_map["mindbot_callback_token"] == "secret-token"
