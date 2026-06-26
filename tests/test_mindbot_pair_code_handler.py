"""Tests for MindBot pair-code tool handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.auth.dingtalk_bind_constants import PAIR_PURPOSE_UNBIND
from services.mindbot.errors import MindbotErrorCode
from services.mindbot.tools.context import ToolIngressContext
from services.mindbot.tools.handlers.pair_code import PairCodeToolHandler


def _ctx(*, text: str = "123-456", staff: str = "staff42") -> ToolIngressContext:
    return ToolIngressContext(
        cfg=MagicMock(organization_id=5),
        body={"msgtype": "text", "text": {"content": text}},
        inbound_msg_type="text",
        text_in=text,
        sender_staff_id=staff,
        session_webhook_valid="https://example.com/hook",
        session_webhook_pinned_ip="",
        pipeline_ctx="test",
        record_usage=AsyncMock(),
        hdr_for_code=MagicMock(return_value={}),
    )


@pytest.mark.asyncio
async def test_pair_handler_passthrough_on_normal_chat() -> None:
    """Non-code chat is not handled."""
    handler = PairCodeToolHandler()
    assert handler.matches(_ctx(text="hello")) is False
    assert await handler.handle(_ctx(text="hello")) is None


@pytest.mark.asyncio
async def test_pair_handler_unbind_success() -> None:
    """Unbind pair session completes with UNBIND_OK."""
    handler = PairCodeToolHandler()
    ctx = _ctx()

    with (
        patch(
            "services.mindbot.tools.handlers.pair_code.is_bind_code_guess_blocked",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "services.mindbot.tools.handlers.pair_code.resolve_bind_token_for_org_code",
            new_callable=AsyncMock,
            return_value="tok-unbind",
        ),
        patch(
            "services.mindbot.tools.handlers.pair_code.get_bind_token_data",
            new_callable=AsyncMock,
            return_value={"pair_purpose": PAIR_PURPOSE_UNBIND},
        ),
        patch(
            "services.mindbot.tools.handlers.pair_code.claim_dingtalk_unbind_pair",
            new_callable=AsyncMock,
            return_value=(True, ""),
        ),
        patch(
            "services.mindbot.tools.handlers.pair_code.finish_pair_reply",
            new_callable=AsyncMock,
            return_value=(200, {}),
        ) as finish,
    ):
        result = await handler.handle(ctx)

    assert result == (200, {})
    finish.assert_awaited_once()
    assert finish.await_args is not None
    assert finish.await_args.args[7] == MindbotErrorCode.UNBIND_OK
