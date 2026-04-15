"""Tests for MindBot DingTalk callback orchestration (no live HTTP)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from models.domain.mindbot_config import OrganizationMindbotConfig
from services.mindbot.core.dify_user_id import (
    mindbot_conv_gate_scope_id,
    mindbot_dify_conv_redis_suffix,
    mindbot_dify_user_id_for_chat,
)
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.platforms.dingtalk import DingTalkInboundMessage


def test_dify_user_id_always_per_staff() -> None:
    """Dify user is always per staff; group and 1:1 share the same pattern."""
    assert mindbot_dify_user_id_for_chat(1, "staffA") == "mindbot_1_staffA"
    assert mindbot_dify_user_id_for_chat(1, "staffB") == "mindbot_1_staffB"


def test_group_redis_conv_key_includes_staff() -> None:
    """Group chats use one Redis Dify conversation binding per member."""
    body = {"conversationType": "2"}
    g = mindbot_dify_conv_redis_suffix(
        1,
        "cidG",
        "alice",
        body,
        "group",
    )
    h = mindbot_dify_conv_redis_suffix(
        1,
        "cidG",
        "bob",
        body,
        "group",
    )
    assert g == "1:cidG:alice"
    assert h == "1:cidG:bob"
    assert g != h


def test_one_to_one_redis_conv_key_no_staff_segment() -> None:
    """1:1 chats keep a single binding per open conversation."""
    body = {"conversationType": "1"}
    o = mindbot_dify_conv_redis_suffix(
        7,
        "cidO2O",
        "alice",
        body,
        "1:1",
    )
    assert o == "7:cidO2O"


def test_conv_gate_scope_group_includes_staff() -> None:
    """Conv gate id must align with Redis conv_key scope in groups."""
    body = {"conversationType": "2"}
    assert (
        mindbot_conv_gate_scope_id("cidG", "alice", body, "group") == "cidG:alice"
    )


@pytest.mark.asyncio
async def test_feature_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback_validate.config",
        SimpleNamespace(FEATURE_MINDBOT=False),
    )
    from services.mindbot.pipeline.callback import process_dingtalk_callback

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
async def test_shared_callback_requires_path_not_body_robot_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared URL without resolved_config does not route by JSON robotCode."""
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback_validate.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    from services.mindbot.pipeline.callback import process_dingtalk_callback

    session = AsyncMock()
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header="1",
        sign_header="1",
        body={"text": {"content": "hi"}, "robotCode": "normal"},
    )
    assert code == 404
    assert hdr.get("X-MindBot-Error-Code") == "MINDBOT_PATH_CALLBACK_REQUIRED"


def _sample_cfg() -> OrganizationMindbotConfig:
    row = OrganizationMindbotConfig(
        organization_id=1,
        dingtalk_robot_code="robot-1",
        public_callback_token="tok_test_12345678901234567890",
        dingtalk_app_secret="test-secret-for-hmac-signing-32chars!!",
        dingtalk_client_id=None,
        dify_api_base_url="https://example.com/v1",
        dify_api_key="k",
        dify_timeout_seconds=300,
        is_enabled=True,
    )
    row.id = 1
    return row


@pytest.mark.asyncio
async def test_invalid_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback_validate.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback.is_redis_available",
        lambda: False,
    )

    cfg = _sample_cfg()

    from services.mindbot.pipeline.callback import process_dingtalk_callback

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
        resolved_config=cfg,
    )
    assert code == 401
    assert "MINDBOT_INVALID_SIGNATURE" in hdr.get("X-MindBot-Error-Code", "")


@pytest.mark.asyncio
async def test_body_robotcode_placeholder_does_not_block_before_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DingTalk may send robotCode != stored dingtalk_robot_code; path routing wins."""
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback_validate.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback.is_redis_available",
        lambda: False,
    )

    cfg = _sample_cfg()

    from services.mindbot.pipeline.callback import process_dingtalk_callback

    session = AsyncMock()
    body = {
        "robotCode": "normal",
        "msgtype": "text",
        "text": {"content": "hello"},
    }
    code, hdr = await process_dingtalk_callback(
        session,
        timestamp_header="1730000000000",
        sign_header="not-the-real-signature",
        body=body,
        resolved_config=cfg,
    )
    assert code == 401
    assert "MINDBOT_INVALID_SIGNATURE" in hdr.get("X-MindBot-Error-Code", "")
    assert "MINDBOT_ROBOT_CODE_MISMATCH" not in hdr.get("X-MindBot-Error-Code", "")


@pytest.mark.asyncio
async def test_shared_connectivity_probe_empty_body_no_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Shared URL: DingTalk may POST empty body with no robotCode when saving the message URL."""
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback_validate.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    from services.mindbot.pipeline.callback import process_dingtalk_callback

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
        "services.mindbot.pipeline.callback_validate.config",
        SimpleNamespace(FEATURE_MINDBOT=True),
    )
    cfg = _sample_cfg()

    from services.mindbot.pipeline.callback import process_dingtalk_callback

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


def _minimal_inbound_msg() -> DingTalkInboundMessage:
    return DingTalkInboundMessage(
        sender_staff_id="staff",
        sender_nick=None,
        sender_id=None,
        conversation_id="conv",
        conversation_type="1",
        chat_type="1:1",
        msg_id=None,
        session_webhook=None,
        inbound_msg_type="text",
        text_in="hi",
    )


@pytest.mark.asyncio
async def test_run_pipeline_background_records_internal_error_metric(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unhandled exceptions in execute_mindbot_pipeline increment the pipeline error counter."""
    recorded: list[str] = []

    async def _boom(_session: object, _ctx: object) -> tuple[int, dict[str, str]]:
        raise RuntimeError("simulated pipeline failure")

    def _capture_error_code(code: str) -> None:
        recorded.append(code)

    monkeypatch.setattr(
        "services.mindbot.pipeline.callback.execute_mindbot_pipeline",
        _boom,
    )
    monkeypatch.setattr(
        "services.mindbot.pipeline.callback.mindbot_metrics.record_error_code",
        _capture_error_code,
    )
    from services.mindbot.pipeline.callback import (
        MindbotPipelineContext,
        run_pipeline_background,
    )

    cfg = _sample_cfg()
    ctx = MindbotPipelineContext(
        cfg=cfg,
        body={},
        timestamp_header=None,
        sign_header=None,
        debug_route_label=None,
        debug_raw_body=None,
        debug_request_headers=None,
        msg=_minimal_inbound_msg(),
        dify_user_id="u1",
        conv_key="ck",
        conv_gate_scope="conv",
    )
    await run_pipeline_background(ctx)
    assert recorded == [MindbotErrorCode.PIPELINE_INTERNAL_ERROR.value]
