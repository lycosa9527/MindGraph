"""Tests for MindBot blocking Dify helper."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from clients.dify import DifyConversationNotFoundError


@pytest.mark.asyncio
async def test_blocking_retries_after_conversation_not_found() -> None:
    from services.mindbot.core.dify_reply import mindbot_dify_chat_blocking

    dify = AsyncMock()
    dify.chat_blocking = AsyncMock(
        side_effect=[
            DifyConversationNotFoundError("gone"),
            {"answer": "retry-ok", "conversation_id": "new-c"},
        ],
    )
    cleared: list[bool] = []

    async def on_stale() -> None:
        cleared.append(True)

    out = await mindbot_dify_chat_blocking(
        dify,
        text="hi",
        user_id="u1",
        conversation_id="old",
        files=None,
        inputs=None,
        on_stale_conversation=on_stale,
    )
    assert cleared == [True]
    assert out == {"answer": "retry-ok", "conversation_id": "new-c"}
    assert dify.chat_blocking.await_count == 2
    second_kw = dify.chat_blocking.await_args_list[1].kwargs
    assert second_kw.get("conversation_id") is None
