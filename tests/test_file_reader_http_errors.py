"""HTTP error classification for the file-reader client."""

from __future__ import annotations

from file_reader.errors import ErrorCode, classify_http_error


def test_pairing_not_found_maps_to_pairing_failed() -> None:
    """Expired pairing codes should not look like a missing API."""
    err = classify_http_error(404, "Pairing code not found or expired")
    assert err.code == ErrorCode.PAIRING_FAILED


def test_pairing_already_used_maps_to_pairing_failed() -> None:
    """Single-use pairing conflicts map to pairing_failed."""
    err = classify_http_error(409, "Pairing code already used")
    assert err.code == ErrorCode.PAIRING_FAILED


def test_validation_error_maps_to_upload_failed() -> None:
    """422 validation errors during ingest map to upload_failed."""
    err = classify_http_error(422, "Unsupported chat platform")
    assert err.code == ErrorCode.UPLOAD_FAILED
