"""Process monitor Celery health: liveness plus stale-banner restart."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.infrastructure.monitoring.process_monitor import (
    ProcessMonitor,
    ServiceStatus,
    check_celery_worker_health,
    reset_celery_banner_check_state,
)
from services.infrastructure.process import _celery_manager as celery_manager


@pytest.fixture(autouse=True)
def _reset_banner_state() -> None:
    reset_celery_banner_check_state()


def _app_with_banner(active: dict | None, registered: dict | None) -> MagicMock:
    inspect = MagicMock()
    inspect.active.return_value = active
    inspect.registered.return_value = registered
    inspect.ping.return_value = {"worker@a": {"ok": "pong"}}
    control = MagicMock()
    control.inspect.return_value = inspect
    app = MagicMock()
    app.control = control
    return app


@pytest.mark.asyncio
async def test_celery_health_managed_current_banner_is_healthy() -> None:
    """Live PID plus a current task banner is healthy."""
    proc = MagicMock()
    proc.poll.return_value = None
    app = _app_with_banner(
        {"worker@ok": []},
        {"worker@ok": ["mind_classroom.run_script"]},
    )
    with (
        patch.object(celery_manager, "required_app_task_names", return_value={"mind_classroom.run_script"}),
        patch(
            "services.infrastructure.monitoring.process_monitor.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
        ),
    ):
        status = await check_celery_worker_health(
            app=app,
            managed_process=proc,
            worker_needed=True,
        )
    assert status == ServiceStatus.HEALTHY


@pytest.mark.asyncio
async def test_celery_health_managed_stale_banner_is_degraded() -> None:
    """A live worker missing current tasks must be replaced."""
    proc = MagicMock()
    proc.poll.return_value = None
    app = _app_with_banner(
        {"worker@old": []},
        {"worker@old": ["showcase.generate_cover"]},
    )
    with (
        patch.object(celery_manager, "required_app_task_names", return_value={"mind_classroom.run_script"}),
        patch(
            "services.infrastructure.monitoring.process_monitor.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
        ),
    ):
        status = await check_celery_worker_health(
            app=app,
            managed_process=proc,
            worker_needed=True,
        )
    assert status == ServiceStatus.DEGRADED


@pytest.mark.asyncio
async def test_celery_health_skips_banner_within_ttl() -> None:
    """After a current banner, do not inspect again until the TTL elapses."""
    proc = MagicMock()
    proc.poll.return_value = None
    app = _app_with_banner(
        {"worker@ok": []},
        {"worker@ok": ["mind_classroom.run_script"]},
    )
    with (
        patch.object(celery_manager, "required_app_task_names", return_value={"mind_classroom.run_script"}),
        patch(
            "services.infrastructure.monitoring.process_monitor.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
        ),
    ):
        first = await check_celery_worker_health(
            app=app,
            managed_process=proc,
            worker_needed=True,
            now=1_000.0,
        )
        app.control.inspect.reset_mock()
        second = await check_celery_worker_health(
            app=app,
            managed_process=proc,
            worker_needed=True,
            now=1_010.0,
        )
    assert first == ServiceStatus.HEALTHY
    assert second == ServiceStatus.HEALTHY
    app.control.inspect.assert_not_called()


@pytest.mark.asyncio
async def test_celery_health_unmanaged_uses_ping_then_banner() -> None:
    """External workers: ping first, then compare the task banner."""
    app = _app_with_banner(
        {"worker@a": []},
        {"worker@a": ["mind_classroom.run_script"]},
    )
    with (
        patch.object(celery_manager, "required_app_task_names", return_value={"mind_classroom.run_script"}),
        patch(
            "services.infrastructure.monitoring.process_monitor.asyncio.to_thread",
            new=AsyncMock(side_effect=lambda fn, *args: fn(*args)),
        ),
    ):
        status = await check_celery_worker_health(
            app=app,
            managed_process=None,
            worker_needed=True,
        )
    assert status == ServiceStatus.HEALTHY
    app.control.inspect.return_value.ping.assert_called()


@pytest.mark.asyncio
async def test_process_monitor_restarts_celery_on_stale_banner() -> None:
    """Stale banner restarts Celery even when the old PID is still alive."""
    monitor = ProcessMonitor()
    proc = MagicMock()
    proc.poll.return_value = None
    with (
        patch("services.infrastructure.monitoring.process_monitor.ServerState") as state,
        patch(
            "services.infrastructure.monitoring.process_monitor.PROCESS_MONITOR_CIRCUIT_BREAKER_ENABLED",
            False,
        ),
        patch.object(monitor, "_restart_service", new=AsyncMock(return_value=True)) as restart,
        patch.object(monitor, "_increment_restart_count", new=AsyncMock()),
    ):
        state.celery_worker_process = proc
        await monitor.apply_service_status("celery", ServiceStatus.DEGRADED)
    restart.assert_awaited_once_with("celery")
    assert monitor.metrics["celery"].restart_count == 1


def test_start_celery_worker_default_loglevel_info() -> None:
    """Managed worker CLI defaults to --loglevel=info."""
    inspect = MagicMock()
    inspect.active.side_effect = [None, None, {}, {"worker@fresh": []}]
    inspect.registered.return_value = {"worker@fresh": ["showcase.generate_cover"]}
    control = MagicMock()
    control.inspect.return_value = inspect
    app = MagicMock()
    app.control = control
    app.tasks = {"showcase.generate_cover": object()}

    server_state = MagicMock()
    server_state.celery_worker_process = MagicMock(pid=99)
    server_state.celery_stdout_file = None
    server_state.celery_stderr_file = None

    def fake_getenv(key: str, default: str | None = None) -> str | None:
        if key == "CELERY_WORKER_LOGLEVEL":
            return None
        if key == "CELERY_MANAGED_BY_APP":
            return "false"
        return default

    with (
        patch.object(celery_manager, "celery_app", app),
        patch.object(celery_manager.time, "sleep"),
        patch.object(celery_manager, "launch_background_process") as launch,
        patch.object(celery_manager.os, "makedirs"),
        patch.object(celery_manager.os, "getenv", side_effect=fake_getenv),
        patch.object(celery_manager.sys, "platform", "linux"),
        patch.object(celery_manager.sys, "executable", "/usr/bin/python"),
        patch.object(celery_manager, "open_append_text", return_value=MagicMock()),
    ):
        celery_manager.start_celery_worker(server_state)

    launch.assert_called_once()
    cmd = launch.call_args.args[3]
    assert "--loglevel=info" in cmd
