"""Additional tests for chat-handoff ingest and doc summary session validation."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from config.database import get_async_db
from routers.api.knowledge_space.chat_handoff import router as chat_router
from routers.api.doc_summary import router as doc_router
from services.knowledge.chat_handoff_service import ChatHandoffRecord
from utils.auth import get_current_user

app = FastAPI()
app.include_router(doc_router, prefix="/api")
app.include_router(chat_router, prefix="/api/knowledge-space")


def _make_user(user_id: int = 42) -> SimpleNamespace:
    user = SimpleNamespace()
    user.id = user_id
    user.role = "teacher"
    user.organization_id = 1
    return user


@pytest.fixture(name="client")
def fixture_client() -> TestClient:
    """Return a TestClient bound to the doc summary and chat handoff routes."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_session_start_rejects_unknown_package_id(client: TestClient) -> None:
    """Invalid package_id returns 400 instead of creating a duplicate package."""
    app.dependency_overrides[get_current_user] = _make_user
    with patch("routers.api.doc_summary.session.KnowledgePackageService") as service_cls:
        service = service_cls.return_value
        service.ensure_doc_summary_session = AsyncMock(side_effect=ValueError("Package 999 not found or access denied"))
        response = client.post(
            "/api/doc-summary/session/start",
            json={"package_id": 999},
        )
    assert response.status_code == 400


def test_chat_handoff_ingest_rejects_used_code(client: TestClient) -> None:
    """Ingest rejects pairing codes that are no longer waiting."""
    app.dependency_overrides[get_current_user] = _make_user
    record = ChatHandoffRecord(user_id=42, package_id=3, status="done", document_id=1)
    with (
        patch(
            "routers.api.knowledge_space.chat_handoff.claim_handoff_for_ingest",
            new_callable=AsyncMock,
        ) as claim,
        patch("routers.api.knowledge_space.chat_handoff.load_handoff", new_callable=AsyncMock) as load,
    ):
        claim.return_value = None
        load.return_value = record
        response = client.post(
            "/api/doc-summary/chat-handoff/ingest",
            json={
                "code": "123456",
                "platform": "wechat",
                "chat_title": "Test chat",
                "content": "hello",
            },
        )
    assert response.status_code == 409


def test_chat_handoff_ingest_success(client: TestClient) -> None:
    """Successful ingest adds transcript to package without starting indexing."""
    app.dependency_overrides[get_current_user] = _make_user

    async def _mock_db():
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        yield mock_db

    app.dependency_overrides[get_async_db] = _mock_db

    record = ChatHandoffRecord(user_id=42, package_id=3, status="received")
    document = SimpleNamespace(
        id=88,
        file_name="chat.md",
        file_type="text/markdown",
        file_size=10,
        status="pending",
        chunk_count=0,
        error_message=None,
        processing_progress=None,
        processing_progress_percent=0,
        doc_metadata={},
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        updated_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
    )
    batch = SimpleNamespace(id=3, source="canvas")
    with (
        patch(
            "routers.api.knowledge_space.chat_handoff.claim_handoff_for_ingest",
            new_callable=AsyncMock,
        ) as claim,
        patch("routers.api.knowledge_space.chat_handoff.update_handoff_status", new_callable=AsyncMock) as update,
        patch("routers.api.knowledge_space.chat_handoff.KnowledgePackageService") as service_cls,
    ):
        claim.return_value = record
        service = service_cls.return_value
        service.get_package = AsyncMock(return_value=batch)
        service.add_text_source = AsyncMock(return_value=document)
        response = client.post(
            "/api/doc-summary/chat-handoff/ingest",
            json={
                "code": "123456",
                "platform": "wechat",
                "chat_title": "Test chat",
                "content": "Alice: hi",
                "source_export_name": "chat.txt",
            },
        )
    assert response.status_code == 200
    assert update.await_count == 1
    assert update.await_args_list[0].args[0] == "123456"
    assert update.await_args_list[0].args[1] == "done"
    service.add_text_source.assert_awaited_once()
    await_args = service.add_text_source.await_args
    assert await_args is not None
    add_kwargs = await_args.kwargs
    assert add_kwargs["extra_metadata"]["handoff_code"] == "123456"
    assert add_kwargs["extra_metadata"]["source_export_name"] == "chat.txt"


def test_chat_handoff_ingest_wecom_platform(client: TestClient) -> None:
    """WeCom platform maps to wecom ingest_source metadata."""
    app.dependency_overrides[get_current_user] = _make_user

    async def _mock_db():
        mock_db = MagicMock()
        mock_db.commit = AsyncMock()
        mock_db.add = MagicMock()
        yield mock_db

    app.dependency_overrides[get_async_db] = _mock_db

    record = ChatHandoffRecord(user_id=42, package_id=3, status="received")
    document = SimpleNamespace(
        id=89,
        file_name="wecom-chat.md",
        file_type="text/markdown",
        file_size=10,
        status="processing",
        chunk_count=0,
        error_message=None,
        processing_progress="queued",
        processing_progress_percent=0,
        doc_metadata={},
        created_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
        updated_at=SimpleNamespace(isoformat=lambda: "2026-01-01T00:00:00"),
    )
    batch = SimpleNamespace(id=3, source="canvas")
    with (
        patch(
            "routers.api.knowledge_space.chat_handoff.claim_handoff_for_ingest",
            new_callable=AsyncMock,
        ) as claim,
        patch("routers.api.knowledge_space.chat_handoff.update_handoff_status", new_callable=AsyncMock),
        patch("routers.api.knowledge_space.chat_handoff.KnowledgePackageService") as service_cls,
    ):
        claim.return_value = record
        service = service_cls.return_value
        service.get_package = AsyncMock(return_value=batch)
        service.add_text_source = AsyncMock(return_value=document)
        response = client.post(
            "/api/doc-summary/chat-handoff/ingest",
            json={
                "code": "654321",
                "platform": "wecom",
                "chat_title": "WeCom group",
                "content": "Alice: hi",
            },
        )
    assert response.status_code == 200
    await_args = service.add_text_source.await_args
    assert await_args is not None
    assert await_args.kwargs["source_kind"] == "wecom"
