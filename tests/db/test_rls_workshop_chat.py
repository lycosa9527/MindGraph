"""Workshop chat global channel flag."""

from utils.db.rls_context import RlsContext


class _User:
    """_User helper."""

    id = 1
    organization_id = 10
    role = "teacher"


def test_allow_global_channels_flag():
    """Test allow global channels flag."""
    ctx = RlsContext.from_user(_User(), allow_global_channels=True)
    assert ctx.session_vars()["allow_global_channels"] == "1"
