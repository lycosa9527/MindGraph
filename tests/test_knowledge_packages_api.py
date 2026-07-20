"""HTTP smoke tests for File Center package routes."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.database import get_async_db
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
    with (
        patch("routers.api.knowledge_space.packages.KnowledgePackageService") as service_cls,
        patch("routers.api.knowledge_space.packages.config") as config,
    ):
        config.FILE_CENTER_WIKI_COMPILE = True
        service_cls.return_value.list_packages = AsyncMock(return_value=[])
        service_cls.return_value.get_package_stats = AsyncMock(return_value={})
        response = client.get("/api/knowledge-space/packages")
    assert response.status_code == 200
    body = response.json()
    assert body["packages"] == []
    assert body["wiki_compile_enabled"] is True


def test_create_package_validates_name(client: TestClient) -> None:
    """Create package rejects empty names."""
    app.dependency_overrides[get_current_user] = _override_current_user
    response = client.post("/api/knowledge-space/packages", json={"name": ""})
    assert response.status_code == 422


def test_create_package_rejects_when_at_limit(client: TestClient) -> None:
    """Create package returns 400 when the user already has three packages."""
    app.dependency_overrides[get_current_user] = _override_current_user
    with patch("routers.api.knowledge_space.packages.KnowledgePackageService") as service_cls:
        service_cls.return_value.create_package = AsyncMock(
            side_effect=ValueError("Maximum 3 packages allowed per user")
        )
        response = client.post("/api/knowledge-space/packages", json={"name": "Fourth"})
    assert response.status_code == 400
    assert "Maximum 3 packages" in response.json()["detail"]


def test_ingest_text_does_not_start_processing(client: TestClient) -> None:
    """Text ingest stores a pending source without enqueueing Celery."""
    app.dependency_overrides[get_current_user] = _override_current_user
    document = SimpleNamespace(
        id=5,
        file_name="note.md",
        file_type="text/markdown",
        file_size=12,
        status="pending",
        chunk_count=0,
        error_message=None,
        processing_progress=None,
        processing_progress_percent=0,
        doc_metadata={},
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        updated_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
    )
    with (
        patch("routers.api.knowledge_space.packages.KnowledgePackageService") as service_cls,
        patch("routers.api.knowledge_space.packages.process_document_task") as task,
    ):
        service = service_cls.return_value
        service.get_package = AsyncMock(return_value=SimpleNamespace(id=3, source="canvas"))
        service.add_text_source = AsyncMock(return_value=document)
        response = client.post(
            "/api/knowledge-space/packages/3/documents/ingest-text",
            json={"content": "hello world", "title": "Note"},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    task.delay.assert_not_called()


def test_start_package_processing_enqueues_pending_sources(client: TestClient) -> None:
    """Start-processing indexes pending package sources on demand."""
    app.dependency_overrides[get_current_user] = _override_current_user

    async def _mock_db():
        mock_db = SimpleNamespace()
        mock_db.commit = AsyncMock()
        mock_db.add = lambda _doc: None
        yield mock_db

    app.dependency_overrides[get_async_db] = _mock_db

    pending = SimpleNamespace(
        id=9,
        status="pending",
        processing_progress=None,
        processing_progress_percent=0,
    )
    completed = SimpleNamespace(id=8, status="completed")
    package = SimpleNamespace(id=3)
    with (
        patch("routers.api.knowledge_space.packages.KnowledgePackageService") as service_cls,
        patch("routers.api.knowledge_space.packages.process_document_task") as task,
    ):
        service = service_cls.return_value
        service.get_package = AsyncMock(return_value=package)
        service.get_package_documents = AsyncMock(return_value=[completed, pending])
        response = client.post("/api/knowledge-space/packages/3/documents/start-processing")
    assert response.status_code == 200
    body = response.json()
    assert body["processed_count"] == 1
    assert pending.status == "processing"
    task.delay.assert_called_once_with(42, 9)
