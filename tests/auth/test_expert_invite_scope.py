"""Expert invite org scoping tests."""

import pytest
from fastapi import HTTPException
from sqlalchemy.sql import false as sql_false
from sqlalchemy.sql import true as sql_true

from models.domain.auth import Organization
from routers.auth.dependencies import _assert_invite_org_scope
from utils.auth.admin_panel_permissions import CAP_SCOPE_INVITED_ORGS, CAP_TAB_INVITES_EDIT
from utils.auth.admin_scope import (
    assert_resource_org_in_scope,
    build_admin_scope,
    invite_org_filter,
    org_filter,
    org_id_readable_in_panel_scope,
    panel_org_table_filter,
)


class _User:
    """_User helper."""
    def __init__(self, role: str, user_id: int = 1, organization_id: int | None = None):
        """ init  ."""
        self.role = role
        self.id = user_id
        self.organization_id = organization_id
        self.phone: str | None = None


def test_expert_with_invited_orgs_scoped():
    """Test expert with invited orgs scoped."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    assert scope.org_ids == frozenset({10, 20})
    assert scope.has_capability(CAP_SCOPE_INVITED_ORGS)
    assert scope.has_capability(CAP_TAB_INVITES_EDIT)


def test_expert_to_rls_session_vars_matches_invited_org_ids():
    """Test expert to rls session vars matches invited org ids."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    vars_map = scope.to_rls_session_vars()
    assert vars_map["rls_mode"] == "panel"
    assert vars_map["readable_org_ids"] == "10,20"
    assert invite_org_filter(scope, Organization.id) is not None


def test_platform_bd_org_filter_global_read():
    """Test platform bd org filter global read."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    clause = org_filter(scope, Organization.id)
    assert clause is not None
    assert clause.compare(sql_true())


def test_expert_org_filter_still_scoped_without_global():
    """Test expert org filter still scoped without global."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    clause = org_filter(scope, Organization.id)
    assert clause is not None


def test_platform_bd_invite_org_filter_uses_invited_ids():
    """Test platform bd invite org filter uses invited ids."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    clause = invite_org_filter(scope, Organization.id)
    assert clause is not None


def test_invite_org_filter_excludes_all_orgs_when_expert_has_no_invited_ids():
    """Test invite org filter excludes all orgs when expert has no invited ids."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset())
    clause = invite_org_filter(scope, Organization.id)
    assert clause.compare(sql_false())


def test_legacy_null_org_not_readable_for_expert():
    """Test legacy null org not readable for expert."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    assert org_id_readable_in_panel_scope(scope, 999, None) is False
    with pytest.raises(HTTPException) as exc:
        assert_resource_org_in_scope(scope, 999, "en", resource_invited_by_user_id=None)
    assert exc.value.status_code == 404


def test_expert_org_filter_excludes_legacy_null_orgs():
    """Test expert org filter excludes legacy null orgs."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    clause = org_filter(scope, Organization.id)
    assert clause is not None
    assert not clause.compare(sql_false())
    assert org_id_readable_in_panel_scope(scope, 999, None) is False


def test_platform_bd_assert_resource_org_in_scope_blocks_foreign_org():
    """Test platform bd assert resource org in scope blocks foreign org."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    with pytest.raises(HTTPException) as exc:
        assert_resource_org_in_scope(scope, 99, "en", resource_invited_by_user_id=8)
    assert exc.value.status_code == 404


def test_platform_bd_assert_resource_org_in_scope_allows_owned_org():
    """Test platform bd assert resource org in scope allows owned org."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    assert_resource_org_in_scope(scope, 10, "en", resource_invited_by_user_id=9)


def test_panel_org_table_filter_global_bd_sees_all_orgs():
    """Test panel org table filter global bd sees all orgs."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    assert panel_org_table_filter(scope).compare(sql_true())


def test_panel_org_table_filter_allows_legacy_null_only_when_no_invited_ids():
    """Test panel org table filter allows legacy null only when no invited ids."""
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset())
    clause = panel_org_table_filter(scope)
    assert clause is not None
    assert not clause.compare(sql_false())


def test_org_id_readable_blocks_foreign_owned_org():
    """Test org id readable blocks foreign owned org."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    assert org_id_readable_in_panel_scope(scope, 99, 8) is False
    assert org_id_readable_in_panel_scope(scope, 10, 5) is True


def test_require_invite_org_create_allows_expert_scope():
    """Test require invite org create allows expert scope."""
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset())
    _assert_invite_org_scope(scope, "en")


def test_require_invite_org_create_blocks_teacher_like_scope():
    """Test require invite org create blocks teacher like scope."""
    user = _User("school_admin", organization_id=42, user_id=3)
    user.role = "school_admin"
    scope = build_admin_scope(user, lang="en")
    with pytest.raises(HTTPException) as exc:
        _assert_invite_org_scope(scope, "en")
    assert exc.value.status_code == 403
