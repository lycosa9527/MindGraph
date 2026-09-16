"""Unit tests for long-wait generation result coalescing."""

from __future__ import annotations

import asyncio
from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from services.diagram import generation_result_coalesce as coalesce_mod
from services.diagram.generation_result_coalesce import coalesce_generation


class _FakeRedis:
    """In-memory SET NX / EXISTS / compare-and-delete stand-in."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    async def set(self, key: str, value: str, nx: bool = False, ex: int | None = None) -> bool:
        """SET with optional NX. ``ex`` is accepted to match redis-py and unused."""
        del ex
        if nx and key in self._values:
            return False
        self._values[key] = value
        return True

    async def exists(self, key: str) -> int:
        """Return 1 when the key is present."""
        return 1 if key in self._values else 0

    async def delete(self, key: str) -> int:
        """Delete a key and report whether it existed."""
        return 1 if self._values.pop(key, None) is not None else 0

    def release(self, key: str) -> None:
        """Drop the lock key after the winner finishes."""
        self._values.pop(key, None)


@pytest.mark.asyncio
async def test_coalesce_one_loader_waiters_read_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concurrent callers run the loader once; waiters take the cached value."""
    redis = _FakeRedis()
    monkeypatch.setattr(coalesce_mod, "is_redis_available", lambda: True)
    monkeypatch.setattr(coalesce_mod, "get_async_redis", lambda: redis)

    async def fake_compare_and_delete(key: str, _expected: str) -> bool:
        redis.release(key)
        return True

    monkeypatch.setattr(
        coalesce_mod.AsyncRedisOps,
        "compare_and_delete",
        staticmethod(fake_compare_and_delete),
    )

    cache: dict[str, Any] = {}
    load_count = 0
    started = asyncio.Event()

    async def loader() -> dict[str, Any]:
        nonlocal load_count
        load_count += 1
        started.set()
        await asyncio.sleep(0.08)
        cache["spec"] = {"topic": "aaa"}
        return {"success": True, "spec": cache["spec"]}

    async def reader() -> Optional[dict[str, Any]]:
        if "spec" in cache:
            return {"success": True, "spec": cache["spec"]}
        return None

    async def winner() -> dict[str, Any]:
        return await coalesce_generation(
            "gen:lock:1:fp",
            loader,
            reader,
            lock_ttl=5,
            wait_timeout=1.0,
            poll_interval=0.02,
        )

    async def waiter() -> dict[str, Any]:
        await started.wait()
        return await coalesce_generation(
            "gen:lock:1:fp",
            loader,
            reader,
            lock_ttl=5,
            wait_timeout=1.0,
            poll_interval=0.02,
        )

    first, second = await asyncio.gather(winner(), waiter())
    assert load_count == 1
    assert first["spec"] == {"topic": "aaa"}
    assert second["spec"] == {"topic": "aaa"}


@pytest.mark.asyncio
async def test_coalesce_cancel_skips_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disconnected waiters stop polling and do not start a second LLM call."""
    redis = _FakeRedis()
    await redis.set("gen:lock:1:fp", "holder", nx=True, ex=5)
    monkeypatch.setattr(coalesce_mod, "is_redis_available", lambda: True)
    monkeypatch.setattr(coalesce_mod, "get_async_redis", lambda: redis)

    load_count = 0

    async def loader() -> dict[str, Any]:
        nonlocal load_count
        load_count += 1
        return {"success": True}

    async def reader() -> Optional[dict[str, Any]]:
        return None

    cancel_event = asyncio.Event()
    cancel_event.set()
    with pytest.raises(asyncio.CancelledError):
        await coalesce_generation(
            "gen:lock:1:fp",
            loader,
            reader,
            cancel_event=cancel_event,
            lock_ttl=5,
            wait_timeout=1.0,
            poll_interval=0.02,
        )
    assert load_count == 0


@pytest.mark.asyncio
async def test_coalesce_fail_open_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    """Redis down runs the loader immediately so generation still works."""
    monkeypatch.setattr(coalesce_mod, "is_redis_available", lambda: False)
    loader = AsyncMock(return_value={"ok": True})
    reader = AsyncMock(return_value=None)
    result = await coalesce_generation("gen:lock:1:fp", loader, reader)
    assert result == {"ok": True}
    loader.assert_awaited_once()
    reader.assert_not_awaited()
