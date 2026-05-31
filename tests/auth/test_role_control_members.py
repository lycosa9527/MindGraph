"""HTTP tests for role control member listing."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, user_id: int = 1):
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = None
    user.phone = "13800000001"
    return user


@pytest.fixture(name="client")
def fixture_client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_teacher_denied_platform_role_members(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("teacher")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/platform-role-members?role=platform_bd")
    assert response.status_code == 403


def test_superadmin_invalid_platform_role_query(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/platform-role-members?role=teacher")
    assert response.status_code == 400


def test_superadmin_platform_role_members_ok(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/platform-role-members?role=expert")
    assert response.status_code == 200
    body = response.json()
    assert "members" in body
    assert isinstance(body["members"], list)
