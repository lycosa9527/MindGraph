"""Mind Classroom Celery / manifesto status log lines."""

from __future__ import annotations

import pytest

from services.mind_classroom.celery_log import (
    classroom_status_changed,
    format_classroom_celery_line,
    log_classroom_celery,
)


def test_classroom_status_changed_on_status_or_stage() -> None:
    """Log only when manifesto status or stage actually moved."""
    assert classroom_status_changed("queued", "queued", "planning", "planning")
    assert classroom_status_changed("planning", "planning", "planning", "outline")
    assert not classroom_status_changed("planning", "planning", "planning", "planning")
    assert not classroom_status_changed("generating", "generating", "generating", None)


def test_format_classroom_celery_line_includes_ids() -> None:
    """API and worker lines share one [MindClassroom] Celery prefix."""
    line = format_classroom_celery_line(
        "enqueue",
        job_id="job-1",
        celery_task_id="task-9",
        status="queued",
        detail="mode=canvas_tour task=mind_classroom.run_script",
    )
    assert line.startswith("[MindClassroom] Celery enqueue job=job-1")
    assert "task=task-9" in line
    assert "status=queued" in line
    assert "mode=canvas_tour" in line


def test_format_omits_stage_when_same_as_status() -> None:
    """Avoid repeating stage=ready when status is already ready."""
    line = format_classroom_celery_line(
        "status",
        job_id="job-1",
        status="ready",
        stage="ready",
    )
    assert "status=ready" in line
    assert "stage=" not in line


def test_log_classroom_celery_writes_info(caplog: pytest.LogCaptureFixture) -> None:
    """INFO logger name is services.mind_classroom so uvicorn shows it."""
    with caplog.at_level("INFO", logger="services.mind_classroom"):
        log_classroom_celery(
            "start",
            job_id="job-1",
            celery_task_id="task-9",
            detail="task=mind_classroom.run_script",
        )
    assert any("[MindClassroom] Celery start job=job-1" in rec.message for rec in caplog.records)
