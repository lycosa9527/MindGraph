"""MindMate collab session chat acceptance guard."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.features.mindmate_collab.manager import MindmateCollabManager


@pytest.mark.asyncio
async def test_session_accepts_chat_false_when_closing() -> None:
    """Reject chat while the room is in closing state."""
    mgr = MindmateCollabManager()
    with patch.object(mgr, "session_is_closing", AsyncMock(return_value=True)):
        assert await mgr.session_accepts_chat("ABC-DEF") is False


@pytest.mark.asyncio
async def test_session_accepts_chat_false_when_not_live() -> None:
    """Reject chat when no live session row exists for the code."""
    mgr = MindmateCollabManager()
    with (
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=False)),
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=None)),
    ):
        assert await mgr.session_accepts_chat("ABC-DEF") is False


@pytest.mark.asyncio
async def test_session_accepts_chat_true_for_live_room() -> None:
    """Accept chat for a live room that is not closing."""
    mgr = MindmateCollabManager()
    live_session = object()
    with (
        patch.object(mgr, "session_is_closing", AsyncMock(return_value=False)),
        patch.object(mgr, "load_session_by_code", AsyncMock(return_value=live_session)),
    ):
        assert await mgr.session_accepts_chat("ABC-DEF") is True
