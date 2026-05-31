"""Expert invite org scoping tests."""

import pytest
from fastapi import HTTPException
from sqlalchemy.sql import false as sql_false

from utils.auth.admin_panel_permissions import CAP_SCOPE_INVITED_ORGS, CAP_TAB_INVITES_EDIT
from utils.auth.admin_scope import (
    assert_resource_org_in_scope,
    build_admin_scope,
    invite_org_filter,
    org_filter,
    org_id_readable_in_panel_scope,
    panel_org_table_filter,
)
from models.domain.auth import Organization


class _User:
    def __init__(self, role: str, user_id: int = 1, organization_id: int | None = None):
        self.role = role
        self.id = user_id
        self.organization_id = organization_id


def test_expert_with_invited_orgs_scoped():
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    assert scope.org_ids == frozenset({10, 20})
    assert scope.has_capability(CAP_SCOPE_INVITED_ORGS)
    assert scope.has_capability(CAP_TAB_INVITES_EDIT)


def test_expert_org_filter_excludes_uninvited():
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    clause = org_filter(scope, Organization.id)
    assert clause is not None


def test_platform_bd_invite_org_filter_uses_invited_ids():
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    clause = invite_org_filter(scope, Organization.id)
    assert clause is not None


def test_invite_org_filter_includes_legacy_null_when_no_invited_ids():
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset())
    clause = invite_org_filter(scope, Organization.id)
    assert clause is not None
    assert clause != sql_false()


def test_legacy_null_org_readable_for_expert():
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    assert org_id_readable_in_panel_scope(scope, 999, None) is True
    assert_resource_org_in_scope(scope, 999, "en", resource_invited_by_user_id=None)


def test_expert_org_filter_includes_legacy_via_subquery():
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    clause = org_filter(scope, Organization.id)
    assert clause is not None
    assert clause != sql_false()


def test_platform_bd_assert_resource_org_in_scope_blocks_foreign_org():
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    with pytest.raises(HTTPException) as exc:
        assert_resource_org_in_scope(scope, 99, "en", resource_invited_by_user_id=8)
    assert exc.value.status_code == 404


def test_platform_bd_assert_resource_org_in_scope_allows_owned_org():
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10, 20}))
    assert_resource_org_in_scope(scope, 10, "en", resource_invited_by_user_id=9)


def test_panel_org_table_filter_allows_legacy_null_only_when_no_invited_ids():
    user = _User("platform_bd", user_id=9)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset())
    clause = panel_org_table_filter(scope)
    assert clause is not None
    assert clause != sql_false()


def test_org_id_readable_blocks_foreign_owned_org():
    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset({10}))
    assert org_id_readable_in_panel_scope(scope, 99, 8) is False
    assert org_id_readable_in_panel_scope(scope, 10, 5) is True


def test_require_invite_org_create_allows_expert_scope():
    from routers.auth.dependencies import _assert_invite_org_scope

    user = _User("expert", user_id=5)
    scope = build_admin_scope(user, lang="en", invited_org_ids=frozenset())
    _assert_invite_org_scope(scope, "en")


def test_require_invite_org_create_blocks_teacher_like_scope():
    from routers.auth.dependencies import _assert_invite_org_scope

    user = _User("school_admin", organization_id=42, user_id=3)
    user.role = "school_admin"
    scope = build_admin_scope(user, lang="en")
    with pytest.raises(HTTPException) as exc:
        _assert_invite_org_scope(scope, "en")
    assert exc.value.status_code == 403
