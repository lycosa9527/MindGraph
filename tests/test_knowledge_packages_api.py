"""HTTP smoke tests for File Center package routes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.knowledge_space.packages import router
from utils.auth import get_current_user


def _make_user(user_id: int = 42) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "teacher"
    user.organization_id = 1
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/knowledge-space")
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides(client: TestClient) -> None:
    client.app.dependency_overrides.clear()
    yield
    client.app.dependency_overrides.clear()


def test_list_packages_requires_authenticated_user(client: TestClient) -> None:
    response = client.get("/api/knowledge-space/packages")
    assert response.status_code in (401, 403)


def test_list_packages_returns_empty_list_when_no_packages(client: TestClient) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: _make_user()
    with patch("routers.api.knowledge_space.packages.KnowledgePackageService") as service_cls:
        service_cls.return_value.list_packages = AsyncMock(return_value=[])
        service_cls.return_value.get_package_stats = AsyncMock(return_value={})
        response = client.get("/api/knowledge-space/packages")
    assert response.status_code == 200
    body = response.json()
    assert body["packages"] == []


def test_create_package_validates_name(client: TestClient) -> None:
    client.app.dependency_overrides[get_current_user] = lambda: _make_user()
    response = client.post("/api/knowledge-space/packages", json={"name": ""})
    assert response.status_code == 422
