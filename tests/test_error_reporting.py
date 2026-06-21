"""Unit tests for error reporting helpers."""

from unittest.mock import AsyncMock, patch

from services.monitoring.error_record import ErrorRecord
from services.monitoring.error_reporting import (
    record_exception,
    record_exception_from_celery,
    record_failure,
)


def test_record_failure_builds_record_and_enqueues():
    with patch("services.monitoring.error_reporting.ErrorCollectorService.record") as mock_record:
        record_failure(
            source="llm",
            component="LLMService",
            message="chat failed",
            exception_type="ValueError",
            tags={"model": "qwen"},
            user_id=42,
        )
    mock_record.assert_called_once()
    record = mock_record.call_args[0][0]
    assert isinstance(record, ErrorRecord)
    assert record.source == "llm"
    assert record.component == "LLMService"
    assert record.message == "chat failed"
    assert record.user_id == 42
    assert record.tags == {"model": "qwen"}


def test_record_exception_includes_stacktrace():
    with patch("services.monitoring.error_reporting.ErrorCollectorService.record") as mock_record:
        try:
            raise ValueError("boom")
        except ValueError as exc:
            record_exception(
                source="application",
                component="test",
                exc=exc,
                severity="critical",
            )
    record = mock_record.call_args[0][0]
    assert record.exception_type == "ValueError"
    assert record.message == "boom"
    assert record.stacktrace is not None
    assert "ValueError: boom" in record.stacktrace


def test_record_exception_from_celery_runs_async_persist():
    exc = RuntimeError("celery fail")
    with patch(
        "services.monitoring.error_reporting.record_error_async",
        new_callable=AsyncMock,
        return_value=99,
    ) as mock_async:
        event_id = record_exception_from_celery(
            source="background",
            component="KnowledgeSpaceTask",
            exc=exc,
            tags={"document_id": 1},
        )
    assert event_id == 99
    mock_async.assert_awaited_once()
    record = mock_async.await_args[0][0]
    assert record.source == "background"
    assert record.component == "KnowledgeSpaceTask"
    assert record.tags == {"document_id": 1}


def test_record_failure_skips_when_collection_disabled():
    with patch("services.monitoring.error_reporting.error_collection_enabled", return_value=False):
        with patch("services.monitoring.error_reporting.ErrorCollectorService.record") as mock_record:
            record_failure(source="llm", component="x", message="msg")
    mock_record.assert_not_called()


def test_record_failure_normalizes_invalid_severity():
    with patch("services.monitoring.error_reporting.ErrorCollectorService.record") as mock_record:
        record_failure(
            source="application",
            component="x",
            message="msg",
            severity="not-a-level",
        )
    record = mock_record.call_args[0][0]
    assert record.severity == "error"
