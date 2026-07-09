"""Tests for one-sentence panel turn persistence."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.one_sentence_turns import (
    append_one_sentence_turn,
    list_one_sentence_turns,
)


@pytest.mark.asyncio
async def test_append_and_list_one_sentence_turns():
    """Append stores a turn in Redis and list returns it for the same owner."""
    scope = "test-scope-uuid"
    user_id = 42
    stored: list[str] = []
    meta_holder: dict[str, str] = {}

    redis = MagicMock()

    async def fake_get(key):
        if key.endswith("one_sentence:meta"):
            return meta_holder.get("meta")
        return None

    async def fake_set(key, value, _ex=None):
        if key.endswith("one_sentence:meta"):
            meta_holder["meta"] = value

    pipe = MagicMock()
    pipe.set = MagicMock()
    pipe.rpush = MagicMock(side_effect=lambda _key, val: stored.append(val))
    pipe.ltrim = MagicMock()
    pipe.expire = MagicMock()
    pipe.execute = AsyncMock(return_value=[])

    class _PipeCtx:
        async def __aenter__(self):
            return pipe

        async def __aexit__(self, *_args):
            return False

    redis.get = AsyncMock(side_effect=fake_get)
    redis.set = AsyncMock(side_effect=fake_set)
    redis.pipeline = MagicMock(return_value=_PipeCtx())
    redis.lrange = AsyncMock(
        return_value=[
            json.dumps(
                {
                    "turn_id": "t1",
                    "ts": 1,
                    "role": "user",
                    "content": "添加历史分支",
                    "phase": "edit",
                    "source": "ws_text",
                },
                ensure_ascii=False,
            )
        ]
    )

    with (
        patch(
            "services.kitty.session.one_sentence_turns.get_async_redis",
            return_value=redis,
        ),
        patch(
            "services.kitty.session.one_sentence_turns.user_may_access_kitty_scope",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.session.one_sentence_turns.ensure_one_sentence_session",
            new=AsyncMock(return_value="sess-abc"),
        ),
        patch(
            "services.kitty.session.one_sentence_turns.schedule_one_sentence_turn_pg",
        ),
        patch(
            "services.kitty.session.one_sentence_turns.list_one_sentence_turns_pg",
            new=AsyncMock(return_value=[]),
        ),
    ):
        row = await append_one_sentence_turn(
            scope,
            user_id,
            {
                "role": "user",
                "content": "添加历史分支",
                "phase": "edit",
                "source": "ws_text",
            },
        )
        assert row is not None
        assert row["content"] == "添加历史分支"
        assert len(stored) == 1

        meta_holder["meta"] = json.dumps({"user_id": user_id})
        payload = await list_one_sentence_turns(scope, user_id, limit=10)
        assert payload["ok"] is True
        assert payload["turns"][0]["role"] == "user"


@pytest.mark.asyncio
async def test_append_rejects_invalid_role():
    """Invalid role payloads are rejected without writing."""
    with patch(
        "services.kitty.session.one_sentence_turns.get_async_redis",
        return_value=MagicMock(),
    ):
        row = await append_one_sentence_turn(
            "scope",
            1,
            {"role": "invalid", "content": "x", "source": "test"},
        )
        assert row is None
