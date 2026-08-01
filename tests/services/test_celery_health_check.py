"""Process monitor Celery health: prefer managed PID; ping only when unmanaged."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.infrastructure.monitoring.process_monitor import (
    ServiceStatus,
    check_celery_worker_health,
)
from services.infrastructure.process import _celery_manager as celery_manager


@pytest.mark.asyncio
async def test_celery_health_skips_inspect_when_managed_process_alive() -> None:
    """App-managed worker: process poll is enough — no broker inspect spam."""
    proc = MagicMock()
    proc.poll.return_value = None
    app = MagicMock()

    status = await check_celery_worker_health(
        app=app,
        managed_process=proc,
        worker_needed=True,
    )

    assert status == ServiceStatus.HEALTHY
    app.control.inspect.assert_not_called()


@pytest.mark.asyncio
async def test_celery_health_unmanaged_uses_ping() -> None:
    """External workers: ping via broker, not inspect.active."""
    inspect = MagicMock()
    inspect.ping.return_value = {"worker@a": {"ok": "pong"}}
    control = MagicMock()
    control.inspect.return_value = inspect
    app = MagicMock()
    app.control = control

    with patch(
        "services.infrastructure.monitoring.process_monitor.asyncio.to_thread",
        new=AsyncMock(side_effect=lambda fn: fn()),
    ):
        status = await check_celery_worker_health(
            app=app,
            managed_process=None,
            worker_needed=True,
        )

    assert status == ServiceStatus.HEALTHY
    inspect.ping.assert_called_once()
    inspect.active.assert_not_called()


def test_start_celery_worker_default_loglevel_info() -> None:
    """Managed worker CLI defaults to --loglevel=info."""
    inspect = MagicMock()
    # Discovery: no workers → start; post-start ready check: worker present
    inspect.active.side_effect = [None, {"worker@fresh": []}]
    inspect.registered.return_value = None
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
