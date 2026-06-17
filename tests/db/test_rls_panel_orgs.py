"""Panel readable_org_ids session var parity."""

from utils.auth.admin_panel_permissions import CAP_SCOPE_INVITED_ORGS
from utils.auth.admin_scope import build_admin_scope


class _User:
    """_User helper."""

    def __init__(self, role: str, user_id: int = 7):
        """init  ."""
        self.role = role
        self.id = user_id
        self.organization_id = None


def test_expert_to_rls_session_vars_includes_readable_org_ids():
    """Test expert to rls session vars includes readable org ids."""
    user = _User("expert")
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map["readable_org_ids"] == "10,20"
    assert CAP_SCOPE_INVITED_ORGS in scope.capabilities
