"""MindBot dify_paths: streaming branch with DingTalk AI card (mocked)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from services.mindbot.errors import MindbotErrorCode
from services.mindbot.pipeline.context import DifyReplyContext
from services.mindbot.pipeline.dify_paths import run_streaming_dify_branch


@pytest.mark.asyncio
async def test_streaming_ai_card_create_stream_and_finalize() -> None:
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

    create_mock = AsyncMock(return_value=(True, None, "", "stream"))
    stream_mock = AsyncMock(return_value=(True, None, "", None))
    prefetch_mock = AsyncMock(return_value="token-z")

    async def fake_consume(_dify, **kwargs):
        on_batch = kwargs["on_batch"]
        on_msg_rep = kwargs["on_message_replace"]
        await on_msg_rep()
        await on_batch("a")
        return "a", None, None, None, ""

    with patch(
        "services.mindbot.pipeline.dify_paths.prefetch_ai_card_access_token",
        prefetch_mock,
    ):
        with patch(
            "services.mindbot.pipeline.ai_card_state.prefetch_ai_card_access_token",
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
                        "services.mindbot.pipeline.ai_card_state.streaming_update_ai_card",
                        stream_mock,
                    ):
                        with patch(
                            "services.mindbot.pipeline.dify_paths.mindbot_consume_dify_stream_batched",
                            fake_consume,
                        ):
                            ctx = DifyReplyContext(
                                cfg=cfg,
                                body=body,
                                session_webhook_valid=None,
                                conversation_id_dt="oc-1",
                                conv_key="ck",
                                record_usage=record_usage,
                                hdr=hdr,
                                redis_bind_dify_conversation=redis_bind,
                                pipeline_ctx="test_ctx",
                            )
                            status, _headers = await run_streaming_dify_branch(
                                ctx,
                                dify=SimpleNamespace(),
                                text_in="hi",
                                user_id="u1",
                                dify_conv=None,
                                files=[],
                                dify_inputs=None,
                                stale_cb=None,
                            )
    assert status == 200
    assert usage_codes == [MindbotErrorCode.OK]
    create_mock.assert_awaited_once()
    assert stream_mock.await_count == 2
    fin_call = stream_mock.await_args_list[-1]
    assert fin_call.kwargs["is_finalize"] is True
    assert fin_call.kwargs["markdown_full"] == "a"
