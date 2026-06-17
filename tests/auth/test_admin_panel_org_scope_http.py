"""HTTP-level admin panel org scope tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    """Make user."""
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    return user


@pytest.fixture(name="client")
def fixture_client():
    """Fixture client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Clear dependency overrides."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_expert_denied_global_organizations(client: TestClient) -> None:
    """Test expert denied global organizations."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("expert", user_id=5)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/organizations")
    assert response.status_code == 403


def test_expert_denied_global_user_detail(client: TestClient) -> None:
    """Test expert denied global user detail."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("expert", user_id=5)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/users/1")
    assert response.status_code == 403


def test_expert_denied_organization_trends(client: TestClient) -> None:
    """Test expert denied organization trends."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("expert", user_id=5)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/trends/organization?organization_id=1")
    assert response.status_code == 403


def test_platform_bd_denied_global_user_update(client: TestClient) -> None:
    """Test platform bd denied global user update."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.put("/api/auth/admin/users/1", json={"name": "Test"})
    assert response.status_code == 403


def test_platform_bd_can_read_global_stats(client: TestClient) -> None:
    """Test platform bd can read global stats."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats")
    assert response.status_code != 403
