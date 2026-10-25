"""Long SSE handlers must close the database session before the body starts."""

from __future__ import annotations

import inspect
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import StreamingResponse

from models import AIAssistantRequest
from routers.api.mindmate_export_jobs import stream_export_job
from routers.api.sse_streaming import ai_assistant_stream
from routers.features.mind_classroom.routes import stream_classroom_job
from routers.features.showcase.routes_covers import stream_showcase_cover


class _ClosingSession:
    """Async context manager that records when it exits."""

    def __init__(self) -> None:
        self.closed = False

    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *_args: object) -> bool:
        self.closed = True
        return False


def _request() -> AIAssistantRequest:
    return AIAssistantRequest(
        message="hello",
        user_id="mg_user_6146",
        conversation_id="60aa19d4-4fe0-4aa7-98ac-0ad20c68db4a",
        server=None,
        dify_user=None,
        files=None,
        inputs=None,
        auto_generate_name=True,
        workflow_id=None,
        trace_id=None,
    )


def _enter_stream_patches(stack: ExitStack, stream_target: SimpleNamespace) -> None:
    stack.enter_context(patch("routers.api.sse_streaming.assert_student_ai_capability", new_callable=AsyncMock))
    stack.enter_context(patch("routers.api.sse_streaming.track_module_activity", new_callable=AsyncMock))
    stack.enter_context(
        patch(
            "routers.api.sse_streaming.resolve_mindmate_dify_stream_short_lived",
            new_callable=AsyncMock,
            return_value=stream_target,
        )
    )
    stack.enter_context(
        patch(
            "routers.api.sse_streaming.resolve_mindmate_stream_dify_user",
            new_callable=AsyncMock,
            return_value="mg_user_6146",
        )
    )
    stack.enter_context(
        patch(
            "routers.api.sse_streaming.apply_persona_inputs_for_organization_id",
            new_callable=AsyncMock,
        )
    )
    stack.enter_context(patch("routers.api.sse_streaming.register_generation_session", new_callable=AsyncMock))


@pytest.mark.asyncio
async def test_ai_assistant_stream_closes_session_before_sse() -> None:
    """Pre-stream reads finish before the handler returns StreamingResponse."""
    current_user = MagicMock()
    current_user.id = 6146
    current_user.organization_id = 1
    request = MagicMock()
    request.headers = {"Accept-Language": "zh"}
    session = _ClosingSession()
    stream_target = SimpleNamespace(
        client=SimpleNamespace(api_url="http://dify.example"),
        notify_backup=False,
        server=1,
        upstream_conversation_id="60aa19d4-4fe0-4aa7-98ac-0ad20c68db4a",
    )

    with ExitStack() as stack:
        stack.enter_context(patch("routers.api.sse_streaming.request_rls_session", return_value=session))
        _enter_stream_patches(stack, stream_target)
        response = await ai_assistant_stream(_request(), request, "zh", current_user)

    assert isinstance(response, StreamingResponse)
    assert session.closed is True


@pytest.mark.asyncio
async def test_ai_assistant_stream_api_key_opens_no_session() -> None:
    """An API-key call has no user row to read."""
    request = MagicMock()
    request.headers = {"Accept-Language": "zh"}
    stream_target = SimpleNamespace(
        client=SimpleNamespace(api_url="http://dify.example"),
        notify_backup=False,
        server=1,
        upstream_conversation_id=None,
    )
    opener = MagicMock()

    with ExitStack() as stack:
        stack.enter_context(patch("routers.api.sse_streaming.request_rls_session", opener))
        _enter_stream_patches(stack, stream_target)
        response = await ai_assistant_stream(_request(), request, "zh", None)

    assert isinstance(response, StreamingResponse)
    opener.assert_not_called()


def test_long_sse_routes_have_no_request_db_session() -> None:
    """These handlers used to keep Depends(get_async_db) open for the whole body."""
    for handler in (
        ai_assistant_stream,
        stream_classroom_job,
        stream_showcase_cover,
        stream_export_job,
    ):
        assert "db" not in inspect.signature(handler).parameters
