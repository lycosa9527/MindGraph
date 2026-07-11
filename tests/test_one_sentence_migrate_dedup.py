"""Redis migrate dedupes by turn_id."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.kitty.session.one_sentence_turns import migrate_one_sentence_scope


@pytest.mark.asyncio
async def test_migrate_redis_dedupes_turn_id() -> None:
    """Redis migrate skips turn_ids already present on the target scope."""
    source_scope = "ephemeral-scope"
    target_scope = "library-scope"
    user_id = 9

    source_rows = [
        json.dumps(
            {
                "turn_id": "shared-1",
                "ts": 1,
                "role": "user",
                "content": "hello",
                "phase": "edit",
                "source": "ws_text",
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "turn_id": "only-source",
                "ts": 2,
                "role": "kitty",
                "content": "hi",
                "phase": "edit",
                "source": "ack",
            },
            ensure_ascii=False,
        ),
    ]
    target_rows = [
        json.dumps(
            {
                "turn_id": "shared-1",
                "ts": 1,
                "role": "user",
                "content": "hello",
                "phase": "edit",
                "source": "ws_text",
            },
            ensure_ascii=False,
        ),
    ]

    pushed: list[str] = []
    redis = MagicMock()

    async def fake_lrange(key, _start, _end):
        key_s = str(key)
        if source_scope in key_s:
            return source_rows
        return target_rows

    redis.lrange = AsyncMock(side_effect=fake_lrange)
    redis.get = AsyncMock(return_value=None)
    redis.delete = AsyncMock()

    pipe = MagicMock()
    pipe.rpush = MagicMock(side_effect=lambda _key, val: pushed.append(val))
    pipe.ltrim = MagicMock()
    pipe.expire = MagicMock()
    pipe.set = MagicMock()
    pipe.delete = MagicMock()
    pipe.execute = AsyncMock(return_value=[])

    class _PipeCtx:
        async def __aenter__(self):
            return pipe

        async def __aexit__(self, *_args):
            return False

    redis.pipeline = MagicMock(return_value=_PipeCtx())

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
            "services.kitty.session.one_sentence_turns.migrate_one_sentence_scope_pg",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "services.kitty.session.one_sentence_turns._read_meta",
            new=AsyncMock(
                side_effect=lambda scope: {
                    "user_id": user_id,
                    "scope": scope,
                    "turn_count": 1,
                }
            ),
        ),
    ):
        result = await migrate_one_sentence_scope(
            user_id=user_id,
            from_scope=source_scope,
            to_scope=target_scope,
        )

    assert result["ok"] is True
    assert len(pushed) == 1
    assert json.loads(pushed[0])["turn_id"] == "only-source"
