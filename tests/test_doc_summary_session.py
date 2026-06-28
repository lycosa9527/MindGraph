"""HTTP tests for Document Summary session start."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.knowledge_space.doc_summary import router
from utils.auth import get_current_user

app = FastAPI()
app.include_router(router, prefix="/api/knowledge-space")


def _make_user(user_id: int = 42) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "teacher"
    user.organization_id = 1
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Return a TestClient bound to the doc summary routes app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_session_start_requires_auth(client: TestClient) -> None:
    """Unauthenticated session start is rejected."""
    response = client.post("/api/knowledge-space/doc-summary/session/start", json={})
    assert response.status_code in (401, 403)


def test_session_start_returns_package(client: TestClient) -> None:
    """Authenticated session start returns package metadata."""
    app.dependency_overrides[get_current_user] = _make_user
    now = datetime.now(UTC)
    batch = SimpleNamespace(
        id=7,
        name="Test package",
        diagram_id=None,
        source="doc_summary",
        created_at=now,
        updated_at=now,
    )
    with patch("routers.api.knowledge_space.doc_summary.KnowledgePackageService") as service_cls:
        service = service_cls.return_value
        service.ensure_doc_summary_session = AsyncMock(return_value=batch)
        service.get_package_stats = AsyncMock(return_value={7: {"total": 0, "completed": 0}})
        response = client.post(
            "/api/knowledge-space/doc-summary/session/start",
            json={"diagram_title": "My diagram"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 7
    assert body["source"] == "doc_summary"
    assert body["status"] == "empty"
