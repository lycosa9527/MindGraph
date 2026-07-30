"""Unit tests for Celery stale-worker detection helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from services.infrastructure.process import _celery_manager as celery_manager


def test_workers_missing_required_tasks_detects_stale() -> None:
    """Flag workers that do not register every app task name."""
    with patch.object(
        celery_manager,
        "required_app_task_names",
        return_value={"showcase.generate_cover", "knowledge.ingest"},
    ):
        stale = celery_manager.workers_missing_required_tasks(
            {
                "worker@old": ["knowledge.ingest"],
                "worker@new": ["showcase.generate_cover", "knowledge.ingest"],
            }
        )
    assert stale == ["worker@old"]


def test_workers_missing_required_tasks_all_current() -> None:
    """Accept workers that register the full required task set."""
    with patch.object(
        celery_manager,
        "required_app_task_names",
        return_value={"showcase.generate_cover"},
    ):
        stale = celery_manager.workers_missing_required_tasks({"worker@a": ["showcase.generate_cover", "other.task"]})
    assert not stale


def test_start_celery_worker_uses_current_workers() -> None:
    """Skip startup when existing workers already register required tasks."""
    inspect = MagicMock()
    inspect.active.return_value = {"worker@ok": []}
    inspect.registered.return_value = {
        "worker@ok": ["showcase.generate_cover", "knowledge.ingest"],
    }

    control = MagicMock()
    control.inspect.return_value = inspect

    app = MagicMock()
    app.control = control
    app.tasks = {
        "showcase.generate_cover": object(),
        "knowledge.ingest": object(),
        "celery.backend_cleanup": object(),
    }

    with (
        patch.object(celery_manager, "celery_app", app),
        patch.object(celery_manager, "launch_background_process") as launch,
    ):
        result = celery_manager.start_celery_worker(MagicMock())

    assert result is None
    launch.assert_not_called()
    control.broadcast.assert_not_called()


def test_start_celery_worker_shuts_down_stale_then_relaunches() -> None:
    """Existing workers missing app tasks must be shut down before relaunch."""
    inspect = MagicMock()
    inspect.registered.return_value = {"worker@old": ["knowledge.ingest"]}

    control = MagicMock()
    control.inspect.return_value = inspect
    control.broadcast.return_value = None

    app = MagicMock()
    app.control = control
    app.tasks = {
        "showcase.generate_cover": object(),
        "knowledge.ingest": object(),
        "celery.backend_cleanup": object(),
    }

    server_state = MagicMock()
    server_state.celery_worker_process = MagicMock(pid=4242)
    server_state.celery_stdout_file = None
    server_state.celery_stderr_file = None

    with (
        patch.object(celery_manager, "celery_app", app),
        patch.object(celery_manager, "shutdown_stale_celery_workers") as shutdown,
        patch.object(celery_manager.time, "sleep"),
        patch.object(celery_manager, "launch_background_process") as launch,
        patch.object(celery_manager.os, "makedirs"),
        patch.object(celery_manager.os, "getenv", return_value="false"),
        patch.object(celery_manager.sys, "platform", "linux"),
        patch.object(celery_manager.sys, "executable", "/usr/bin/python"),
    ):
        inspect.active.side_effect = [
            {"worker@old": []},  # attempt 0 discovery
            {},  # attempt 1 after shutdown — none left
            {"worker@fresh": []},  # post-start ready check
        ]
        result = celery_manager.start_celery_worker(server_state)

    shutdown.assert_called_once_with(["worker@old"])
    launch.assert_called_once()
    assert result is server_state.celery_worker_process


def test_start_celery_worker_keeps_healthy_peers_after_stale_shutdown() -> None:
    """After killing stale workers, reuse remaining peers that register required tasks."""
    inspect = MagicMock()
    control = MagicMock()
    control.inspect.return_value = inspect

    app = MagicMock()
    app.control = control
    app.tasks = {
        "showcase.generate_cover": object(),
        "knowledge.ingest": object(),
        "celery.backend_cleanup": object(),
    }

    with (
        patch.object(celery_manager, "celery_app", app),
        patch.object(celery_manager, "shutdown_stale_celery_workers") as shutdown,
        patch.object(celery_manager.time, "sleep"),
        patch.object(celery_manager, "launch_background_process") as launch,
    ):
        inspect.active.side_effect = [
            {"worker@old": [], "worker@ok": []},
            {"worker@ok": []},
        ]
        inspect.registered.side_effect = [
            {
                "worker@old": ["knowledge.ingest"],
                "worker@ok": ["showcase.generate_cover", "knowledge.ingest"],
            },
            {
                "worker@ok": ["showcase.generate_cover", "knowledge.ingest"],
            },
        ]
        result = celery_manager.start_celery_worker(MagicMock())

    shutdown.assert_called_once_with(["worker@old"])
    launch.assert_not_called()
    assert result is None


def test_shutdown_stale_targets_only_named_workers() -> None:
    """Never broadcast shutdown to the whole cluster — only stale destinations."""
    control = MagicMock()
    app = MagicMock()
    app.control = control
    inspect = MagicMock()
    inspect.active.return_value = {}
    control.inspect.return_value = inspect

    with (
        patch.object(celery_manager, "celery_app", app),
        patch.object(celery_manager.time, "sleep"),
    ):
        celery_manager.shutdown_stale_celery_workers(["worker@old"])

    control.broadcast.assert_called_once_with(
        "shutdown",
        destination=["worker@old"],
    )
