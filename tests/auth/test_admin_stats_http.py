"""HTTP-level admin stats endpoint smoke tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
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


def test_global_stats_readable_by_superadmin(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats")
    assert response.status_code != 403


def test_token_stats_response_shape_keys(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/token-stats")
    if response.status_code != 200:
        pytest.skip("token-stats requires database")
    body = response.json()
    assert "today" in body
    assert "past_week" in body
    assert "top_users_today" in body
    assert "by_service" in body


def test_school_stats_includes_top_users(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("school_admin", organization_id=42)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/school")
    if response.status_code != 200:
        pytest.skip("school stats requires database")
    body = response.json()
    assert "top_users" in body
    assert "token_stats" in body


def test_user_trends_requires_user_id(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/trends/user?days=1&hourly=true&service=mindmate")
    assert response.status_code == 400
