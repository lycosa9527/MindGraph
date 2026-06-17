"""Tests for AdminScope and panel capabilities."""

import pytest
from fastapi import HTTPException

from utils.auth.admin_panel_permissions import (
    CAP_PANEL_ACCESS,
    CAP_SCOPE_GLOBAL,
    CAP_SCOPE_INVITED_ORGS,
    CAP_TAB_BILLING_VIEW,
    CAP_TAB_DATA_CENTER_VIEW,
    CAP_TAB_INVITES_EDIT,
    CAP_TAB_INVITES_VIEW,
    CAP_TAB_ORGANIZATIONS_VIEW,
    CAP_TAB_SCHOOL_DASHBOARD_VIEW,
    CAP_TAB_SETTINGS_VIEW,
    CAP_TAB_USERS_EDIT,
    CAP_TAB_USERS_VIEW,
    ROLE_PANEL_CAPABILITIES,
    capabilities_for_role,
    role_has_panel_access,
    user_panel_capabilities,
    validate_role_panel_config,
)
from utils.auth.admin_scope import build_admin_scope, resolve_effective_org_id
from utils.auth.role_constants import ALL_USER_ROLES


class _User:
    """_User helper."""
    def __init__(self, role: str, organization_id: int | None = None, user_id: int = 1):
        """ init  ."""
        self.role = role
        self.organization_id = organization_id
        self.id = user_id
        self.phone: str | None = None


def test_teacher_has_no_panel_access():
    """Test teacher has no panel access."""
    assert not role_has_panel_access("teacher")
    assert CAP_PANEL_ACCESS not in capabilities_for_role("teacher")


def test_school_admin_has_school_member_caps_without_global_scope():
    """Test school admin has school member caps without global scope."""
    caps = capabilities_for_role("school_admin")
    assert CAP_PANEL_ACCESS in caps
    assert CAP_TAB_USERS_VIEW in caps
    assert CAP_TAB_USERS_EDIT in caps
    assert CAP_TAB_SCHOOL_DASHBOARD_VIEW in caps
    assert CAP_TAB_DATA_CENTER_VIEW not in caps
    assert CAP_TAB_INVITES_VIEW not in caps
    assert CAP_TAB_SETTINGS_VIEW not in caps
    assert CAP_SCOPE_GLOBAL not in caps


def test_superadmin_has_users_tab():
    """Test superadmin has users tab."""
    caps = capabilities_for_role("superadmin")
    assert CAP_TAB_USERS_VIEW in caps
    assert CAP_SCOPE_GLOBAL in caps


def test_expert_invites_only():
    """Test expert invites only."""
    caps = capabilities_for_role("expert")
    assert CAP_PANEL_ACCESS in caps
    assert CAP_TAB_INVITES_VIEW in caps
    assert CAP_TAB_INVITES_EDIT in caps
    assert CAP_SCOPE_INVITED_ORGS in caps
    assert CAP_TAB_USERS_VIEW not in caps
    assert CAP_TAB_DATA_CENTER_VIEW not in caps


def test_expert_scope_empty_without_db():
    """Test expert scope empty without db."""
    user = _User("expert", user_id=7)
    scope = build_admin_scope(user, lang="en")
    assert scope.org_ids == frozenset()


def test_build_admin_scope_rejects_teacher():
    """Test build admin scope rejects teacher."""
    user = _User("teacher")
    with pytest.raises(HTTPException) as exc:
        build_admin_scope(user, lang="en")
    assert exc.value.status_code == 403


def test_superadmin_to_rls_session_vars_global_read():
    """Test superadmin to rls session vars global read."""
    user = _User("superadmin", user_id=1)
    scope = build_admin_scope(user, lang="en")
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map.get("panel_global_read") == "1"


def test_school_admin_to_rls_session_vars_org_scope():
    """Test school admin to rls session vars org scope."""
    user = _User("school_admin", organization_id=42)
    scope = build_admin_scope(user, lang="en")
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map["readable_org_ids"] == "42"
    assert vars_map["organization_id"] == "42"


