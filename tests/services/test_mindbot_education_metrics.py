"""Tests for MindBot educational research helpers."""

from __future__ import annotations

import pytest

from services.mindbot.education import metrics as mindbot_edu


def test_chat_scope_group() -> None:
    assert mindbot_edu.dingtalk_chat_scope({"conversationType": "2"}) == "group"
    assert mindbot_edu.dingtalk_chat_scope({"conversation_type": "group"}) == "group"


def test_chat_scope_oto() -> None:
    assert mindbot_edu.dingtalk_chat_scope({"conversationType": "1"}) == "oto"


def test_chat_scope_unknown() -> None:
    assert mindbot_edu.dingtalk_chat_scope({}) == "unknown"


@pytest.mark.asyncio
async def test_turn_index_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mindbot_edu, "education_metrics_enabled", lambda: False)
    out = await mindbot_edu.conversation_user_turn_index(1, "c1")
    assert out is None
