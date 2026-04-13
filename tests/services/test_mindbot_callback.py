"""Tests for MindBot DingTalk callback orchestration (no live HTTP)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.domain.mindbot_config import OrganizationMindbotConfig


@pytest.mark.asyncio
async def test_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.config",
        SimpleNamespace(FEATURE_MINDBOT=False),
    )
    from services.mindbot.mindbot_callback import process_dingtalk_callback

    session = AsyncMock()
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header="1",
        sign_header="1",
        body={},
    )
    assert code == 404
    assert "MINDBOT_FEATURE_DISABLED" in hdr.get("X-MindBot-Error-Code", "")


@pytest.mark.asyncio
async def test_missing_robot_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    from services.mindbot.mindbot_callback import process_dingtalk_callback

    session = AsyncMock()
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header="1",
        sign_header="1",
        body={"text": {"content": "hi"}},
    )
    assert code == 400
    assert "MINDBOT_MISSING_ROBOT_CODE" in hdr.get("X-MindBot-Error-Code", "")


def _sample_cfg() -> OrganizationMindbotConfig:
    row = OrganizationMindbotConfig(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        public_callback_token="tok_test_12345678901234567890",
        dingtalk_app_secret="test-secret-for-hmac-signing-32chars!!",
        dingtalk_client_id=None,
        dify_api_base_url="https://example.com/v1",
        dify_api_key="k",
        dify_timeout_seconds=30,
        is_enabled=True,
    )
    row.id = 1
    return row


@pytest.mark.asyncio
async def test_invalid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.is_redis_available",
        lambda: False,
    )

    cfg = _sample_cfg()

    class _FakeRepo:
        def __init__(self, _session: object) -> None:
            pass

        async def get_by_robot_code(self, _rc: str) -> OrganizationMindbotConfig:
            return cfg

    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.MindbotConfigRepository",
        _FakeRepo,
    )

    from services.mindbot.mindbot_callback import process_dingtalk_callback

    session = AsyncMock()
    body = {
        "robotCode": "robot-1",
        "msgtype": "text",
        "text": {"content": "hello"},
    }
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header="1730000000000",
        sign_header="not-the-real-signature",
        body=body,
    )
    assert code == 401
    assert "MINDBOT_INVALID_SIGNATURE" in hdr.get("X-MindBot-Error-Code", "")


@pytest.mark.asyncio
async def test_shared_connectivity_probe_empty_body_no_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared URL: DingTalk may POST empty body with no robotCode when saving the message URL."""
    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    from services.mindbot.mindbot_callback import process_dingtalk_callback

    session = AsyncMock()
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header=None,
        sign_header=None,
        body={},
    )
    assert code == 200
    assert hdr.get("X-MindBot-Error-Code") == "MINDBOT_OK"


@pytest.mark.asyncio
async def test_per_org_connectivity_probe_empty_body_no_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DingTalk console may POST empty JSON with no timestamp/sign when validating URL."""
    monkeypatch.setattr(
        "services.mindbot.mindbot_callback.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    cfg = _sample_cfg()

    from services.mindbot.mindbot_callback import process_dingtalk_callback

    session = AsyncMock()
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header=None,
        sign_header=None,
        body={},
        resolved_config=cfg,
    )
    assert code == 200
    assert hdr.get("X-MindBot-Error-Code") == "MINDBOT_OK"
