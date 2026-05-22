"""Tests for debounced Omni context refresh."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.omni.context_refresh import schedule_omni_context_refresh
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.session.ops import create_voice_session


@pytest.mark.asyncio
async def test_pedagogical_review_uses_deep_instructions() -> None:
    voice_session_id = create_voice_session(
        user_id="1",
        diagram_session_id="omni_ped_review",
        diagram_type="circle_map",
    )
    omni = MagicMock()
    omni.update_instructions = AsyncMock()
    voice_sessions[voice_session_id]["context"] = {
        "diagram_data": {"children": [{"text": "A"}], "center": {"text": "Topic"}},
    }
    voice_sessions[voice_session_id]["omni_client"] = omni

    with patch(
        "services.kitty.omni.context_refresh.build_voice_instructions",
        return_value="deep-instructions",
    ) as build_mock:
        await schedule_omni_context_refresh(voice_session_id, reason="pedagogical_review")
        await asyncio.sleep(0)

    build_mock.assert_called_once()
    assert build_mock.call_args.kwargs.get("diagram_review_deep") is True
    omni.update_instructions.assert_awaited_once_with("deep-instructions")
    voice_sessions.pop(voice_session_id, None)
