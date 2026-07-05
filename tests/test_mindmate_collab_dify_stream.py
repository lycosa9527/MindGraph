"""MindMate collab Dify stream broadcast tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.features.mindmate_collab.dify_stream import stream_assistant_reply


@pytest.mark.asyncio
async def test_ai_message_end_omits_conversation_id() -> None:
    """Client-facing end frames do not expose internal Dify conversation ids."""
    broadcasts: list[dict] = []

    async def _capture(_code: str, message: dict) -> None:
        broadcasts.append(message)

    mock_client = MagicMock()

    with (
        patch(
            "services.features.mindmate_collab.dify_stream.resolve_mindmate_dify_client_short_lived",
            AsyncMock(return_value=mock_client),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.is_dify_stream_aborted",
            AsyncMock(return_value=False),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.broadcast_to_all",
            side_effect=_capture,
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.release_dify_stream_lock",
            AsyncMock(),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.clear_dify_stream_abort",
            AsyncMock(),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.clear_dify_stream_task",
            MagicMock(),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.get_mindmate_collab_manager",
        ) as mgr_factory,
    ):
        mgr = MagicMock()
        saved = MagicMock()
        saved.id = 99
        mgr.persist_message = AsyncMock(return_value=saved)
        mgr.set_dify_conversation_id = AsyncMock()
        mgr_factory.return_value = mgr

        async def _one_chunk_stream(*_args, **_kwargs):
            yield {"answer": "Hi", "conversation_id": "secret-conv-id"}

        mock_client.stream_chat.return_value = _one_chunk_stream()

        await stream_assistant_reply(
            code="ABC-DEF",
            session_id="sess-1",
            org_id=1,
            user_message="Hello",
            sender_user_id=7,
            conversation_id=None,
        )

    end_frames = [msg for msg in broadcasts if msg.get("type") == "ai_message_end"]
    assert len(end_frames) == 1
    assert "conversation_id" not in end_frames[0]
