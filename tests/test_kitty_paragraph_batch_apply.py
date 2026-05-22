"""Tests for paragraph batch apply helper (persist, hub sync, event bus)."""

from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

online_collab_pkg = types.ModuleType("services.online_collab")
online_collab_pkg.__path__ = []  # type: ignore[attr-defined]
online_collab_redis_pkg = types.ModuleType("services.online_collab.redis")
online_collab_redis_pkg.__path__ = []  # type: ignore[attr-defined]
redis8_features_stub = types.ModuleType("services.online_collab.redis.redis8_features")
redis8_features_stub.timeseries_enabled = lambda: False


async def _ts_record_counter(_key: str, _delta: float) -> None:
    return None


redis8_features_stub.ts_record_counter = _ts_record_counter
sys.modules.setdefault("services.online_collab", online_collab_pkg)
sys.modules.setdefault("services.online_collab.redis", online_collab_redis_pkg)
sys.modules.setdefault("services.online_collab.redis.redis8_features", redis8_features_stub)

from services.kitty.content.paragraph_batch_apply import apply_paragraph_batch_add_nodes
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.ops import create_voice_session


@pytest.mark.asyncio
async def test_apply_paragraph_batch_add_nodes_persists_and_syncs() -> None:
    ws = MagicMock()
    voice_session_id = create_voice_session(
        user_id="1",
        diagram_session_id="para_batch_test",
        diagram_type="circle_map",
    )
    session_context: dict = {"diagram_data": {"children": [], "center": {"text": "Topic"}}}
    voice_sessions[voice_session_id]["context"] = {"diagram_data": {"children": []}}

    nodes = [{"text": "Apple"}, {"text": "Banana", "category": "fruit"}]

    with (
        patch(
            "services.kitty.content.paragraph_batch_apply.safe_websocket_send",
            new=AsyncMock(),
        ) as send_mock,
        patch(
            "services.kitty.content.paragraph_batch_apply.emit_diagram_mutated",
            new=AsyncMock(),
        ) as emit_mock,
        patch(
            "services.kitty.content.paragraph_batch_apply.try_sync_voice_diagram_to_hub",
            new=AsyncMock(),
        ) as hub_mock,
        patch(
            "services.kitty.content.paragraph_batch_apply.kitty_agent_manager.get_or_create",
        ) as agent_mock,
    ):
        agent = MagicMock()
        agent_mock.return_value = agent
        applied = await apply_paragraph_batch_add_nodes(
            ws,
            voice_session_id,
            session_context,
            nodes,
            log_label="test_batch",
        )

    assert applied is True
    send_mock.assert_awaited_once()
    emit_mock.assert_awaited_once()
    hub_mock.assert_awaited_once_with(voice_session_id)
    agent.update_diagram_state.assert_called_once()

    stored = voice_sessions[voice_session_id]["context"]["diagram_data"]["children"]
    assert stored[0]["text"] == "Apple"
    assert stored[1]["text"] == "Banana"
    assert stored[1]["category"] == "fruit"

    voice_sessions.pop(voice_session_id, None)


@pytest.mark.asyncio
async def test_apply_paragraph_batch_add_nodes_noop_when_empty() -> None:
    ws = MagicMock()
    voice_session_id = create_voice_session(
        user_id="1",
        diagram_session_id="para_batch_empty",
        diagram_type="circle_map",
    )
    session_context: dict = {"diagram_data": {"children": []}}

    with patch(
        "services.kitty.content.paragraph_batch_apply.safe_websocket_send",
        new=AsyncMock(),
    ) as send_mock:
        applied = await apply_paragraph_batch_add_nodes(
            ws,
            voice_session_id,
            session_context,
            [],
            log_label="empty",
        )

    assert applied is False
    send_mock.assert_not_awaited()
    voice_sessions.pop(voice_session_id, None)
