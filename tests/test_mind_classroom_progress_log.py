"""Mind Classroom poll / stage log helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from services.mind_classroom.canvas_tour_chunks import family_branch_label
from services.mind_classroom.progress_log import (
    POLL_HEARTBEAT_SEC,
    format_job_stage_line,
    format_poll_line,
    job_elapsed_seconds,
    poll_fingerprint,
    progress_branch_part,
    progress_phase,
    remember_poll,
    should_log_poll,
)


class _JobTimes:
    def __init__(self, started_at: datetime | None, created_at: datetime | None) -> None:
        self.started_at = started_at
        self.created_at = created_at


def test_progress_phase_and_branch() -> None:
    """Phase and branch fragments come from the manifesto progress dict."""
    progress = {"phase": "llm_waiting", "branch": 2, "branch_total": 5}
    assert progress_phase(progress) == "llm_waiting"
    assert progress_branch_part(progress) == "branch=2/5"
    assert progress_phase(None) == ""
    assert progress_branch_part({"phase": "queued"}) == ""


def test_format_poll_line_includes_stage() -> None:
    """Uvicorn poll lines name the current phase so GET is not a silent 200."""
    line = format_poll_line(
        "job-1",
        status="generating",
        progress={
            "phase": "llm_request",
            "branch": 1,
            "branch_total": 4,
            "branch_label": "光合作用",
            "in_flight": 4,
        },
        elapsed_s=42.2,
    )
    assert line.startswith("[MindClassroom] poll job=job-1")
    assert "status=generating" in line
    assert "phase=llm_request" in line
    assert "branch=1/4" in line
    assert "in_flight=4" in line
    assert "label=光合作用" in line
    assert "elapsed=42s" in line


def test_format_job_stage_line() -> None:
    """Worker lines spell out DashScope / spec stages."""
    line = format_job_stage_line(
        "job-1",
        "DashScope request sent model=qwen branch=1/3 chars=800",
        status="generating",
        phase="llm_request",
    )
    assert "[MindClassroom] job=job-1" in line
    assert "phase=llm_request" in line
    assert "DashScope request sent" in line


def test_poll_fingerprint_changes_with_phase() -> None:
    """Heartbeat dedupe keys off status + phase + branch + done + tts."""
    queued = poll_fingerprint("queued", {"phase": "queued"})
    waiting = poll_fingerprint("generating", {"phase": "llm_waiting", "branch": 1, "branch_total": 2})
    assert queued != waiting
    assert queued == poll_fingerprint("queued", {"phase": "queued"})
    streaming = poll_fingerprint(
        "generating",
        {"phase": "llm_streaming", "branch": 2, "branch_total": 4, "done": 1},
    )
    first_tts = poll_fingerprint(
        "generating",
        {"phase": "llm_streaming", "branch": 2, "branch_total": 4, "done": 1, "tts_ready": True},
    )
    assert streaming != first_tts


def test_should_log_poll_on_change_and_heartbeat() -> None:
    """Log the first poll, a phase change, and a 15s heartbeat."""
    job_id = "poll-dedupe-job"
    first = poll_fingerprint("queued", {"phase": "queued"})
    assert should_log_poll(job_id, first, now=100.0) is True
    remember_poll(job_id, first, now=100.0)
    assert should_log_poll(job_id, first, now=110.0) is False
    assert should_log_poll(job_id, first, now=100.0 + POLL_HEARTBEAT_SEC) is True
    next_fp = poll_fingerprint("generating", {"phase": "reading_spec"})
    assert should_log_poll(job_id, next_fp, now=112.0) is True


def test_job_elapsed_prefers_started_at() -> None:
    """Elapsed uses started_at when the worker has claimed the job."""
    created = datetime(2026, 8, 17, 15, 0, tzinfo=UTC)
    started = created + timedelta(seconds=8)
    with_start = job_elapsed_seconds(_JobTimes(started, created))
    created_only = job_elapsed_seconds(_JobTimes(None, created))
    assert with_start is not None
    assert created_only is not None
    assert with_start < created_only
    assert job_elapsed_seconds(_JobTimes(None, None)) is None


def test_family_branch_label_uses_trunk_text() -> None:
    """Per-branch logs show the trunk title, not a raw node dump."""
    assert family_branch_label([{"id": "b1", "text": "呼吸作用"}]) == "呼吸作用"
    assert family_branch_label([{"id": "only-id"}]) == "only-id"
    assert family_branch_label([]) == ""
