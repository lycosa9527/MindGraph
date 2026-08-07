"""DebateVerse stream: short RLS around LLM/TTS."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from routers.features.debateverse import stream as stream_mod


@pytest.mark.asyncio
async def test_stream_debater_closes_rls_before_llm() -> None:
    """Context load session must exit before chat_stream runs."""
    session_open = {"value": False}
    llm_saw_closed: list[bool] = []

    fake_cm = MagicMock()

    async def _enter(_self: object) -> MagicMock:
        session_open["value"] = True
        return MagicMock()

    async def _exit(_self: object, *_args: object) -> bool:
        session_open["value"] = False
        return False

    fake_cm.__aenter__ = _enter
    fake_cm.__aexit__ = _exit

    async def _chat_stream(**_kwargs: object):
        llm_saw_closed.append(not session_open["value"])
        yield {"type": "token", "content": "hello"}

    tts = MagicMock()
    tts.is_available.return_value = False

    with (
        patch.object(stream_mod, "user_rls_session", return_value=fake_cm),
        patch.object(
            stream_mod,
            "_load_stream_context",
            new=AsyncMock(
                return_value=(
                    [{"role": "user", "content": "hi"}],
                    "qwen",
                    "debater",
                )
            ),
        ),
        patch.object(stream_mod, "get_tts_service", return_value=tts),
        patch.object(stream_mod.llm_service, "chat_stream", side_effect=_chat_stream),
        patch.object(
            stream_mod,
            "_persist_stream_message",
            new=AsyncMock(return_value=(42, None)),
        ),
    ):
        chunks = [
            chunk
            async for chunk in stream_mod.stream_debater_response(
                session_id="sess-1",
                participant_id=3,
                stage="opening",
                language="zh",
                user_id=7,
            )
        ]

    assert llm_saw_closed == [True]
    assert any('"type": "token"' in chunk for chunk in chunks)
    assert any('"type": "done"' in chunk for chunk in chunks)
    assert session_open["value"] is False