def test_school_admin_locked_org():
    """Test school admin locked org."""
    user = _User("school_admin", organization_id=42)
    scope = build_admin_scope(user, lang="en")
    assert scope.org_ids == frozenset({42})
    assert scope.effective_org_id == 42


def test_school_admin_cross_org_forbidden():
    """Test school admin cross org forbidden."""
    user = _User("school_admin", organization_id=42)
    with pytest.raises(HTTPException) as exc:
        build_admin_scope(user, organization_id=99, lang="en")
    assert exc.value.status_code == 403


def test_superadmin_requires_org_when_resolving():
    """Test superadmin requires org when resolving."""
    user = _User("superadmin")
    scope = build_admin_scope(user, lang="en")
    with pytest.raises(HTTPException) as exc:
        resolve_effective_org_id(scope, None, "en", require_org_for_superadmin=True)
    assert exc.value.status_code == 400


def test_platform_bd_has_readonly_global_tabs_and_invite_edit():
    """Test platform bd has readonly global tabs and invite edit."""
    caps = capabilities_for_role("platform_bd")
    assert CAP_TAB_USERS_VIEW in caps
    assert CAP_TAB_USERS_EDIT not in caps
    assert CAP_TAB_ORGANIZATIONS_VIEW in caps
    assert CAP_TAB_INVITES_EDIT in caps
    assert CAP_TAB_BILLING_VIEW in caps
    assert CAP_SCOPE_GLOBAL in caps
    assert CAP_SCOPE_INVITED_ORGS in caps


def test_platform_bd_invite_scope_keeps_global_org_ids():
    """Test platform bd invite scope keeps global org ids."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({101, 102}))
    assert scope.org_ids is None
    assert scope.invited_org_ids == frozenset({101, 102})
    assert scope.has_capability(CAP_SCOPE_GLOBAL)
    assert scope.has_capability(CAP_SCOPE_INVITED_ORGS)


def test_platform_bd_to_rls_session_vars_global_read():
    """Test platform bd to rls session vars global read."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({101, 102}))
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map.get("panel_global_read") == "1"
    assert "readable_org_ids" not in vars_map


def test_platform_bd_invited_orgs_still_loaded_in_scope():
    """Test platform bd invited orgs still loaded in scope."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({101, 102}))
    assert scope.invited_org_ids == frozenset({101, 102})


def test_expert_still_uses_readable_org_ids_not_global():
    """Test expert still uses readable org ids not global."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map.get("readable_org_ids") == "10,20"
    assert "panel_global_read" not in vars_map


def test_platform_bd_partial_read_only_flag():
    """Test platform bd partial read only flag."""
    user = _User("platform_bd")
    scope = build_admin_scope(user, lang="en")
    assert scope.read_only is True
    assert scope.has_capability(CAP_TAB_INVITES_EDIT)


def test_superadmin_not_read_only():
    """Test superadmin not read only."""
    user = _User("superadmin")
    scope = build_admin_scope(user, lang="en")
    assert scope.read_only is False


def test_env_superadmin_with_teacher_role_gets_full_caps(monkeypatch):
    """Test env superadmin with teacher role gets full caps."""
    user = _User("teacher")
    user.phone = "13800138000"
    monkeypatch.setattr("utils.auth.roles.ADMIN_PHONES", ["13800138000"])
    monkeypatch.setattr("utils.auth.roles.ADMIN_USER_IDS", [])
    caps = user_panel_capabilities(user)
    assert CAP_SCOPE_GLOBAL in caps
    scope = build_admin_scope(user, lang="en")
    assert scope.read_only is False


def test_personal_paid_rejected():
    """Test personal paid rejected."""
    user = _User("personal_paid")
    with pytest.raises(HTTPException) as exc:
        build_admin_scope(user, lang="en")
    assert exc.value.status_code == 403


def test_all_seven_roles_have_capability_config():
    """Test all seven roles have capability config."""
    validate_role_panel_config()
    assert len(ROLE_PANEL_CAPABILITIES) == len(ALL_USER_ROLES)
