"""Tests for AdminScope and panel capabilities."""

import pytest
from fastapi import HTTPException

from utils.auth.admin_panel_permissions import (
    CAP_PANEL_ACCESS,
    CAP_SCOPE_GLOBAL,
    CAP_TAB_BILLING_VIEW,
    CAP_TAB_INVITES_EDIT,
    CAP_TAB_INVITES_VIEW,
    CAP_TAB_ORGANIZATIONS_VIEW,
    CAP_TAB_USERS_EDIT,
    CAP_TAB_USERS_VIEW,
    capabilities_for_role,
    role_has_panel_access,
)
from utils.auth.admin_scope import build_admin_scope, resolve_effective_org_id


class _User:
    def __init__(self, role: str, organization_id: int | None = None, user_id: int = 1):
        self.role = role
        self.organization_id = organization_id
        self.id = user_id


def test_teacher_has_no_panel_access():
    assert not role_has_panel_access("teacher")
    assert CAP_PANEL_ACCESS not in capabilities_for_role("teacher")


def test_school_admin_has_school_member_caps_without_global_scope():
    caps = capabilities_for_role("school_admin")
    assert CAP_PANEL_ACCESS in caps
    assert CAP_TAB_USERS_VIEW in caps
    assert CAP_TAB_USERS_EDIT in caps
    assert CAP_SCOPE_GLOBAL not in caps


def test_superadmin_has_users_tab():
    caps = capabilities_for_role("superadmin")
    assert CAP_TAB_USERS_VIEW in caps
    assert CAP_SCOPE_GLOBAL in caps


def test_expert_invites_only():
    caps = capabilities_for_role("expert")
    assert CAP_PANEL_ACCESS in caps
    assert CAP_TAB_INVITES_VIEW in caps
    assert CAP_TAB_USERS_VIEW not in caps


def test_build_admin_scope_rejects_teacher():
    user = _User("teacher")
    with pytest.raises(HTTPException) as exc:
        build_admin_scope(user, lang="en")
    assert exc.value.status_code == 403


def test_school_admin_locked_org():
    user = _User("school_admin", organization_id=42)
    scope = build_admin_scope(user, lang="en")
    assert scope.org_ids == frozenset({42})
    assert scope.effective_org_id == 42


def test_school_admin_cross_org_forbidden():
    user = _User("school_admin", organization_id=42)
    with pytest.raises(HTTPException) as exc:
        build_admin_scope(user, organization_id=99, lang="en")
    assert exc.value.status_code == 403


def test_superadmin_requires_org_when_resolving():
    user = _User("superadmin")
    scope = build_admin_scope(user, lang="en")
    with pytest.raises(HTTPException) as exc:
        resolve_effective_org_id(scope, None, "en", require_org_for_superadmin=True)
    assert exc.value.status_code == 400


def test_platform_bd_has_readonly_global_tabs_and_invite_edit():
    caps = capabilities_for_role("platform_bd")
    assert CAP_TAB_USERS_VIEW in caps
    assert CAP_TAB_USERS_EDIT not in caps
    assert CAP_TAB_ORGANIZATIONS_VIEW in caps
    assert CAP_TAB_INVITES_EDIT in caps
    assert CAP_TAB_BILLING_VIEW in caps
    assert CAP_SCOPE_GLOBAL in caps


def test_platform_bd_partial_read_only_flag():
    user = _User("platform_bd")
    scope = build_admin_scope(user, lang="en")
    assert scope.read_only is True
    assert scope.has_capability(CAP_TAB_INVITES_EDIT)


def test_superadmin_not_read_only():
    user = _User("superadmin")
    scope = build_admin_scope(user, lang="en")
    assert scope.read_only is False


def test_env_superadmin_with_teacher_role_gets_full_caps(monkeypatch):
    from utils.auth.admin_panel_permissions import CAP_SCOPE_GLOBAL, user_panel_capabilities

    user = _User("teacher")
    user.phone = "13800138000"
    monkeypatch.setattr("utils.auth.roles.ADMIN_PHONES", ["13800138000"])
    monkeypatch.setattr("utils.auth.roles.ADMIN_USER_IDS", [])
    caps = user_panel_capabilities(user)
    assert CAP_SCOPE_GLOBAL in caps
    scope = build_admin_scope(user, lang="en")
    assert scope.read_only is False


def test_personal_paid_rejected():
    user = _User("personal_paid")
    with pytest.raises(HTTPException) as exc:
        build_admin_scope(user, lang="en")
    assert exc.value.status_code == 403


def test_all_seven_roles_have_capability_config():
    from utils.auth.admin_panel_permissions import ROLE_PANEL_CAPABILITIES, validate_role_panel_config
    from utils.auth.role_constants import ALL_USER_ROLES

    validate_role_panel_config()
    assert len(ROLE_PANEL_CAPABILITIES) == len(ALL_USER_ROLES)
