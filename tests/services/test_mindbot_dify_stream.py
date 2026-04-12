"""Tests for batched Dify SSE consumption (no live HTTP)."""

from __future__ import annotations

import pytest

from services.mindbot.core.dify_stream import mindbot_consume_dify_stream_batched


class _FakeDifyOk:
    async def stream_chat(self, **_kwargs):
        yield {"event": "message", "answer": "x" * 70}
        yield {"event": "message", "answer": "y"}
        yield {"event": "message_end", "conversation_id": "conv-1"}


class _FakeDifyWithUsage:
    async def stream_chat(self, **_kwargs):
        yield {"event": "message", "answer": "hi"}
        yield {
            "event": "message_end",
            "conversation_id": "c-u",
            "metadata": {
                "usage": {
                    "prompt_tokens": 1,
                    "completion_tokens": 2,
                    "total_tokens": 3,
                },
            },
        }


class _FakeDifyErr:
    async def stream_chat(self, **_kwargs):
        yield {"event": "error", "message": "bad", "code": "x"}


class _FakeDifyChatflowPrelude:
    async def stream_chat(self, **_kwargs):
        yield {"event": "workflow_started", "task_id": "t1", "workflow_run_id": "w1"}
        yield {"event": "node_finished", "task_id": "t1", "data": {"node_type": "answer"}}
        yield {"event": "message", "answer": "hello", "conversation_id": "c1"}
        yield {"event": "message_end", "conversation_id": "c1"}


class _FakeDifyMessageReplace:
    async def stream_chat(self, **_kwargs):
        yield {"event": "message", "answer": "bad"}
        yield {"event": "message_replace", "answer": "safe reply"}
        yield {"event": "message_end", "conversation_id": "c1"}


class _FakeDifyWorkflowOutputsOnly:
    async def stream_chat(self, **_kwargs):
        yield {
            "event": "workflow_finished",
            "data": {"outputs": {"text": "from workflow"}},
        }
        yield {"event": "message_end", "conversation_id": "c-wf"}


class _FakeDifyWorkflowCustomKey:
    async def stream_chat(self, **_kwargs):
        yield {
            "event": "workflow_finished",
            "data": {"outputs": {"custom_out": "custom text"}},
        }
        yield {"event": "message_end", "conversation_id": "c2"}


@pytest.mark.asyncio
async def test_batches_on_min_chars_and_message_end() -> None:
    sent: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    full, conv, err, usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyOk(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=64,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert usage is None
    assert conv == "conv-1"
    assert "x" * 70 in full
    assert "y" in full
    assert len(sent) >= 1
    assert "".join(sent) == full


@pytest.mark.asyncio
async def test_message_end_metadata_usage() -> None:
    async def on_batch(_chunk: str) -> tuple[bool, bool]:
        return True, False

    _full, conv, err, usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyWithUsage(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=1,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert conv == "c-u"
    assert usage == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
    }


@pytest.mark.asyncio
async def test_dify_error_stops() -> None:
    async def on_batch(_chunk: str) -> tuple[bool, bool]:
        return True, False

    _full, _conv, err, _usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyErr(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=10,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err == "dify_error"


@pytest.mark.asyncio
async def test_chatflow_workflow_prelude_then_message() -> None:
    sent: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    full, conv, err, _usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyChatflowPrelude(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=1,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert conv == "c1"
    assert full == "hello"
    assert sent == ["hello"]


@pytest.mark.asyncio
async def test_message_replace_resets_full_text() -> None:
    sent: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    full, conv, err, _usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyMessageReplace(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=1,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert conv == "c1"
    assert full == "safe reply"
    assert "bad" not in full
    assert sent


@pytest.mark.asyncio
async def test_workflow_finished_outputs_when_no_message_deltas() -> None:
    sent: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    full, conv, err, _usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyWorkflowOutputsOnly(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=1,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert conv == "c-wf"
    assert full == "from workflow"
    assert sent == ["from workflow"]


@pytest.mark.asyncio
async def test_workflow_output_key_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MINDBOT_DIFY_WORKFLOW_OUTPUT_KEY", "custom_out")
    sent: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    full, conv, err, _usage = await mindbot_consume_dify_stream_batched(
        _FakeDifyWorkflowCustomKey(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=1,
        flush_interval_s=60.0,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert conv == "c2"
    assert full == "custom text"
    assert sent == ["custom text"]


@pytest.mark.asyncio
async def test_defer_to_end_sends_once_at_message_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MINDBOT_STREAM_DEFER_TO_END", "true")
    sent: list[str] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    class _FakeMultiDelta:
        async def stream_chat(self, **_kwargs):
            yield {"event": "message", "answer": "ab"}
            yield {"event": "message", "answer": "cd"}
            yield {"event": "message_end", "conversation_id": "c-defer"}

    full, conv, err, _usage = await mindbot_consume_dify_stream_batched(
        _FakeMultiDelta(),
        text="hi",
        user_id="u1",
        conversation_id=None,
        files=None,
        min_chars=1,
        flush_interval_s=0.05,
        max_parts=10,
        on_batch=on_batch,
    )
    assert err is None
    assert conv == "c-defer"
    assert full == "abcd"
    assert sent == ["abcd"]


class _FakeDifyStaleConversation:
    """First stream: conversation missing; second stream (retry): success."""

    def __init__(self) -> None:
        self.stream_calls = 0

    async def stream_chat(self, **_kwargs):
        self.stream_calls += 1
        if self.stream_calls == 1:
            yield {
                "event": "error",
                "code": "conversation_not_exists",
                "message": "Conversation does not exist",
            }
            return
        yield {"event": "message", "answer": "recovered"}
        yield {"event": "message_end", "conversation_id": "new-conv"}


@pytest.mark.asyncio
async def test_stale_conversation_retries_without_conv_id() -> None:
    sent: list[str] = []
    cleared: list[bool] = []

    async def on_batch(chunk: str) -> tuple[bool, bool]:
        sent.append(chunk)
        return True, False

    async def on_stale() -> None:
        cleared.append(True)

    fake = _FakeDifyStaleConversation()
    full, conv, err, _usage = await mindbot_consume_dify_stream_batched(
        fake,
        text="hi",
        user_id="u1",
        conversation_id="stale-id",
        files=None,
        min_chars=1,
        flush_interval_s=0.05,
        max_parts=10,
        on_batch=on_batch,
        on_stale_conversation=on_stale,
    )
    assert cleared == [True]
    assert fake.stream_calls == 2
    assert err is None
    assert conv == "new-conv"
    assert full == "recovered"
    assert sent == ["recovered"]
