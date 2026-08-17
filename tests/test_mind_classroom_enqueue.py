"""Mind Classroom enqueue reuse and stuck-queue dispatch."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.mind_classroom.enqueue import ClassroomJobsBusy
from services.mind_classroom.queue_dispatch import (
    KICK_AFTER_SECONDS,
    QUEUED_GIVE_UP_SECONDS,
    queued_watch_action,
    task_name_for_settings,
    workers_register_task,
)


def test_find_reusable_includes_in_flight_jobs() -> None:
    """Closing the modal must be able to reattach to a still-queued job."""
    text = Path("repositories/mind_classroom_repo.py").read_text(encoding="utf-8")
    assert '_REUSABLE_STATUSES = ("ready", "partial", "queued", "planning", "generating")' in text
    assert "MindClassroomJob.status.in_(_REUSABLE_STATUSES)" in text
    assert "async def list_active_jobs" in text
    routes = Path("routers/features/mind_classroom/routes.py").read_text(encoding="utf-8")
    assert "_STALE_MINUTES = 15" in routes
    assert (
        "publish_classroom_job_snapshot(job_id)"
        in routes.split("async def _sweep_stale")[1].split("async def _refresh_queued_job")[0]
    )
    body = text.split("async def find_reusable")[1].split("async def list_jobs_for_diagram")[0]
    assert "if row.status in _ACTIVE_STATUSES:" in body
    assert "classroom_ready_job_reusable" in body
    assert "MindClassroomJob.spec_hash ==" not in body


def test_busy_error_exposes_blocking_job_id() -> None:
    """A 429 names the other in-flight job so the user can cancel it."""
    exc = ClassroomJobsBusy(1, 1, "job-busy")
    assert exc.job_id == "job-busy"
    assert "1/1" in str(exc)


def test_queued_watch_action_waits_then_kicks_then_fails() -> None:
    """Jobs that never leave queued are re-dispatched, then failed."""
    created = datetime(2026, 8, 16, 13, 0, tzinfo=UTC)
    assert queued_watch_action(created, created, now=created + timedelta(seconds=5)) == "wait"
    assert (
        queued_watch_action(
            created,
            created,
            now=created + timedelta(seconds=KICK_AFTER_SECONDS),
        )
        == "kick"
    )
    assert (
        queued_watch_action(
            created,
            created + timedelta(seconds=30),
            now=created + timedelta(seconds=QUEUED_GIVE_UP_SECONDS),
        )
        == "fail"
    )


def test_task_name_for_settings_splits_script_and_slides() -> None:
    """Canvas tour and slide deck stay on separate Celery task names."""
    assert task_name_for_settings({"mode": "canvas_tour"}) == "mind_classroom.run_script"
    assert task_name_for_settings({"mode": "slide_deck"}) == "mind_classroom.run_slides"
    assert task_name_for_settings(None) == "mind_classroom.run_script"


def test_workers_register_task_false_when_inspect_omits_classroom() -> None:
    """Fail fast when every worker is missing the classroom task."""
    inspect = MagicMock()
    inspect.registered.return_value = {"worker@old": ["showcase.generate_cover"]}
    app = MagicMock()
    app.control.inspect.return_value = inspect
    with patch("services.mind_classroom.queue_dispatch.celery_app", app):
        assert workers_register_task("mind_classroom.run_script") is False
