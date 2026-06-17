"""Dashboard aggregate RLS mode."""

from utils.db.rls_context import RlsContext


def test_dashboard_mode_vars():
    """Test dashboard mode vars."""
    ctx = RlsContext.for_dashboard()
    assert ctx.session_vars()["rls_mode"] == "dashboard"
