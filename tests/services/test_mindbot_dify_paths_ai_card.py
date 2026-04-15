"""MindBot dify_paths: DingTalk AI card blocking path (mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.mindbot.errors import MindbotErrorCode
from services.mindbot.pipeline.dify_paths import run_blocking_send_branch


@pytest.mark.asyncio
async def test_blocking_send_uses_ai_card_when_configured() -> None:
    usage_codes: list[object] = []

    async def record_usage(code: MindbotErrorCode, **_kwargs) -> None:
        usage_codes.append(code)

    def hdr(code: MindbotErrorCode) -> dict[str, str]:
        return {"X-MindBot-Error-Code": code.value}

    async def redis_bind(_a: str, _b: str, _c: int) -> None:
        return None

    cfg = SimpleNamespace(
        organization_id=1,
        show_chain_of_thought_oto=False,
        show_chain_of_thought_internal_group=False,
        show_chain_of_thought_cross_org_group=False,
        chain_of_thought_max_chars=4000,
        dingtalk_ai_card_template_id="tpl-x",
        dingtalk_ai_card_param_key=None,
        dingtalk_client_id="app-key",
        dingtalk_robot_code="robot-z",
        dingtalk_app_secret="secret",
    )
    body: dict = {
        "senderStaffId": "staff-1",
        "conversationId": "oc-1",
        "conversationType": "2",
    }
    resp = {"answer": "hello card", "conversation_id": "dify-c1"}
    create_mock = AsyncMock(return_value=(True, None, "", "stream"))
    stream_mock = AsyncMock(return_value=(True, None, "", None))
    prefetch_mock = AsyncMock(return_value="token-z")
    attach_mock = AsyncMock(return_value=None)
    with patch(
        "services.mindbot.pipeline.dify_paths.prefetch_ai_card_access_token",
        prefetch_mock,
    ):
        with patch(
            "services.mindbot.pipeline.dify_paths.create_and_deliver_ai_card",
            create_mock,
        ):
            with patch(
                "services.mindbot.pipeline.dify_paths.streaming_update_ai_card",
                stream_mock,
            ):
                with patch(
                    "services.mindbot.pipeline.dify_paths.send_blocking_response_attachments",
                    attach_mock,
                ):
                    status, _headers = await run_blocking_send_branch(
                        cfg=cfg,
                        body=body,
                        resp=resp,
                        usage_block=None,
                        raw_sw=None,
                        session_webhook_valid=None,
                        conversation_id_dt="oc-1",
                        conv_key="ck",
                        record_usage=record_usage,
                        hdr=hdr,
                        redis_bind_dify_conversation=redis_bind,
                        pipeline_ctx="test_ctx",
                    )
    assert status == 200
    assert usage_codes == [MindbotErrorCode.OK]
    create_mock.assert_awaited_once()
    stream_mock.assert_awaited_once()
    assert stream_mock.await_args is not None
    assert stream_mock.await_args.kwargs["is_finalize"] is True
    attach_mock.assert_awaited()


@pytest.mark.asyncio
async def test_blocking_ai_card_mark_error_uses_token_from_failed_stream() -> None:
    """After finalize PUT fails, mark_error must use refreshed token if stream returned one."""
    usage_codes: list[object] = []

    async def record_usage(code: MindbotErrorCode, **_kwargs) -> None:
        usage_codes.append(code)

    def hdr(code: MindbotErrorCode) -> dict[str, str]:
        return {"X-MindBot-Error-Code": code.value}

    async def redis_bind(_a: str, _b: str, _c: int) -> None:
        return None

    cfg = SimpleNamespace(
        organization_id=1,
        show_chain_of_thought_oto=False,
        show_chain_of_thought_internal_group=False,
        show_chain_of_thought_cross_org_group=False,
        chain_of_thought_max_chars=4000,
        dingtalk_ai_card_template_id="tpl-x",
        dingtalk_ai_card_param_key=None,
        dingtalk_client_id="app-key",
        dingtalk_robot_code="robot-z",
        dingtalk_app_secret="secret",
    )
    body: dict = {
        "senderStaffId": "staff-1",
        "conversationId": "oc-1",
        "conversationType": "2",
    }
    resp = {"answer": "hello", "conversation_id": "dify-c1"}
    create_mock = AsyncMock(return_value=(True, None, "", "stream"))
    stream_mock = AsyncMock(
        return_value=(False, "e1", "detail", "refreshed-tok"),
    )
    mark_mock = AsyncMock(return_value=(True, None, "", None))
    prefetch_mock = AsyncMock(return_value="token-old")
    with patch(
        "services.mindbot.pipeline.dify_paths.prefetch_ai_card_access_token",
        prefetch_mock,
    ):
        with patch(
            "services.mindbot.pipeline.dify_paths.create_and_deliver_ai_card",
            create_mock,
        ):
            with patch(
                "services.mindbot.pipeline.dify_paths.streaming_update_ai_card",
                stream_mock,
            ):
                with patch(
                    "services.mindbot.pipeline.dify_paths.mark_ai_card_stream_error",
                    mark_mock,
                ):
                    with patch(
                        "services.mindbot.pipeline.dify_paths.reply_via_openapi",
                        new=AsyncMock(return_value=(True, False)),
                    ):
                        status, _ = await run_blocking_send_branch(
                            cfg=cfg,
                            body=body,
                            resp=resp,
                            usage_block=None,
                            raw_sw=None,
                            session_webhook_valid=None,
                            conversation_id_dt="oc-1",
                            conv_key="ck",
                            record_usage=record_usage,
                            hdr=hdr,
                            redis_bind_dify_conversation=redis_bind,
                            pipeline_ctx="test_ctx",
                        )
    assert status == 200
    mark_mock.assert_awaited_once()
    assert mark_mock.await_args is not None
    assert mark_mock.await_args.kwargs["access_token"] == "refreshed-tok"
    assert MindbotErrorCode.OK in usage_codes
