"""HTTP tests for Dify conversation routes (identity resolution + error mapping)."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import main as _main_app
from clients.dify_exceptions import DifyConversationNotFoundError
from config.database import get_async_db
from utils.auth import get_current_user

assert _main_app.app.title

app = _main_app.app


@pytest.fixture(name="client")
def client_fixture() -> TestClient:
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset auth/db overrides after each test."""
    yield
    app.dependency_overrides.clear()


def _make_user(user_id: int = 3) -> SimpleNamespace:
    return SimpleNamespace(id=user_id, organization_id=5, name="Alice", phone="", email="")


@pytest.mark.asyncio
async def test_get_conversation_messages_maps_not_found_to_404(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MindBot conversation misses return 404 instead of an unhandled 500."""
    app.dependency_overrides[get_current_user] = _make_user

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_async_db] = _fake_db

    async def _raise_not_found(*_args, **_kwargs):
        raise DifyConversationNotFoundError("Conversation Not Exists")

    mock_client = MagicMock()
    mock_client.get_messages = AsyncMock(side_effect=_raise_not_found)

    async def _fake_resolve(*_args, **_kwargs):
        return mock_client, "mg_user_3"

    monkeypatch.setattr(
        "routers.api.dify_conversations.resolve_client_and_dify_user",
        _fake_resolve,
    )

    response = client.get("/api/dify/conversations/missing-id/messages?limit=20")

    assert response.status_code == 404
    assert "Conversation Not Exists" in response.json()["detail"]
