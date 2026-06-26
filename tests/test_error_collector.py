"""Unit tests for error collector fingerprinting and redaction."""

from services.monitoring.error_collector import (
    compute_fingerprint,
    redact_sensitive_text,
)


def test_compute_fingerprint_stable_for_same_input():
    """Identical inputs produce the same 32-character fingerprint."""
    first = compute_fingerprint(
        exception_type="ValueError",
        component="LLMService",
        message="chat failed",
        stacktrace='File "a.py", line 1\nValueError: chat failed',
    )
    second = compute_fingerprint(
        exception_type="ValueError",
        component="LLMService",
        message="chat failed",
        stacktrace='File "a.py", line 1\nValueError: chat failed',
    )
    assert first == second
    assert len(first) == 32


def test_compute_fingerprint_differs_by_component():
    """Fingerprints differ when the component name changes."""
    first = compute_fingerprint(
        exception_type="ValueError",
        component="LLMService",
        message="chat failed",
    )
    second = compute_fingerprint(
        exception_type="ValueError",
        component="OtherService",
        message="chat failed",
    )
    assert first != second


def test_redact_sensitive_text_masks_secrets():
    """Redaction masks bearer tokens, phone numbers, and api_key values."""
    raw = "Authorization: Bearer abc.def.ghi phone 13800138000 api_key=secret123"
    redacted = redact_sensitive_text(raw)
    assert "secret123" not in redacted
    assert "13800138000" not in redacted
    assert "[REDACTED]" in redacted
