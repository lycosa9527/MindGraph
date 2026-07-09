"""Tests for text-only one-sentence conversational replies."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.one_sentence_text_reply import reply_text_only_conversational


@pytest.mark.asyncio
async def test_reply_text_only_skips_non_text_mode() -> None:
    """Handler does not run when client_mode is not text."""
    with patch(
        "services.kitty.session.one_sentence_text_reply.voice_sessions",
        {"vs1": {"_kitty_client_mode": "voice", "active_panel": "one_sentence"}},
    ):
        handled = await reply_text_only_conversational(
            MagicMock(),
            "vs1",
            "hello",
            {},
        )
    assert handled is False


@pytest.mark.asyncio
async def test_reply_text_only_emits_llm_reply() -> None:
    """Text-only one_sentence panel gets a Qwen text reply."""
    websocket = MagicMock()
    session_state = {
        "_kitty_client_mode": "text",
        "active_panel": "one_sentence",
        "diagram_type": "mindmap",
        "user_id": 7,
    }
    with patch(
        "services.kitty.session.one_sentence_text_reply.voice_sessions",
        {"vs1": session_state},
    ):
        with patch(
            "services.kitty.session.one_sentence_text_reply.llm_service.chat",
            new_callable=AsyncMock,
            return_value={"content": "可以添加一个历史分支。"},
        ):
            with patch(
                "services.kitty.session.one_sentence_text_reply.emit_user_ack",
                new_callable=AsyncMock,
            ) as ack_mock:
                with patch(
                    "services.kitty.session.one_sentence_text_reply.safe_websocket_send",
                    new_callable=AsyncMock,
                ):
                    with patch("services.kitty.session.one_sentence_text_reply.get_session_memory") as memory_mock:
                        memory = MagicMock()
                        memory.summarize_for_parser.return_value = ""
                        memory_mock.return_value = memory
                        handled = await reply_text_only_conversational(
                            websocket,
                            "vs1",
                            "怎么改？",
                            {"diagram_type": "mindmap"},
                        )

    assert handled is True
    ack_mock.assert_awaited_once()
    await_args = ack_mock.await_args
    assert await_args is not None
    assert "历史分支" in await_args.args[2]
