"""Classroom job Redis/SSE event helpers."""

from __future__ import annotations

from types import SimpleNamespace

from services.mind_classroom.job_events import (
    TERMINAL_JOB_STATUSES,
    build_progress_payload,
    classroom_job_channel,
    decode_pubsub_data,
)
from services.mind_classroom.job_payload import job_event_dict


def test_classroom_job_channel_is_per_job() -> None:
    """Each job has its own pub/sub channel."""
    assert classroom_job_channel("job-a") == "mind_classroom:job:job-a"
    assert classroom_job_channel("job-a") != classroom_job_channel("job-b")


def test_progress_payload_wraps_job_snapshot() -> None:
    """SSE frames carry a typed progress envelope."""
    raw = build_progress_payload({"id": "job-1", "status": "generating"})
    assert '"type": "progress"' in raw
    assert '"id": "job-1"' in raw


def test_decode_pubsub_accepts_str_and_bytes() -> None:
    """Redis may yield str (decode_responses) or raw bytes."""
    assert decode_pubsub_data('{"type":"heartbeat"}') == '{"type":"heartbeat"}'
    assert decode_pubsub_data(b'{"type":"heartbeat"}') == '{"type":"heartbeat"}'
    assert decode_pubsub_data(None) is None


def test_job_event_dict_serializes_without_request() -> None:
    """Workers publish the same snapshot the SSE client consumes."""
    row = SimpleNamespace(
        id="job-9",
        status="generating",
        current_stage="llm_streaming",
        progress={"phase": "llm_streaming", "done": 1, "in_flight": 2},
        error_message=None,
        diagram_id="diag-1",
        settings={"mode": "canvas_tour", "tour_scope": "main_branch"},
        result_json={"steps": [{"id": "s1", "caption": "Hello"}], "partial": True},
        celery_task_id="task-1",
        created_at=None,
        updated_at=None,
    )
    payload = job_event_dict(row)
    assert payload["id"] == "job-9"
    assert payload["status"] == "generating"
    assert payload["result_json"]["partial"] is True
    assert payload["progress"]["in_flight"] == 2


def test_ready_is_terminal_for_sse() -> None:
    """The stream closes when the lecture is playable or failed."""
    assert "ready" in TERMINAL_JOB_STATUSES
    assert "partial" in TERMINAL_JOB_STATUSES
    assert "generating" not in TERMINAL_JOB_STATUSES
