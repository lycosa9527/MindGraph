"""Tests for org-level Dify / MindBot settings unification."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from routers.api import mindbot_helpers as mindbot_helpers_mod
from routers.api.mindbot_models import MindbotConfigCreatePayload
from routers.auth.admin import organization_dify as org_dify_mod
from services.dify import org_mindmate_client as mindmate_client_mod


def _org(**overrides: object) -> SimpleNamespace:
    base = {
        "id": 1,
        "dify_api_base_url": None,
        "dify_api_key": None,
        "dify_timeout_seconds": 120,
        "show_chain_of_thought_oto": True,
        "show_chain_of_thought_internal_group": False,
        "show_chain_of_thought_cross_org_group": False,
        "chain_of_thought_max_chars": 5000,
        "dingtalk_ai_card_streaming_max_chars": 7000,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _mindbot_row(**overrides: object) -> SimpleNamespace:
    base = {
        "dify_api_base_url": "https://old.example/v1",
        "dify_api_key": "old-key",
        "dify_timeout_seconds": 300,
        "show_chain_of_thought_oto": False,
        "show_chain_of_thought_internal_group": False,
        "show_chain_of_thought_cross_org_group": False,
        "chain_of_thought_max_chars": 4000,
        "dingtalk_ai_card_streaming_max_chars": 6500,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_propagate_org_dify_skips_custom_bots(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        org_dify_mod,
        "resolve_organization_dify_credentials",
        lambda _org: ("school-key", "https://school.example/v1"),
    )
    org = _org()
    linked = _mindbot_row(use_org_dify_settings=True)
    custom = _mindbot_row(
        use_org_dify_settings=False,
        dify_api_base_url="https://custom.example/v1",
        dify_api_key="custom-key",
    )

    class _Scalars:
        def all(self) -> list[SimpleNamespace]:
            return [linked, custom]

    class _Result:
        def scalars(self) -> _Scalars:
            return _Scalars()

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())

    await org_dify_mod.propagate_org_dify_settings_to_mindbot_configs(db, org)

    assert linked.dify_api_key == "school-key"
    assert custom.dify_api_key == "custom-key"
    assert custom.dify_api_base_url == "https://custom.example/v1"


def test_mindbot_row_supports_use_org_dify_settings_flag() -> None:
    row = _mindbot_row(use_org_dify_settings=False)
    assert row.use_org_dify_settings is False


def test_apply_org_dify_fields_updates_behavior_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        org_dify_mod,
        "resolve_organization_dify_credentials",
        lambda _org: ("", ""),
    )
    org = _org()
    row = _mindbot_row()
    org_dify_mod.apply_org_dify_fields_to_mindbot_config(org, row)
    assert row.dify_timeout_seconds == 120
    assert row.show_chain_of_thought_oto is True
    assert row.chain_of_thought_max_chars == 5000
    assert row.dingtalk_ai_card_streaming_max_chars == 7000
    assert row.dify_api_base_url == "https://old.example/v1"
    assert row.dify_api_key == "old-key"


def test_apply_org_dify_fields_updates_credentials_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        org_dify_mod,
        "resolve_organization_dify_credentials",
        lambda _org: ("school-key", "https://school.example/v1"),
    )
    org = _org()
    row = _mindbot_row()
    org_dify_mod.apply_org_dify_fields_to_mindbot_config(org, row)
    assert row.dify_api_base_url == "https://school.example/v1"
    assert row.dify_api_key == "school-key"
    assert row.dify_timeout_seconds == 120


def test_resolved_dify_settings_use_org_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mindbot_helpers_mod,
        "resolve_organization_dify_credentials",
        lambda _org: ("org-key", "https://org.example/v1"),
    )
    org = _org()
    payload = MindbotConfigCreatePayload(
        organization_id=1,
        dingtalk_robot_code="robot-a",
        dingtalk_app_secret="secret",
        use_org_dify_settings=True,
    )
    settings = mindbot_helpers_mod._resolved_dify_settings(
        payload,
        org,
        None,
        resolved_dify_key="",
    )
    assert settings["dify_api_key"] == "org-key"
    assert settings["dify_api_base_url"] == "https://org.example/v1"
    assert settings["dify_timeout_seconds"] == 120
    assert settings["show_chain_of_thought_oto"] is True


def test_resolved_dify_settings_requires_org_credentials_when_flag_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        mindbot_helpers_mod,
        "resolve_organization_dify_credentials",
        lambda _org: ("", ""),
    )
    org = _org()
    payload = MindbotConfigCreatePayload(
        organization_id=1,
        dingtalk_robot_code="robot-a",
        dingtalk_app_secret="secret",
        use_org_dify_settings=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        mindbot_helpers_mod._resolved_dify_settings(
            payload,
            org,
            None,
            resolved_dify_key="",
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_mindmate_client_keeps_org_timeout_with_global_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    org = _org(dify_api_base_url=None, dify_api_key=None, dify_timeout_seconds=120)

    class _Result:
        def scalar_one_or_none(self) -> SimpleNamespace:
            return org

    db = AsyncMock()
    db.execute = AsyncMock(return_value=_Result())

    monkeypatch.setenv("DIFY_API_KEY", "global-key")
    monkeypatch.setenv("DIFY_API_URL", "https://global.example/v1")
    monkeypatch.setenv("DIFY_TIMEOUT", "300")

    client = await mindmate_client_mod.resolve_mindmate_dify_client(db, 1)
    assert client.api_key == "global-key"
    assert client.api_url == "https://global.example/v1"
    assert client.timeout == 120
