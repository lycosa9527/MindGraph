"""HTTP-level MindBot admin org-scope tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from main import app
from repositories.mindbot_repo import MindbotConfigRepository
from routers.auth.dependencies import get_language_dependency
from utils.auth import get_current_user


def _make_user(role: str, organization_id: int | None = None, user_id: int = 1):
    """Make user."""
    user = SimpleNamespace()
    user.id = user_id
    user.role = role
    user.organization_id = organization_id
    return user


def _mindbot_config_row(**overrides: object) -> SimpleNamespace:
    """Minimal ORM-like row for list/get admin responses."""
    base = {
        "id": 7,
        "organization_id": 42,
        "bot_label": "Test bot",
        "public_callback_token": "callback-token-abcdef12",
        "dingtalk_robot_code": "ding-robot-1",
        "dingtalk_app_secret": "secret-value",
        "dify_api_key": "dify-key-value",
        "dingtalk_client_id": "client-id",
        "dingtalk_event_token": None,
        "dingtalk_event_aes_key": None,
        "dingtalk_event_owner_key": None,
        "dify_api_base_url": "https://dify.example/v1",
        "dify_timeout_seconds": 300,
        "dify_inputs_json": None,
        "show_chain_of_thought_oto": False,
        "show_chain_of_thought_internal_group": False,
        "show_chain_of_thought_cross_org_group": False,
        "chain_of_thought_max_chars": 4000,
        "dingtalk_ai_card_template_id": None,
        "dingtalk_ai_card_param_key": None,
        "dingtalk_ai_card_streaming_max_chars": 6500,
        "use_org_dify_settings": True,
        "is_enabled": True,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(name="client")
def fixture_client():
    """Fixture client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    """Clear dependency overrides."""
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_school_admin_denied_mindbot_admin(client: TestClient) -> None:
    """School admins no longer have MindBot admin access (matrix alignment)."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin",
        organization_id=42,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"
    response = client.get("/api/mindbot/admin/configs/1")
    assert response.status_code == 403


def test_school_admin_cross_org_mindbot_config_denied(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test school admin cross org mindbot config denied."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "school_admin",
        organization_id=42,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    async def _allow_feature(_user, _feature):
        return True

    async def _fake_config(_config_id, _db):
        return SimpleNamespace(organization_id=99)

    def _noop_feature():
        return None

    def _fake_response(row, _school_manager_view=False):
        return {"id": 1, "organization_id": row.organization_id}

    monkeypatch.setattr(
        "routers.auth.dependencies.user_has_feature_access",
        _allow_feature,
    )
    monkeypatch.setattr(
        "routers.api.mindbot_admin._require_mindbot_feature",
        _noop_feature,
    )
    monkeypatch.setattr(
        "routers.api.mindbot_admin._get_config_or_404",
        _fake_config,
    )
    response = client.get("/api/mindbot/admin/configs/1")
    assert response.status_code == 403


def test_superadmin_list_mindbot_configs_returns_repo_rows(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Superadmin list must not return empty when configs exist (RLS session fix)."""
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        "admin",
        organization_id=None,
    )
    app.dependency_overrides[get_language_dependency] = lambda: "en"

    async def _allow_feature(_user: object, _feature: str) -> bool:
        return True

    row = _mindbot_config_row()

    async def _list_all(_self, *, limit: int = 200, after_id: int | None = None):
        del limit, after_id
        return [row]

    def _noop_feature() -> None:
        return None

    monkeypatch.setattr(
        "routers.auth.dependencies.user_has_feature_access",
        _allow_feature,
    )
    monkeypatch.setattr(
        "routers.api.mindbot_admin._require_mindbot_feature",
        _noop_feature,
    )
    monkeypatch.setattr(MindbotConfigRepository, "list_all", _list_all)

    response = client.get("/api/mindbot/admin/configs")
    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert len(payload) == 1
    assert payload[0]["id"] == row.id
    assert payload[0]["organization_id"] == row.organization_id
    assert payload[0]["public_callback_token"] == row.public_callback_token
