"""MindBot Dify stream recovery for hung bound conversations (idle sock_read)."""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional
from unittest.mock import AsyncMock

import pytest

from services.mindbot.core.dify_stream import (
    _stream_error_is_hung_bound_conversation,
    _stream_error_is_idle_read_timeout,
    mindbot_consume_dify_stream_batched,
)


def test_idle_read_timeout_matches_aiohttp_sock_read_message() -> None:
    """aiohttp sock_read idle timeout string is recognized."""
    assert _stream_error_is_idle_read_timeout(
        {"event": "error", "error": "Timeout on reading data from socket"},
    )
    assert _stream_error_is_idle_read_timeout(
        {"event": "error", "message": "Timeout on reading data from socket"},
    )
    assert not _stream_error_is_idle_read_timeout(
        {"event": "error", "error": "connection reset by peer"},
    )


def test_hung_bound_conversation_requires_zero_assistant_content() -> None:
    """Partial streams must not clear Redis / retry on idle timeout."""
    timeout_ev = {"event": "error", "error": "Timeout on reading data from socket"}
    assert _stream_error_is_hung_bound_conversation(
        timeout_ev,
        saw_answer=False,
        full_text="",
        media_sent=0,
    )
    assert not _stream_error_is_hung_bound_conversation(
        timeout_ev,
        saw_answer=True,
        full_text="",
        media_sent=0,
    )
    assert not _stream_error_is_hung_bound_conversation(
        timeout_ev,
        saw_answer=False,
        full_text="partial",
        media_sent=0,
    )
    assert not _stream_error_is_hung_bound_conversation(
        timeout_ev,
        saw_answer=False,
        full_text="",
        media_sent=1,
    )


class _FakeDify:
    """Minimal AsyncDifyClient stand-in with scripted SSE sequences."""

    def __init__(self, sequences: list[list[dict[str, Any]]]) -> None:
        self._sequences = list(sequences)
        self.calls: list[Optional[str]] = []

    async def stream_chat(
        self,
        message: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        files: Optional[list[Any]] = None,
        auto_generate_name: bool = False,
        inputs: Optional[dict[str, Any]] = None,
        **_kwargs: Any,
    ) -> AsyncIterator[dict[str, Any]]:
        """Yield the next scripted SSE sequence and record conversation_id."""
        del message, user_id, files, auto_generate_name, inputs
        self.calls.append(conversation_id)
        events = self._sequences.pop(0) if self._sequences else []
        for ev in events:
            yield ev


async def _consume(
    dify: Any,
    *,
    conversation_id: Optional[str],
    on_stale_conversation: Any,
    on_batch: Any,
) -> tuple[str, Optional[str], Optional[str], Optional[dict[str, int]], str]:
    """Call the stream consumer with shared test defaults."""
    return await mindbot_consume_dify_stream_batched(
        dify,
        text="你好",
        user_id="mindbot_5_staff",
        conversation_id=conversation_id,
        files=None,
        min_chars=1,
        flush_interval_s=0.05,
        max_parts=10,
        on_batch=on_batch,
        on_stale_conversation=on_stale_conversation,
        pipeline_ctx="test",
    )


@pytest.mark.asyncio
async def test_hung_idle_timeout_clears_binding_and_retries_without_conv() -> None:
    """Zero-output sock_read timeout with a bound id clears Redis and retries once."""
    dify = _FakeDify(
        [
            [{"event": "error", "error": "Timeout on reading data from socket"}],
            [
                {"event": "message", "answer": "hello", "conversation_id": "new-conv"},
                {"event": "message_end", "conversation_id": "new-conv"},
            ],
        ],
    )
    stale_cb = AsyncMock()
    batches: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        batches.append(chunk)
        return True, False

    full, conv_id, err, _usage, _reasoning = await _consume(
        dify,
        conversation_id="stuck-conv",
        on_stale_conversation=stale_cb,
        on_batch=on_batch,
    )

    stale_cb.assert_awaited_once()
    assert dify.calls == ["stuck-conv", None]
    assert err is None
    assert full == "hello"
    assert conv_id == "new-conv"
    assert batches == ["hello"]


@pytest.mark.asyncio
async def test_idle_timeout_with_partial_answer_does_not_retry() -> None:
    """Mid-stream idle timeout keeps the bound conversation (no clear/retry)."""
    dify = _FakeDify(
        [
            [
                {"event": "message", "answer": "hi", "conversation_id": "alive-conv"},
                {"event": "error", "error": "Timeout on reading data from socket"},
            ],
        ],
    )
    stale_cb = AsyncMock()

    async def on_batch(_chunk: str) -> tuple[bool, bool]:
        return True, False

    full, conv_id, err, _usage, _reasoning = await _consume(
        dify,
        conversation_id="alive-conv",
        on_stale_conversation=stale_cb,
        on_batch=on_batch,
    )

    stale_cb.assert_not_awaited()
    assert dify.calls == ["alive-conv"]
    assert err == "dify_error"
    assert full == "hi"
    assert conv_id == "alive-conv"


@pytest.mark.asyncio
async def test_conversation_not_exists_still_retries_without_conv() -> None:
    """Existing stale-id recovery path remains unchanged."""
    dify = _FakeDify(
        [
            [
                {
                    "event": "error",
                    "code": "conversation_not_exists",
                    "message": "Conversation Not Exists.",
                },
            ],
            [
                {"event": "message", "answer": "ok", "conversation_id": "fresh"},
                {"event": "message_end", "conversation_id": "fresh"},
            ],
        ],
    )
    stale_cb = AsyncMock()

    async def on_batch(_chunk: str) -> tuple[bool, bool]:
        return True, False

    full, conv_id, err, _usage, _reasoning = await _consume(
        dify,
        conversation_id="missing-conv",
        on_stale_conversation=stale_cb,
        on_batch=on_batch,
    )

    stale_cb.assert_awaited_once()
    assert dify.calls == ["missing-conv", None]
    assert err is None
    assert full == "ok"
    assert conv_id == "fresh"


@pytest.mark.asyncio
async def test_idle_timeout_without_bound_conv_does_not_retry() -> None:
    """Cold-start idle timeout has nothing to clear; fail once."""
    dify = _FakeDify(
        [
            [{"event": "error", "error": "Timeout on reading data from socket"}],
        ],
    )
    stale_cb = AsyncMock()

    async def on_batch(_chunk: str) -> tuple[bool, bool]:
        return True, False

    full, _conv_id, err, _usage, _reasoning = await _consume(
        dify,
        conversation_id=None,
        on_stale_conversation=stale_cb,
        on_batch=on_batch,
    )

    stale_cb.assert_not_awaited()
    assert dify.calls == [None]
    assert err == "dify_error"
    assert full == ""
