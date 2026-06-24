"""HTTP tests for admin organization activity timeline."""

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
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    return user


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


def test_expert_denied_org_activity(client: TestClient) -> None:
    """Experts cannot read organization activity timeline."""
    app.dependency_overrides[get_current_user] = lambda: _make_user("expert", user_id=5)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/auth/admin/organizations/1/activity")
    assert response.status_code == 403


def test_org_not_found_returns_404(client: TestClient) -> None:
    """Missing organization returns 404."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=mock_result)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    app.dependency_overrides[get_async_db] = override_db

    response = client.get("/api/auth/admin/organizations/999/activity")
    assert response.status_code == 404


def test_org_activity_response_shape(client: TestClient) -> None:
    """Successful list returns items with userName enrichment."""
    org = SimpleNamespace(id=2, name="Test School")
    activity_row = SimpleNamespace(
        id=10,
        user_id=7,
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

    async def mock_execute(stmt, *_args, **_kwargs):
        mock_result = MagicMock()
        sql = str(stmt)
        if "FROM organizations" in sql or "organizations.id" in sql:
            mock_result.scalar_one_or_none.return_value = org
        elif "FROM users" in sql and "users.id" in sql:
            mock_result.all.return_value = [
                SimpleNamespace(id=7, name="Teacher A", phone="13800000000"),
            ]
        else:
            mock_result.scalar_one_or_none.return_value = None
            mock_result.all.return_value = []
        return mock_result

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=mock_execute)

    async def override_db():
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: _make_user("platform_bd", user_id=9)
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    app.dependency_overrides[get_async_db] = override_db

    with patch(
        "routers.auth.admin.organizations.assert_panel_org_readable",
        new=AsyncMock(),
    ), patch(
        "routers.auth.admin.organizations.list_org_usage_activities",
        new=AsyncMock(return_value=[activity_row]),
    ), patch(
        "routers.auth.admin.organizations.activity_to_admin_dict",
        return_value={
            "id": 10,
            "userId": 7,
            "source": "mindmate",
            "action": "chat_turn",
            "promptPreview": "Hello",
            "replyPreview": "Hi",
            "totalTokens": 12,
            "success": True,
            "createdAt": "2026-06-19T12:00:00+00:00",
        },
    ):
        response = client.get("/api/auth/admin/organizations/2/activity")

    assert response.status_code == 200
    payload = response.json()
    assert payload["hasMore"] is False
    assert len(payload["items"]) == 1
    assert payload["items"][0]["userName"] == "Teacher A"
