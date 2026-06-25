"""Tests for MindBot DingTalk bind picture ingress."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.mindbot.bind.picture_handler import try_handle_bind_picture
from services.mindbot.errors import MindbotErrorCode


def _cfg() -> MagicMock:
    cfg = MagicMock()
    cfg.organization_id = 5
    cfg.dingtalk_client_id = "ding-client-id"
    cfg.dingtalk_app_secret = "secret"
    cfg.dingtalk_robot_code = "robot-code"
    return cfg


def _picture_body() -> dict[str, object]:
    return {
        "msgtype": "picture",
        "content": {"downloadCode": "dl-code-abc"},
    }


def _record_usage_outcome(record_usage: AsyncMock) -> MindbotErrorCode:
    """Return the MindbotErrorCode passed to the usage recorder mock."""
    assert record_usage.await_args is not None
    outcome = record_usage.await_args.args[0]
    assert isinstance(outcome, MindbotErrorCode)
    return outcome


@pytest.mark.asyncio
async def test_invalid_staff_id_returns_bind_invalid_staff() -> None:
    """Placeholder senderStaffId must not proceed to claim."""
    record_usage = AsyncMock()
    hdr_for_code = MagicMock(return_value={"X-MindBot-Error-Code": "x"})

    with patch(
        "services.mindbot.bind.picture_handler.send_full_reply",
        new_callable=AsyncMock,
        return_value=(True, False),
    ):
        result = await try_handle_bind_picture(
            cfg=_cfg(),
            body=_picture_body(),
            inbound_msg_type="picture",
            sender_staff_id="unknown",
            session_webhook_valid="https://example.com/hook",
            session_webhook_pinned_ip="",
            pipeline_ctx="test",
            record_usage=record_usage,
            hdr_for_code=hdr_for_code,
        )

    assert result is not None
    record_usage.assert_awaited_once()
    assert _record_usage_outcome(record_usage) == MindbotErrorCode.BIND_INVALID_STAFF


@pytest.mark.asyncio
async def test_openapi_disabled_returns_bind_unavailable() -> None:
    """Missing bind infra must not silently fall through to Dify."""
    record_usage = AsyncMock()
    hdr_for_code = MagicMock(return_value={})

    with (
        patch(
            "services.mindbot.bind.picture_handler.env_bool",
            return_value=False,
        ),
        patch(
            "services.mindbot.bind.picture_handler.send_full_reply",
            new_callable=AsyncMock,
            return_value=(True, False),
        ),
    ):
        result = await try_handle_bind_picture(
            cfg=_cfg(),
            body=_picture_body(),
            inbound_msg_type="picture",
            sender_staff_id="staff42",
            session_webhook_valid="https://example.com/hook",
            session_webhook_pinned_ip="",
            pipeline_ctx="test",
            record_usage=record_usage,
            hdr_for_code=hdr_for_code,
        )

    assert result is not None
    assert _record_usage_outcome(record_usage) == MindbotErrorCode.BIND_UNAVAILABLE


@pytest.mark.asyncio
async def test_non_bind_picture_passthrough() -> None:
    """Regular pictures without bind QR continue the MindBot pipeline."""
    with (
        patch(
            "services.mindbot.bind.picture_handler.pyzbar_backend_ready",
            return_value=True,
        ),
        patch(
            "services.mindbot.bind.picture_handler.fetch_message_media_bytes",
            new_callable=AsyncMock,
            return_value=b"\xff\xd8\xff",
        ),
        patch(
            "services.mindbot.bind.picture_handler.decode_bind_token_from_image",
            return_value=(None, None, False),
        ),
    ):
        result = await try_handle_bind_picture(
            cfg=_cfg(),
            body=_picture_body(),
            inbound_msg_type="picture",
            sender_staff_id="staff42",
            session_webhook_valid=None,
            session_webhook_pinned_ip="",
            pipeline_ctx="test",
            record_usage=AsyncMock(),
            hdr_for_code=MagicMock(return_value={}),
        )

    assert result is None


@pytest.mark.asyncio
async def test_org_mismatch_preclaim_without_consume() -> None:
    """Handler can reject wrong-org QR before calling claim."""
    record_usage = AsyncMock()

    with (
        patch(
            "services.mindbot.bind.picture_handler.pyzbar_backend_ready",
            return_value=True,
        ),
        patch(
            "services.mindbot.bind.picture_handler.fetch_message_media_bytes",
            new_callable=AsyncMock,
            return_value=b"img",
        ),
        patch(
            "services.mindbot.bind.picture_handler.decode_bind_token_from_image",
            return_value=("tok123", "123456", True),
        ),
        patch(
            "services.mindbot.bind.picture_handler.get_bind_token_consumed",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.mindbot.bind.picture_handler.get_bind_token_data",
            new_callable=AsyncMock,
            return_value={"user_id": 1, "organization_id": 99},
        ),
        patch(
            "services.mindbot.bind.picture_handler.claim_bind_token_for_staff",
            new_callable=AsyncMock,
        ) as mock_claim,
        patch(
            "services.mindbot.bind.picture_handler.send_full_reply",
            new_callable=AsyncMock,
            return_value=(True, False),
        ),
    ):
        result = await try_handle_bind_picture(
            cfg=_cfg(),
            body=_picture_body(),
            inbound_msg_type="picture",
            sender_staff_id="staff42",
            session_webhook_valid="https://example.com/hook",
            session_webhook_pinned_ip="",
            pipeline_ctx="test",
            record_usage=record_usage,
            hdr_for_code=MagicMock(return_value={}),
        )

    assert result is not None
    mock_claim.assert_not_called()
    assert _record_usage_outcome(record_usage) == MindbotErrorCode.BIND_ORG_MISMATCH
