"""HTTP tests for admin user activity timeline."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from config.database import get_async_db
from main import app
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    """Build a minimal user stub for dependency overrides."""
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    return user


def _mock_db_with_user(user: SimpleNamespace | None) -> AsyncMock:
    """Return an async session mock whose execute returns the given user."""
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = user
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)
    return mock_db


@pytest.fixture(name="client")
def fixture_client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Reset dependency overrides between tests."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_expert_denied_user_activity(client: TestClient) -> None:
    """Experts cannot read the user activity timeline."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("expert", user_id=5)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/users/1/activity")
    assert response.status_code == 403


def test_platform_bd_can_read_user_activity(client: TestClient) -> None:
    """Platform BD is not blocked by the users-read gate."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/users/999999/activity")
    assert response.status_code != 403


def test_user_not_found_returns_404(client: TestClient) -> None:
    """Missing target user returns 404."""
    mock_db = _mock_db_with_user(None)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    app.dependency_overrides[get_async_db] = override_db

    response = client.get("/api/auth/admin/users/1/activity")
    assert response.status_code == 404


def test_invalid_source_returns_400(client: TestClient) -> None:
    """Invalid source filter returns 400."""
    target_user = SimpleNamespace(id=1, organization_id=2)
    mock_db = _mock_db_with_user(target_user)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    app.dependency_overrides[get_async_db] = override_db

    with patch(
        "routers.auth.admin.user_activity.assert_panel_user_readable",
        new=AsyncMock(),
    ):
        response = client.get("/api/auth/admin/users/1/activity?source=invalid")
    assert response.status_code == 400


def test_activity_response_shape(client: TestClient) -> None:
    """Successful list returns items and hasMore."""
    target_user = SimpleNamespace(id=1, organization_id=2)
    mock_db = _mock_db_with_user(target_user)
    activity_row = SimpleNamespace(
        id=10,
        user_id=1,
        organization_id=2,
        source="mindmate",
        action="chat_turn",
        title=None,
        prompt_preview="Hello",
        reply_preview="Hi",
        diagram_type=None,
        diagram_id=None,
        conversation_id="conv-1",
        total_tokens=12,
        success=True,
        created_at=SimpleNamespace(isoformat=lambda: "2026-06-19T12:00:00+00:00"),
    )

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    app.dependency_overrides[get_async_db] = override_db

    with (
        patch(
            "routers.auth.admin.user_activity.assert_panel_user_readable",
            new=AsyncMock(),
        ),
        patch(
            "routers.auth.admin.user_activity.list_user_usage_activities",
            new=AsyncMock(return_value=[activity_row]),
        ),
        patch(
            "routers.auth.admin.user_activity.activity_to_admin_dict",
            return_value={
                "id": 10,
                "userId": 1,
                "source": "mindmate",
                "action": "chat_turn",
                "promptPreview": "Hello",
                "replyPreview": "Hi",
                "totalTokens": 12,
                "success": True,
                "createdAt": "2026-06-19T12:00:00+00:00",
            },
        ),
    ):
        response = client.get("/api/auth/admin/users/1/activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["hasMore"] is False
    assert len(payload["items"]) == 1
    assert payload["items"][0]["source"] == "mindmate"
