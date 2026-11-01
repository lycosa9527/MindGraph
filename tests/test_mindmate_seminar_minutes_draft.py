"""Seminar minutes drafts go to qwen3.8-flash, not the MindMate chat stream."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from routers.api.mindmate_seminar_routes import router
from services.features.mindmate_seminar.minutes_draft import (
    SEMINAR_MINUTES_MODEL,
    MinutesDraftInput,
    build_minutes_prompt,
    draft_seminar_minutes,
)


def _draft() -> MinutesDraftInput:
    return MinutesDraftInput(
        zh=True,
        topic="导入环节",
        goals=["先改导入"],
        speakers="王雅萱（组长）",
        observers="",
        files=["框架.pdf"],
        quotes=["王雅萱：先改导入"],
        transcript="王雅萱：这节课的导入太长，我们先改导入。",
    )


def _mounted_paths() -> set[str]:
    """Paths after included seminar routers pick up the parent prefix."""
    paths: set[str] = set()
    for route in router.routes:
        direct = getattr(route, "path", "")
        if isinstance(direct, str) and direct:
            paths.add(direct)
        candidates = getattr(route, "effective_candidates", None)
        if callable(candidates):
            candidates = candidates()
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            mounted = getattr(candidate, "path", "")
            if isinstance(mounted, str) and mounted:
                paths.add(mounted)
    return paths


def test_minutes_route_is_registered() -> None:
    """The live room can ask for a draft without posting into MindMate chat."""
    assert "/mindmate/seminar/{session_id}/minutes" in _mounted_paths()


def test_prompt_keeps_the_transcript_and_asks_for_json() -> None:
    """The model sees the seminar text and the minutes keys, not a chat opener."""
    prompt = build_minutes_prompt(_draft())
    assert "只输出 JSON" in prompt
    assert "consensus" in prompt
    assert "先改导入" in prompt
    assert "框架.pdf" in prompt
    assert "这节课的导入太长" in prompt


def test_prompt_keeps_the_end_of_a_long_transcript() -> None:
    """A long seminar keeps the latest lines. The old chat cap dropped the call."""
    head = "甲：开头。" * 20
    tail = "乙：最后决定先改导入。"
    prompt = build_minutes_prompt(
        MinutesDraftInput(
            zh=True,
            topic="",
            goals=[],
            speakers="",
            observers="",
            files=[],
            quotes=[],
            transcript=head + ("记。" * 60_000) + tail,
        )
    )
    assert tail in prompt
    assert "甲：开头。" not in prompt


@pytest.mark.asyncio
async def test_draft_calls_qwen38_flash() -> None:
    """The draft uses the pinned flash model and returns its JSON text."""
    reply = '{"goals":[],"consensus":["先改导入"],"open":[],"materials":[],"tasks":[],"quotes":[]}'
    chat = AsyncMock(return_value=reply)
    with patch("services.features.mindmate_seminar.minutes_draft.llm_service.chat", chat):
        text = await draft_seminar_minutes(_draft(), user_id=7, organization_id=3)
    assert text == reply
    assert chat.await_args is not None
    kwargs = chat.await_args.kwargs
    assert kwargs["model"] == SEMINAR_MINUTES_MODEL
    assert kwargs["model"] == "qwen3.8-flash"
    assert kwargs["request_type"] == "mindmate"
    assert kwargs["response_format"] == {"type": "json_object"}
    assert kwargs["use_knowledge_base"] is False
    assert "这节课的导入太长" in kwargs["prompt"]


@pytest.mark.asyncio
async def test_draft_rejects_an_empty_model_reply() -> None:
    """A blank completion is a failure, not an empty minutes card."""
    chat = AsyncMock(return_value="   ")
    with patch("services.features.mindmate_seminar.minutes_draft.llm_service.chat", chat):
        with pytest.raises(ValueError, match="empty_reply"):
            await draft_seminar_minutes(_draft(), user_id=7, organization_id=None)
