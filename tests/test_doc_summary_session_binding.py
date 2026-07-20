"""Session binding must never resume a Knowledge Space package as Document Summary."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.doc_summary import router
from utils.auth import get_current_user

app = FastAPI()
app.include_router(router, prefix="/api")


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


def test_session_start_rejects_non_doc_summary_package_id(client: TestClient) -> None:
    """Resume with a KS package id is rejected."""
    app.dependency_overrides[get_current_user] = _make_user
    with patch("routers.api.doc_summary.session.KnowledgePackageService") as service_cls:
        service = service_cls.return_value
        service.ensure_doc_summary_session = AsyncMock(
            side_effect=ValueError("Package is not a Document Summary session")
        )
        response = client.post(
            "/api/doc-summary/session/start",
            json={"package_id": 9, "create_if_missing": False},
        )
    assert response.status_code == 400
    assert "Document Summary" in response.json()["detail"]


def test_session_start_creates_doc_summary_when_requested(client: TestClient) -> None:
    """create_if_missing still returns a doc_summary package."""
    app.dependency_overrides[get_current_user] = _make_user
    now = datetime.now(UTC)
    batch = SimpleNamespace(
        id=22,
        name="Title",
        diagram_id="d1",
        source="doc_summary",
        created_at=now,
        updated_at=now,
    )
    with patch("routers.api.doc_summary.session.KnowledgePackageService") as service_cls:
        service = service_cls.return_value
        service.ensure_doc_summary_session = AsyncMock(return_value=batch)
        service.get_package_stats = AsyncMock(return_value={22: {"total": 0, "completed": 0}})
        response = client.post(
            "/api/doc-summary/session/start",
            json={"diagram_id": "d1", "diagram_title": "Title", "create_if_missing": True},
        )
    assert response.status_code == 200
    assert response.json()["source"] == "doc_summary"
