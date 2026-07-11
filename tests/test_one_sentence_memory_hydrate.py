"""Tests for one-sentence memory hydrate and request_id turn normalize."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.kitty.session.memory import get_session_memory, remove_session_memory
from services.kitty.session.one_sentence_memory_hydrate import (
    hydrate_one_sentence_session_memory,
)
from services.kitty.session.one_sentence_turns import _normalize_turn_payload
from services.kitty.session.runtime_state import voice_sessions


def test_normalize_turn_keeps_request_id() -> None:
    """Turn normalize preserves request_id for conversation correlation."""
    turn = _normalize_turn_payload(
        {
            "role": "user",
            "content": "添加分支",
            "phase": "edit",
            "source": "ws_text",
            "request_id": "req-abc",
        }
    )
    assert turn is not None
    assert turn["request_id"] == "req-abc"


@pytest.mark.asyncio
async def test_hydrate_one_sentence_session_memory() -> None:
    """Hydrate loads PG turns into session memory and conversation_history."""
    voice_session_id = "vs-hydrate-1"
    remove_session_memory(voice_session_id)
    voice_sessions[voice_session_id] = {
        "active_panel": "one_sentence",
        "diagram_session_id": "scope-1",
        "user_id": "7",
        "conversation_history": [],
    }

    turns = [
        {
            "turn_id": "t1",
            "role": "user",
            "content": "添加历史分支",
            "phase": "edit",
            "source": "ws_text",
            "request_id": "r1",
        },
        {
            "turn_id": "t2",
            "role": "kitty",
            "content": "已添加",
            "phase": "edit",
            "source": "ack",
            "request_id": "r1",
            "outcome": "success",
        },
    ]

    with patch(
        "services.kitty.session.one_sentence_memory_hydrate.list_one_sentence_turns",
        new=AsyncMock(return_value={"ok": True, "turns": turns}),
    ):
        applied = await hydrate_one_sentence_session_memory(
            voice_session_id=voice_session_id,
            user_id=7,
            diagram_scope="scope-1",
        )

    assert applied == 2
    mem = get_session_memory(voice_session_id)
    assert len(mem.turns) == 2
    assert mem.turns[0].role == "user"
    assert mem.turns[0].content == "添加历史分支"
    assert mem.turns[1].role == "assistant"
    history = voice_sessions[voice_session_id]["conversation_history"]
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"

    remove_session_memory(voice_session_id)
    voice_sessions.pop(voice_session_id, None)
