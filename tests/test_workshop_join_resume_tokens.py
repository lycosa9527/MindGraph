"""Tests for Redis join resume tokens."""

from __future__ import annotations

import pytest

from services.online_collab.participant import workshop_join_resume_tokens as tokens


class _FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def setex(self, key: str, _ttl: int, val: str) -> bool:
        self.data[key] = val
        return True

    async def get(self, key: str) -> str | None:
        return self.data.get(key)

    async def delete(self, key: str) -> int:
        if key in self.data:
            del self.data[key]
            return 1
        return 0


@pytest.mark.asyncio
async def test_resume_mint_then_consume_deletes(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(tokens, 'get_async_redis', lambda: fake)

    tok = await tokens.mint_join_resume_token_async(
        user_id=101,
        workshop_code_upper='CODE-AAA',
        diagram_id='diag-uuid',
    )
    assert tok
    consumed = await tokens.try_consume_join_resume_token_async(
        raw_query_token=tok,
        user_id=101,
        workshop_code_upper='CODE-AAA',
        diagram_id='diag-uuid',
    )
    assert consumed is True


@pytest.mark.asyncio
async def test_resume_wrong_user_leaves_blob(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(tokens, 'get_async_redis', lambda: fake)

    tok = await tokens.mint_join_resume_token_async(
        user_id=2,
        workshop_code_upper='CODE-B',
        diagram_id='d2',
    )
    consumed = await tokens.try_consume_join_resume_token_async(
        raw_query_token=tok,
        user_id=3,
        workshop_code_upper='CODE-B',
        diagram_id='d2',
    )
    assert consumed is False
    assert len(fake.data) == 1
