"""HTTP tests for Dify conversation routes (identity resolution + error mapping)."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import main as _main_app
from clients.dify_exceptions import DifyAPIError, DifyConversationNotFoundError
from config.database import get_async_db
from utils.auth import get_current_user, get_current_user_or_api_key

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


def test_app_parameters_returns_503_when_dify_is_restarting(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dify HTTP 502 is a temporary outage, not an unhandled server error."""
    app.dependency_overrides[get_current_user_or_api_key] = _make_user

    mock_client = MagicMock()
    mock_client.get_app_parameters = AsyncMock(side_effect=DifyAPIError("HTTP 502", status_code=502))

    async def _fake_resolve(*_args, **_kwargs):
        return mock_client

    monkeypatch.setattr(
        "routers.api.dify_files.resolve_mindmate_dify_client_short_lived",
        _fake_resolve,
    )

    response = client.get("/api/dify/app/parameters", headers={"X-Language": "zh"})

    assert response.status_code == 503
    assert "暂时不可用" in response.json()["detail"]


def test_conversation_list_returns_503_when_dify_is_restarting(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing history during a Dify restart fails closed instead of returning no rows."""
    app.dependency_overrides[get_current_user] = _make_user

    async def _fake_db():
        yield MagicMock()

    app.dependency_overrides[get_async_db] = _fake_db

    async def _raise_outage(*_args, **_kwargs):
        raise DifyAPIError("HTTP 502", status_code=502)

    monkeypatch.setattr(
        "routers.api.dify_conversations.list_unified_conversations",
        _raise_outage,
    )

    response = client.get("/api/dify/conversations?limit=20", headers={"X-Language": "zh"})

    assert response.status_code == 503
    assert "暂时不可用" in response.json()["detail"]
