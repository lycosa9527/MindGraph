"""HTTP-level admin stats trends query-parameter and access tests."""

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


def test_org_trends_requires_org_identifier(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/trends/organization?days=1&hourly=true&service=mindmate")
    assert response.status_code == 400


def test_user_trends_requires_user_id(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/trends/user?days=1&hourly=true")
    assert response.status_code == 400


def test_school_trends_service_param_not_forbidden_for_manager(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin",
        organization_id=42,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/school/trends?days=1&hourly=true&service=mindgraph")
    assert response.status_code != 403


def test_global_token_trends_accepts_service_filter(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _make_user("superadmin")
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/stats/trends?metric=tokens&days=7&service=mindgraph")
    assert response.status_code != 403
    assert response.status_code != 422
