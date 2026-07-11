"""Tests for PG-first conversation logging and request_id insert."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from repositories.kitty_one_sentence_turn_repo import KittyOneSentenceTurnRepository
from services.kitty.session.one_sentence_turn_pg import turn_dict_to_row
from services.kitty.session.one_sentence_turns import (
    _merge_turns_by_id,
    append_one_sentence_turn,
)


def test_merge_turns_prefers_primary_and_keeps_redis_only() -> None:
    """Merge prefers primary rows and retains redis-only turn ids."""
    primary = [
        {
            "turn_id": "a",
            "ts": 1,
            "role": "user",
            "content": "from-pg",
            "request_id": "r1",
        }
    ]
    secondary = [
        {
            "turn_id": "a",
            "ts": 1,
            "role": "user",
            "content": "from-redis",
            "request_id": "r1",
        },
        {
            "turn_id": "b",
            "ts": 2,
            "role": "kitty",
            "content": "redis-only",
            "request_id": "r1",
        },
    ]
    merged = _merge_turns_by_id(primary, secondary, cap=10)
    assert len(merged) == 2
    assert merged[0]["content"] == "from-pg"
    assert merged[1]["turn_id"] == "b"


@pytest.mark.asyncio
async def test_append_logs_to_pg_when_redis_unavailable():
    """Conversation must still land in PG when Redis is down."""
    scheduled: list[dict] = []

    def _schedule(**kwargs):
        scheduled.append(kwargs["turn"])

    with (
        patch(
            "services.kitty.session.one_sentence_turns.get_async_redis",
            return_value=None,
        ),
        patch(
            "services.kitty.session.one_sentence_turns.user_may_access_kitty_scope",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.session.one_sentence_turns.ensure_one_sentence_session",
            new=AsyncMock(return_value="sess-1"),
        ),
        patch(
            "services.kitty.session.one_sentence_turns.schedule_one_sentence_turn_pg",
            side_effect=_schedule,
        ),
    ):
        row = await append_one_sentence_turn(
            "scope-pg-only",
            11,
            {
                "role": "user",
                "content": "添加分支",
                "phase": "edit",
                "source": "ui_edit",
                "request_id": "req-pg-1",
            },
        )

    assert row is not None
    assert row["request_id"] == "req-pg-1"
    assert len(scheduled) == 1
    assert scheduled[0]["request_id"] == "req-pg-1"


@pytest.mark.asyncio
async def test_insert_ignore_duplicate_includes_request_id():
    """PG INSERT values must include request_id so conversation correlation survives."""
    session = AsyncMock()
    executed = {}

    async def _execute(stmt):
        executed["values"] = stmt.compile().params
        result = MagicMock()
        result.rowcount = 1
        return result

    session.execute = AsyncMock(side_effect=_execute)
    repo = KittyOneSentenceTurnRepository(session)
    row = turn_dict_to_row(
        user_id=1,
        organization_id=2,
        scope="scope-1",
        session_id="sess-1",
        turn={
            "turn_id": "t-1",
            "ts": 1_700_000_000,
            "role": "user",
            "content": "hello",
            "phase": "edit",
            "source": "ws_text",
            "request_id": "req-insert-1",
        },
    )
    with patch(
        "repositories.kitty_one_sentence_turn_repo.result_rowcount",
        return_value=1,
    ):
        ok = await repo.insert_ignore_duplicate(row)

    assert ok is True
    assert executed["values"].get("request_id") == "req-insert-1"
