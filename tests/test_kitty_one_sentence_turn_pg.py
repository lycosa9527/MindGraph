"""Tests for one-sentence PG persistence and activity hooks."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from services.kitty.session.one_sentence_turn_activity import (
    _resolve_teacher_activity_type,
    _resolve_usage_action,
)
from services.kitty.session.one_sentence_turn_pg import (
    persist_one_sentence_turn_pg,
    turn_dict_to_row,
)


def test_turn_dict_to_row_maps_fields() -> None:
    """Normalized turn dict maps to ORM columns."""
    row = turn_dict_to_row(
        user_id=7,
        organization_id=3,
        scope="diagram-scope",
        session_id="sess-1",
        turn={
            "turn_id": "abc",
            "ts": 1_700_000_000,
            "role": "user",
            "content": "添加历史分支",
            "phase": "edit",
            "source": "ws_text",
            "diagram_type": "mindmap",
        },
    )
    assert row.turn_id == "abc"
    assert row.role == "user"
    assert row.diagram_type == "mindmap"


def test_resolve_usage_action_create_user() -> None:
    """Create-phase user prompt maps to one_sentence_generate."""
    action = _resolve_usage_action({"role": "user", "phase": "create", "content": "主题"})
    assert action == "one_sentence_generate"


def test_resolve_teacher_activity_executed_kitty() -> None:
    """Executed kitty ack counts as teacher one_sentence_edit."""
    activity = _resolve_teacher_activity_type({"role": "kitty", "outcome": "executed", "content": "历史分支已补完。"})
    assert activity == "one_sentence_edit"


@pytest.mark.asyncio
async def test_persist_one_sentence_turn_pg_commits_on_insert() -> None:
    """PG persist commits and schedules activity when insert succeeds."""
    session = AsyncMock()
    session.commit = AsyncMock()

    session_ctx = AsyncMock()

    async def _enter_session(*_args: object, **_kwargs: object) -> AsyncMock:
        return session

    session_ctx.__aenter__.side_effect = _enter_session
    session_ctx.__aexit__.return_value = False

    with patch("services.kitty.session.one_sentence_turn_pg.system_rls_session", return_value=session_ctx):
        with (
            patch(
                "services.kitty.session.one_sentence_turn_pg.ensure_one_sentence_session",
                new=AsyncMock(return_value="sess-1"),
            ),
            patch("services.kitty.session.one_sentence_turn_pg.KittyOneSentenceTurnRepository") as repo_cls,
        ):
            repo_cls.return_value.insert_ignore_duplicate = AsyncMock(return_value=True)
            with (
                patch(
                    "services.kitty.session.one_sentence_turn_pg.record_session_turn_metadata",
                    new=AsyncMock(),
                ),
                patch(
                    "services.kitty.session.one_sentence_turn_pg.schedule_one_sentence_turn_activity"
                ) as schedule_mock,
            ):
                ok = await persist_one_sentence_turn_pg(
                    user_id=9,
                    organization_id=2,
                    scope="scope-1",
                    turn={
                        "turn_id": "t1",
                        "ts": int(datetime.now(UTC).timestamp()),
                        "role": "user",
                        "content": "北京三日游",
                        "phase": "create",
                        "source": "ui_create",
                    },
                )
    assert ok is True
    session.commit.assert_awaited_once()
    schedule_mock.assert_called_once()
