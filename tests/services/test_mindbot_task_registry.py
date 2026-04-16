"""Tests for services/mindbot/infra/task_registry.py."""

from __future__ import annotations

import asyncio

import pytest

import services.mindbot.infra.task_registry as registry


@pytest.fixture(autouse=True)
def _clear_active() -> None:
    """Ensure _active set is empty before and after each test."""
    registry._active.clear()
    yield
    registry._active.clear()


class TestRegister:
    """Tests for register()."""

    @pytest.mark.asyncio
    async def test_task_appears_in_active_while_running(self) -> None:
        event = asyncio.Event()
        task = asyncio.ensure_future(event.wait())
        registry.register(task)
        assert task in registry._active
        event.set()
        await task

    @pytest.mark.asyncio
    async def test_task_removed_from_active_when_done(self) -> None:
        async def noop() -> None:
            pass

        task = asyncio.ensure_future(noop())
        registry.register(task)
        await task
        await asyncio.sleep(0)
        assert task not in registry._active


class TestDrain:
    """Tests for drain()."""

    @pytest.mark.asyncio
    async def test_drain_empty_returns_immediately(self) -> None:
        await registry.drain(timeout_s=1.0)

    @pytest.mark.asyncio
    async def test_drain_waits_for_tasks_to_finish(self) -> None:
        results: list[str] = []

        async def slow_task() -> None:
            await asyncio.sleep(0.02)
            results.append("done")

        task = asyncio.ensure_future(slow_task())
        registry.register(task)
        await registry.drain(timeout_s=5.0)
        assert results == ["done"]
        assert registry._active == set()

    @pytest.mark.asyncio
    async def test_drain_with_timeout_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        event = asyncio.Event()

        async def blocking_task() -> None:
            await event.wait()

        task = asyncio.ensure_future(blocking_task())
        registry.register(task)
        with caplog.at_level(logging.WARNING, logger="services.mindbot.infra.task_registry"):
            await registry.drain(timeout_s=0.05)
        assert "still pending" in caplog.text
        event.set()
        await task

    @pytest.mark.asyncio
    async def test_drain_cancels_pending_when_env_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MINDBOT_SHUTDOWN_CANCEL_PENDING", "true")

        blocked = asyncio.Event()

        async def blocking_task() -> None:
            await blocked.wait()

        task = asyncio.ensure_future(blocking_task())
        registry.register(task)
        await registry.drain(timeout_s=0.05)
        assert task.cancelled() or task.done()
