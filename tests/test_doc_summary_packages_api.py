"""HTTP tests for Document Summary package aliases under /api/doc-summary."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from models.responses import PackageListResponse, PackageResponse
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


def test_list_packages_filters_to_doc_summary(client: TestClient) -> None:
    """GET /api/doc-summary/packages returns only doc_summary sources."""
    app.dependency_overrides[get_current_user] = _make_user
    now = datetime.now(UTC).isoformat()
    with patch(
        "routers.api.doc_summary.packages.ks_packages.list_packages",
        new_callable=AsyncMock,
    ) as list_mock:
        list_mock.return_value = PackageListResponse(
            packages=[
                PackageResponse(
                    id=1,
                    name="Summary",
                    diagram_id=None,
                    source="doc_summary",
                    status="empty",
                    document_count=0,
                    completed_count=0,
                    created_at=now,
                    updated_at=now,
                ),
                PackageResponse(
                    id=2,
                    name="RAG",
                    diagram_id=None,
                    source="canvas",
                    status="empty",
                    document_count=0,
                    completed_count=0,
                    created_at=now,
                    updated_at=now,
                ),
            ],
            total=2,
            wiki_compile_enabled=False,
        )
        response = client.get("/api/doc-summary/packages")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["packages"][0]["source"] == "doc_summary"


def test_get_package_rejects_non_doc_summary(client: TestClient) -> None:
    """Detail endpoint rejects Knowledge Space packages."""
    app.dependency_overrides[get_current_user] = _make_user
    batch = SimpleNamespace(id=3, source="canvas")
    with patch("routers.api.doc_summary.packages.KnowledgePackageService") as service_cls:
        service = service_cls.return_value
        service.get_package = AsyncMock(return_value=batch)
        response = client.get("/api/doc-summary/packages/3")
    assert response.status_code == 400
    assert "Document Summary" in response.json()["detail"]
