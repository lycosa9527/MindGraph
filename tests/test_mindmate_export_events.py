"""Tests for MindMate export job event helpers."""

from __future__ import annotations

import json

from services.dify.export.job_events import (
    TERMINAL_JOB_STATUSES,
    build_control_payload,
    build_progress_payload,
    export_job_channel,
)


def test_export_job_channel_name() -> None:
    assert export_job_channel(42) == "mindmate_export:job:42"


def test_progress_payload_shape() -> None:
    raw = build_progress_payload({"id": 1, "status": "running", "progress_percent": 10})
    parsed = json.loads(raw)
    assert parsed["type"] == "progress"
    assert parsed["job"]["status"] == "running"


def test_control_payload_shape() -> None:
    raw = build_control_payload("pause")
    parsed = json.loads(raw)
    assert parsed == {"type": "control", "action": "pause"}


def test_terminal_statuses_include_completed() -> None:
    assert "completed" in TERMINAL_JOB_STATUSES
    assert "running" not in TERMINAL_JOB_STATUSES
