"""Canvas-tour DashScope stream heartbeats."""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, AsyncIterator, Iterator
from unittest.mock import AsyncMock, patch

import pytest

from services.mind_classroom.canvas_tour_llm import stream_chunk_text, stream_tour_script_text
from services.mind_classroom.progress_log import format_llm_stream_detail, should_log_llm_stream

_LLM_CALL: ContextVar[str | None] = ContextVar("llm_call", default=None)


@contextmanager
def _bind_llm_call() -> Iterator[None]:
    """Same token reset ``bind_llm_call`` uses around ``chat_stream`` yields."""
    token = _LLM_CALL.set("mind_classroom_canvas_tour")
    try:
        yield
    finally:
        _LLM_CALL.reset(token)


def test_stream_chunk_text_splits_token_and_usage() -> None:
    """Structured stream items become text or usage, never thinking."""
    assert stream_chunk_text({"type": "token", "content": "你好"}) == ("你好", None)
    assert stream_chunk_text("plain") == ("plain", None)
    assert stream_chunk_text({"type": "thinking", "content": "..."}) == ("", None)
    usage = {"prompt_tokens": 2, "completion_tokens": 4}
    assert stream_chunk_text({"type": "usage", "usage": usage}) == ("", usage)


def test_format_llm_stream_names_the_branch() -> None:
    """Worker lines say which branch is streaming."""
    line = format_llm_stream_detail(
        branch=2,
        branch_total=6,
        branch_label="呼吸作用",
        chars=240,
        elapsed_s=3.2,
        first_token=True,
    )
    assert line.startswith("LLM result streaming for branch 2/6")
    assert "label=呼吸作用" in line
    assert "first_token" in line
    assert "chars=240" in line


def test_should_log_llm_stream_on_first_and_char_step() -> None:
    """First token always logs; later logs after 800 chars or 15s."""
    assert should_log_llm_stream(
        chars=12,
        last_chars=0,
        last_at=0.0,
        now=0.1,
        first_token=True,
    )
    assert not should_log_llm_stream(
        chars=100,
        last_chars=12,
        last_at=1.0,
        now=2.0,
        first_token=False,
    )
    assert should_log_llm_stream(
        chars=900,
        last_chars=12,
        last_at=1.0,
        now=2.0,
        first_token=False,
    )
    assert should_log_llm_stream(
        chars=20,
        last_chars=12,
        last_at=1.0,
        now=16.1,
        first_token=False,
    )


@pytest.mark.asyncio
async def test_stream_tour_script_text_joins_tokens() -> None:
    """chat_stream tokens concatenate; usage comes from the final chunk."""

    async def _fake_stream(**_kwargs: Any) -> AsyncIterator[Any]:
        yield {"type": "token", "content": '{"steps":'}
        yield {"type": "token", "content": " []}"}
        yield {"type": "usage", "usage": {"prompt_tokens": 3, "completion_tokens": 5}}

    with patch("services.mind_classroom.canvas_tour_llm.llm_service") as llm:
        llm.chat_stream = _fake_stream
        text, usage = await stream_tour_script_text(
            prompt="p",
            model="qwen",
            system_message="s",
            max_tokens=100,
            temperature=0.4,
            user_id=3,
            organization_id=1,
        )
    assert text == '{"steps": []}'
    assert usage == {"prompt_tokens": 3, "completion_tokens": 5}


class _SlowStream:
    """Yields one token after the heartbeat window, and records close."""

    def __init__(self) -> None:
        self.sent = False
        self.closed = 0

    def __aiter__(self) -> "_SlowStream":
        return self

    async def __anext__(self) -> dict[str, str]:
        if self.sent:
            raise StopAsyncIteration
        await asyncio.sleep(0.12)
        if self.closed:
            raise RuntimeError("generator closed during heartbeat")
        self.sent = True
        return {"type": "token", "content": "late"}

    async def aclose(self) -> None:
        """Count closes. A heartbeat must not close the live generator."""
        self.closed += 1


