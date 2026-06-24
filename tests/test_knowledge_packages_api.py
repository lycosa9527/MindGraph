"""HTTP smoke tests for File Center package routes."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.knowledge_space.packages import router
from utils.auth import get_current_user

app = FastAPI()
app.include_router(router, prefix="/api/knowledge-space")


def _make_user(user_id: int = 42) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "teacher"
    user.organization_id = 1
    return user


def _override_current_user() -> SimpleNamespace:
    return _make_user()


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Return a TestClient bound to the package routes app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_list_packages_requires_authenticated_user(client: TestClient) -> None:
    """Unauthenticated requests are rejected."""
    response = client.get("/api/knowledge-space/packages")
    assert response.status_code in (401, 403)


def test_list_packages_returns_empty_list_when_no_packages(client: TestClient) -> None:
    """Authenticated list returns an empty package list when none exist."""
    app.dependency_overrides[get_current_user] = _override_current_user
    with patch("routers.api.knowledge_space.packages.KnowledgePackageService") as service_cls:
        service_cls.return_value.list_packages = AsyncMock(return_value=[])
        service_cls.return_value.get_package_stats = AsyncMock(return_value={})
        response = client.get("/api/knowledge-space/packages")
    assert response.status_code == 200
    body = response.json()
    assert body["packages"] == []


def test_create_package_validates_name(client: TestClient) -> None:
    """Create package rejects empty names."""
    app.dependency_overrides[get_current_user] = _override_current_user
    response = client.post("/api/knowledge-space/packages", json={"name": ""})
    assert response.status_code == 422
