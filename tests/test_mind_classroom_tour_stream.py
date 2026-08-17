"""Canvas-tour DashScope stream heartbeats."""

from __future__ import annotations

from typing import Any, AsyncIterator
from unittest.mock import patch

import pytest

from services.mind_classroom.canvas_tour_llm import stream_chunk_text, stream_tour_script_text
from services.mind_classroom.progress_log import format_llm_stream_detail, should_log_llm_stream


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
            job_id="job-stream",
            branch=1,
            branch_total=3,
            branch_label="开场",
        )
    assert text == '{"steps": []}'
    assert usage == {"prompt_tokens": 3, "completion_tokens": 5}
