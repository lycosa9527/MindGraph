"""MindMate collab Dify stream broadcast tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.dify.org_mindmate_client import MindmateDifyStream
from services.features.mindmate_collab.dify_stream import stream_assistant_reply


async def _apply_persona(inputs: dict, _org_id: object) -> None:
    """Stand in for the org-row loader used by the three chat paths."""
    inputs.pop("mg_school_blurb", None)
    inputs.update(
        {
            "mg_agent_name": "MindMate",
            "mg_agent_alias": "MindMate",
            "mg_school_name": "Demo School",
        }
    )


@pytest.mark.asyncio
async def test_ai_message_end_omits_conversation_id() -> None:
    """Client-facing end frames do not expose internal Dify conversation ids."""
    broadcasts: list[dict] = []

    async def _capture(_code: str, message: dict) -> None:
        broadcasts.append(message)

    mock_client = MagicMock()

    with (
        patch(
            "services.features.mindmate_collab.dify_stream.resolve_mindmate_dify_stream_short_lived",
            AsyncMock(return_value=MindmateDifyStream(mock_client, False, "conv-9", 1)),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.apply_persona_inputs_for_organization_id",
            AsyncMock(side_effect=_apply_persona),
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
        saved.prev_id = 4
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
            conversation_id="conv-9",
        )

    end_frames = [msg for msg in broadcasts if msg.get("type") == "ai_message_end"]
    assert len(end_frames) == 1
    assert "conversation_id" not in end_frames[0]
    assert end_frames[0]["id"] == 99
    assert end_frames[0]["prev_id"] == 4
    assert mock_client.stream_chat.call_args.kwargs["conversation_id"] == "conv-9"
    assert not any(msg.get("type") == "mindmate_failover" for msg in broadcasts)
    sent = mock_client.stream_chat.call_args.kwargs["inputs"]
    assert sent["mg_dify_user"] == "mindmate_collab_1_sess-1"
    assert sent["mg_conversation_id"] == "conv-9"
    assert sent["mg_agent_name"] == "MindMate"
    assert sent["mg_school_name"] == "Demo School"
    assert "mg_school_blurb" not in sent


@pytest.mark.asyncio
async def test_backup_failover_omits_main_conversation_and_notifies() -> None:
    """A fail-over turn does not send the 主服务器 conversation id to 备用服务器."""
    broadcasts: list[dict] = []

    async def _capture(_code: str, message: dict) -> None:
        broadcasts.append(message)

    mock_client = MagicMock()

    async def _one_chunk_stream(*_args, **_kwargs):
        yield {"answer": "Hi", "conversation_id": "backup-conv"}

    mock_client.stream_chat.return_value = _one_chunk_stream()

    with (
        patch(
            "services.features.mindmate_collab.dify_stream.resolve_mindmate_dify_stream_short_lived",
            AsyncMock(return_value=MindmateDifyStream(mock_client, True, None, 2)),
        ),
        patch(
            "services.features.mindmate_collab.dify_stream.apply_persona_inputs_for_organization_id",
            AsyncMock(side_effect=_apply_persona),
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
        saved.id = 3
        saved.prev_id = 2
        saved.created_at = None
        mgr.persist_message = AsyncMock(return_value=saved)
        mgr.set_dify_conversation_id = AsyncMock()
        mgr_factory.return_value = mgr
        await stream_assistant_reply(
            code="ABC-DEF",
            session_id="sess-1",
            org_id=1,
            user_message="Hello",
            sender_user_id=7,
            conversation_id="conv-9",
        )

    assert broadcasts[0] == {"type": "mindmate_failover"}
    assert mock_client.stream_chat.call_args.kwargs["conversation_id"] is None
    assert mock_client.stream_chat.call_args.kwargs["inputs"]["mg_conversation_id"] == "conv-9"
    mgr.set_dify_conversation_id.assert_not_called()
