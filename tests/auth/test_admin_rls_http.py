"""HTTP-level admin RLS tests using dependency overrides."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    return user


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_teacher_denied_school_stats(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("teacher")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/school?organization_id=1")
    assert response.status_code == 403


def test_school_admin_cross_org_denied(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin", organization_id=42
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/school?organization_id=99")
    assert response.status_code == 403


def test_school_admin_cross_org_school_users_denied(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin", organization_id=42
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/school/users?organization_id=99")
    assert response.status_code == 403


def test_school_admin_missing_org_query_not_cross_org_error(client: TestClient) -> None:
    """Managers omit organization_id; must not be treated as cross-org (403)."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin", organization_id=42
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/school")
    assert response.status_code != 403


def test_school_admin_denied_global_stats(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin", organization_id=42
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats")
    assert response.status_code == 403


def test_platform_bd_denied_school_user_update(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.put(
        "/api/auth/admin/school/users/1?organization_id=1",
        json={"name": "Test User"},
    )
    assert response.status_code == 403


def test_teacher_capabilities_empty_panel(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("teacher")
    response = client.get("/api/auth/admin/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["panel_access"] is False
    assert body["capabilities"] == []


def test_superadmin_capabilities_full_panel(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    response = client.get("/api/auth/admin/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert body["panel_access"] is True
    assert body["read_only"] is False
    assert "scope.global" in body["capabilities"]
    assert "tab.data_center.view" in body["capabilities"]


def test_platform_bd_mutation_blocked_on_scope() -> None:
    from utils.auth.admin_scope import build_admin_scope

    user = _make_user("platform_bd")
    scope = build_admin_scope(user, lang="en")
    with pytest.raises(HTTPException) as exc:
        scope.assert_mutation_allowed("en")
    assert exc.value.status_code == 403
