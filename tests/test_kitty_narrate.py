"""Kitty narrate is lecture TTS, not command ingress."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.kitty.ws.narrate import handle_kitty_narrate


def test_inbound_routes_narrate_before_text_ingress() -> None:
    """Narrate is handled before WS text ingress and does not begin_ingress."""
    source = Path("services/kitty/ws/inbound.py").read_text(encoding="utf-8")
    narrate_at = source.index('if msg_type == "narrate"')
    text_at = source.index('if msg_type == "text"')
    assert narrate_at < text_at
    narrate_src = Path("services/kitty/ws/narrate.py").read_text(encoding="utf-8")
    assert "begin_ingress" not in narrate_src
    assert "conversation_history" not in narrate_src


@pytest.mark.asyncio
async def test_handle_kitty_narrate_speaks_without_history(monkeypatch: pytest.MonkeyPatch) -> None:
    """Lecture TTS must not append the caption to conversation history."""
    sent: list[dict] = []
    session: dict = {"conversation_history": []}

    async def fake_send(_websocket, payload):
        """Capture the lecture text_chunk frame."""
        sent.append(payload)

    async def speak(*_args, **_kwargs) -> None:
        """Assert lecture metadata is still set while enqueueing TTS."""
        assert session.get("_kitty_lecture") is True
        assert session.get("_kitty_lecture_step_id") == "s1"

    speak_mock = AsyncMock(side_effect=speak)
    monkeypatch.setattr("services.kitty.ws.narrate.safe_websocket_send", fake_send)
    monkeypatch.setattr("services.kitty.ws.narrate.speak_kitty_final_reply", speak_mock)
    monkeypatch.setattr("services.kitty.ws.narrate.voice_sessions", {"sid": session})

    await handle_kitty_narrate(MagicMock(), "sid", {"text": "Hello class", "step_id": "s1"})

    assert sent[0]["reply_kind"] == "lecture"
    speak_mock.assert_awaited_once()
    called = speak_mock.await_args
    assert called is not None
    assert called.kwargs.get("force") is True
    assert session.get("_kitty_lecture") is False
    assert "_kitty_lecture_step_id" not in session
    assert not session["conversation_history"]
