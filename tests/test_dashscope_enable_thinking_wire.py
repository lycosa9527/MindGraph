"""DashScope chat completions must send enable_thinking as a top-level field."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from services.llm import llm_service
from clients.llm.dashscope import DeepSeekClient
from clients.llm.openai_extra_body import hoist_openai_extra_body


def test_hoist_moves_enable_thinking_to_the_top_level() -> None:
    """Nested extra_body keys become ordinary JSON fields."""
    payload: dict[str, Any] = {
        "model": "deepseek-v4.1-flash",
        "extra_body": {"enable_thinking": False, "top_k": 20},
    }
    hoist_openai_extra_body(payload)
    assert payload["enable_thinking"] is False
    assert payload["top_k"] == 20
    assert "extra_body" not in payload


class _DoneStream:
    """SSE stream that ends immediately and records the posted JSON."""

    status_code = 200

    def __init__(self, captured: dict[str, Any], body: dict[str, Any]) -> None:
        captured["json"] = body

    async def __aenter__(self) -> "_DoneStream":
        """Enter the stream context."""
        return self

    async def __aexit__(self, *_args: object) -> None:
        """Leave the stream context."""
        return None

    async def aiter_lines(self) -> AsyncIterator[str]:
        """Yield the SSE terminator and stop."""
        yield "data: [DONE]"


class _CaptureClient:
    """httpx stand-in that keeps the JSON body."""

    def __init__(self, captured: dict[str, Any]) -> None:
        self._captured = captured

    def stream(self, *_args: object, **kwargs: object) -> _DoneStream:
        """Record the JSON body of the streaming POST."""
        body = kwargs["json"]
        assert isinstance(body, dict)
        return _DoneStream(self._captured, body)


class _CaptureManager:
    """Returns the capturing client."""

    def __init__(self, captured: dict[str, Any]) -> None:
        self._captured = captured

    async def get_client(self, *_args: object) -> _CaptureClient:
        """Return the client that captures the request body."""
        return _CaptureClient(self._captured)


@pytest.mark.asyncio
async def test_express_stream_disables_thinking_on_the_wire(monkeypatch: pytest.MonkeyPatch) -> None:
    """Express palette calls must not leave thinking on via a nested extra_body."""
    assert hasattr(llm_service, "chat_stream")
    captured: dict[str, Any] = {}

    def _manager() -> _CaptureManager:
        return _CaptureManager(captured)

    monkeypatch.setattr("clients.llm.dashscope.get_httpx_manager", _manager)
    client = DeepSeekClient(model_id="express")
    messages = [{"role": "user", "content": "充电宝"}]
    async for _chunk in client.async_stream_chat_completion(
        messages,
        max_tokens=500,
        enable_thinking=False,
    ):
        continue
    body = captured["json"]
    assert isinstance(body, dict)
    assert body["model"] == "deepseek-v4.1-flash"
    assert body["enable_thinking"] is False
    assert body["max_tokens"] == 500
    assert "extra_body" not in body
