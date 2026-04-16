"""Tests for MindBot usage persistence (persist_mindbot_usage_event).

Verifies that DB errors during commit do not raise exceptions and do not
crash the pipeline — the docstring guarantee of isolation from the caller's
DB session.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.mindbot.errors import MindbotErrorCode
from services.mindbot.telemetry.usage import persist_mindbot_usage_event


def _make_cfg(org_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        organization_id=org_id,
        id=10,
        dingtalk_robot_code="robot-test",
    )


def _make_body() -> dict:
    return {
        "senderStaffId": "staff-1",
        "senderNick": "Alice",
        "dingtalkId": "d-1",
    }


@pytest.mark.asyncio
async def test_persist_usage_event_succeeds_silently(monkeypatch: pytest.MonkeyPatch) -> None:
    """Happy-path: event is added and committed without raising."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock()

    @asynccontextmanager
    async def mock_session_local():
        yield mock_session

    monkeypatch.setenv("MINDBOT_USAGE_TRACKING", "true")
    with patch("services.mindbot.telemetry.usage.AsyncSessionLocal", mock_session_local):
        await persist_mindbot_usage_event(
            cfg=_make_cfg(),
            body=_make_body(),
            text_in="hello",
            conversation_id_dt="conv-1",
            user_id="user-1",
            streaming=True,
            error_code=MindbotErrorCode.OK,
            reply_text="world",
            dify_conversation_id="dify-conv-1",
            started_mono=time.monotonic() - 1.0,
            msg_id="msg-1",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            dingtalk_chat_scope="oto",
            inbound_msg_type="text",
            conversation_user_turn=1,
        )
    mock_session.add.assert_called_once()
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_persist_usage_db_error_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
    """DB commit failure must be swallowed — not re-raised — so the pipeline continues."""
    mock_session = AsyncMock()
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock(side_effect=Exception("DB connection lost"))

    @asynccontextmanager
    async def mock_session_local():
        yield mock_session

    monkeypatch.setenv("MINDBOT_USAGE_TRACKING", "true")
    with patch("services.mindbot.telemetry.usage.AsyncSessionLocal", mock_session_local):
        with patch("services.mindbot.telemetry.usage.logger") as mock_logger:
            await persist_mindbot_usage_event(
                cfg=_make_cfg(),
                body=_make_body(),
                text_in="hi",
                conversation_id_dt="conv-2",
                user_id="user-2",
                streaming=False,
                error_code=MindbotErrorCode.DIFY_FAILED,
                reply_text="",
                dify_conversation_id=None,
                started_mono=time.monotonic() - 0.5,
                msg_id="msg-2",
                usage=None,
                dingtalk_chat_scope="group",
                inbound_msg_type="text",
                conversation_user_turn=None,
            )
    # Must have logged a warning (not raised) when the commit failed.
    mock_logger.warning.assert_called_once()
    warning_msg = mock_logger.warning.call_args[0][0]
    assert "usage_persist_failed" in warning_msg


@pytest.mark.asyncio
async def test_persist_usage_session_local_error_does_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even if AsyncSessionLocal itself raises (e.g. pool exhausted), the call is swallowed."""
    class _AlwaysRaising:
        async def __aenter__(self):
            raise RuntimeError("pool exhausted")

        async def __aexit__(self, *_args):
            return False

    def exploding_session_local():
        return _AlwaysRaising()

    monkeypatch.setenv("MINDBOT_USAGE_TRACKING", "true")
    with patch("services.mindbot.telemetry.usage.AsyncSessionLocal", exploding_session_local):
        with patch("services.mindbot.telemetry.usage.logger") as mock_logger:
            await persist_mindbot_usage_event(
                cfg=_make_cfg(),
                body=_make_body(),
                text_in="test",
                conversation_id_dt="conv-3",
                user_id="user-3",
                streaming=True,
                error_code=MindbotErrorCode.OK,
                reply_text="reply",
                dify_conversation_id="d-conv",
                started_mono=time.monotonic(),
                msg_id=None,
                usage=None,
                dingtalk_chat_scope="oto",
                inbound_msg_type="text",
                conversation_user_turn=None,
            )
    # Must have warned that the persist failed (RuntimeError from pool exhausted).
    mock_logger.warning.assert_called_once()
    warning_msg = mock_logger.warning.call_args[0][0]
    assert "usage_persist_failed" in warning_msg


@pytest.mark.asyncio
async def test_persist_usage_skipped_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """When MINDBOT_USAGE_TRACKING=false, nothing is written to the DB."""
    monkeypatch.setenv("MINDBOT_USAGE_TRACKING", "false")

    mock_session_local = MagicMock()

    with patch("services.mindbot.telemetry.usage.AsyncSessionLocal", mock_session_local):
        await persist_mindbot_usage_event(
            cfg=_make_cfg(),
            body=_make_body(),
            text_in="x",
            conversation_id_dt="c",
            user_id="u",
            streaming=False,
            error_code=MindbotErrorCode.OK,
            reply_text="r",
            dify_conversation_id=None,
            started_mono=time.monotonic(),
            msg_id=None,
            usage=None,
            dingtalk_chat_scope="oto",
            inbound_msg_type="text",
            conversation_user_turn=None,
        )
    mock_session_local.assert_not_called()
