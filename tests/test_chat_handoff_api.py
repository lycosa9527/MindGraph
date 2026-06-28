"""HTTP tests for chat-handoff pairing routes."""

from __future__ import annotations

from collections.abc import Generator
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers.api.knowledge_space.chat_handoff import router
from services.knowledge.chat_handoff_service import ChatHandoffRecord
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
    """Return a TestClient bound to the chat handoff routes app."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides before and after each test."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_chat_handoff_start_mints_code(client: TestClient) -> None:
    """Start endpoint returns a six-digit pairing code."""
    app.dependency_overrides[get_current_user] = _make_user
    batch = SimpleNamespace(id=3)
    with (
        patch("routers.api.knowledge_space.chat_handoff.KnowledgePackageService") as service_cls,
        patch("routers.api.knowledge_space.chat_handoff.mint_handoff_code", new_callable=AsyncMock) as mint,
    ):
        service_cls.return_value.get_package = AsyncMock(return_value=batch)
        mint.return_value = "123456"
        response = client.post(
            "/api/knowledge-space/chat-handoff/start",
            json={"package_id": 3},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "123456"
    assert body["package_id"] == 3


def test_chat_handoff_waiting_lists_sessions(client: TestClient) -> None:
    """Waiting endpoint returns active pairing sessions for the user."""
    app.dependency_overrides[get_current_user] = partial(_make_user, 42)
    batch = SimpleNamespace(id=3, name="Diagram package", diagram_id=None)
    waiting = SimpleNamespace(
        code="654321",
        package_id=3,
        status="waiting",
        expires_in_seconds=540,
    )
    with (
        patch(
            "routers.api.knowledge_space.chat_handoff.list_waiting_handoffs",
            new_callable=AsyncMock,
            return_value=[waiting],
        ),
        patch("routers.api.knowledge_space.chat_handoff.KnowledgePackageService") as service_cls,
    ):
        service_cls.return_value.get_package = AsyncMock(return_value=batch)
        response = client.get("/api/knowledge-space/chat-handoff/waiting")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["sessions"][0]["code"] == "654321"
    assert body["sessions"][0]["package_name"] == "Diagram package"


def test_chat_handoff_status_not_found(client: TestClient) -> None:
    """Status returns 404 for unknown codes."""
    app.dependency_overrides[get_current_user] = _make_user
    with patch(
        "routers.api.knowledge_space.chat_handoff.load_handoff",
        new_callable=AsyncMock,
        return_value=None,
    ):
        response = client.get("/api/knowledge-space/chat-handoff/status?code=000000")
    assert response.status_code == 404


def test_chat_handoff_status_returns_record(client: TestClient) -> None:
    """Status returns handoff metadata for the owning user."""
    app.dependency_overrides[get_current_user] = partial(_make_user, 42)
    record = ChatHandoffRecord(user_id=42, package_id=3, status="waiting")
    with patch(
        "routers.api.knowledge_space.chat_handoff.load_handoff",
        new_callable=AsyncMock,
        return_value=record,
    ):
        response = client.get("/api/knowledge-space/chat-handoff/status?code=123456")
    assert response.status_code == 200
    assert response.json()["status"] == "waiting"
