"""MindMate SSE must not keep a request transaction open across the Dify stream."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.responses import StreamingResponse

from models import AIAssistantRequest
from routers.api.sse_streaming import ai_assistant_stream


@pytest.mark.asyncio
async def test_ai_assistant_stream_commits_request_session_before_sse() -> None:
    """Pre-stream reads are committed before the handler returns StreamingResponse."""
    db = MagicMock()
    db.in_transaction.return_value = True
    db.commit = AsyncMock()

    current_user = MagicMock()
    current_user.id = 6146
    current_user.organization_id = 1

    request = MagicMock()
    request.headers = {"Accept-Language": "zh"}

    req = AIAssistantRequest(
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
    stream_target = SimpleNamespace(
        client=SimpleNamespace(api_url="http://dify.example"),
        notify_backup=False,
        server=1,
    )

    with (
        patch("routers.api.sse_streaming.assert_student_ai_capability", new_callable=AsyncMock),
        patch("routers.api.sse_streaming.track_module_activity", new_callable=AsyncMock),
        patch(
            "routers.api.sse_streaming.resolve_mindmate_dify_stream_short_lived",
            new_callable=AsyncMock,
            return_value=stream_target,
        ),
        patch(
            "routers.api.sse_streaming.resolve_mindmate_stream_dify_user",
            new_callable=AsyncMock,
            return_value="mg_user_6146",
        ),
        patch(
            "routers.api.sse_streaming.apply_persona_inputs_for_organization_id",
            new_callable=AsyncMock,
        ),
        patch("routers.api.sse_streaming.register_generation_session", new_callable=AsyncMock),
    ):
        response = await ai_assistant_stream(req, request, "zh", current_user, db)

    assert isinstance(response, StreamingResponse)
    db.commit.assert_awaited_once()