@pytest.mark.asyncio
async def test_stream_heartbeat_does_not_cancel_the_generator() -> None:
    """A quiet model keeps the stream open and still delivers the next token."""
    slow = _SlowStream()

    def _chat(**_kwargs: Any) -> _SlowStream:
        return slow

    with (
        patch("services.mind_classroom.canvas_tour_llm.llm_service") as llm,
        patch("services.mind_classroom.canvas_tour_llm.STREAM_HEARTBEAT_SEC", 0.05),
    ):
        llm.chat_stream = _chat
        text, usage = await stream_tour_script_text(
            prompt="p",
            model="qwen",
            system_message="s",
            max_tokens=100,
            temperature=0.4,
            user_id=None,
            organization_id=None,
        )
    assert text == "late"
    assert usage is None
    assert slow.closed == 1


@pytest.mark.asyncio
async def test_stream_heartbeat_logs_while_the_model_is_quiet(caplog: pytest.LogCaptureFixture) -> None:
    """A quiet model logs waiting and still returns the late token."""
    slow = _SlowStream()

    def _chat(**_kwargs: Any) -> _SlowStream:
        return slow

    with (
        patch("services.mind_classroom.canvas_tour_llm.llm_service") as llm,
        patch("services.mind_classroom.canvas_tour_llm.STREAM_HEARTBEAT_SEC", 0.05),
        patch("services.mind_classroom.canvas_tour_llm.patch_tour_progress", new_callable=AsyncMock),
        caplog.at_level(logging.INFO, logger="services.mind_classroom"),
    ):
        llm.chat_stream = _chat
        text, usage = await stream_tour_script_text(
            prompt="p",
            model="qwen",
            system_message="s",
            max_tokens=100,
            temperature=0.4,
            user_id=None,
            organization_id=None,
            job_id="job-heartbeat",
            branch=2,
            branch_total=3,
            branch_label="两栖类",
        )
    assert text == "late"
    assert usage is None
    waiting = [record.message for record in caplog.records if "waiting" in record.message]
    assert waiting
    assert "branch 2/3" in waiting[0]
    assert "label=两栖类" in waiting[0]
    assert "chars=0" in waiting[0]


@pytest.mark.asyncio
async def test_stream_provider_error_reaches_the_caller() -> None:
    """A provider failure is not swallowed when the generator is closed."""

    async def _fake_stream(**_kwargs: Any) -> AsyncIterator[Any]:
        with _bind_llm_call():
            yield {"type": "token", "content": "部分"}
            raise RuntimeError("provider down")

    with patch("services.mind_classroom.canvas_tour_llm.llm_service") as llm:
        llm.chat_stream = _fake_stream
        with pytest.raises(RuntimeError, match="provider down"):
            await stream_tour_script_text(
                prompt="p",
                model="qwen",
                system_message="s",
                max_tokens=100,
                temperature=0.4,
                user_id=3,
                organization_id=1,
            )


@pytest.mark.asyncio
async def test_stream_keeps_llm_call_token_in_one_context() -> None:
    """Several chunks must not reset llm_call from another task."""

    async def _fake_stream(**_kwargs: Any) -> AsyncIterator[Any]:
        with _bind_llm_call():
            yield {"type": "token", "content": "两栖"}
            await asyncio.sleep(0)
            yield {"type": "token", "content": "类"}
            yield {"type": "usage", "usage": {"prompt_tokens": 1, "completion_tokens": 2}}

    with patch("services.mind_classroom.canvas_tour_llm.llm_service") as llm:
        llm.chat_stream = _fake_stream
        text, usage = await stream_tour_script_text(
            prompt="p",
            model="qwen",
            system_message="s",
            max_tokens=100,
            temperature=0.4,
            user_id=3,
            organization_id=1,
            branch=2,
            branch_total=3,
            branch_label="两栖类",
        )
    assert text == "两栖类"
    assert usage == {"prompt_tokens": 1, "completion_tokens": 2}
