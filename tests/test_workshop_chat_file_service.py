"""Unit tests for workshop chat file path sanitization."""

import pytest

from services.features.workshop_chat.file_service import (
    _disk_path_for_stored_url,
    _safe_upload_basename,
    attachment_download_url,
)


def test_safe_upload_basename_strips_path_components() -> None:
    """Upload filenames are reduced to a safe basename."""
    assert _safe_upload_basename("../../etc/passwd") == "passwd"
    assert _safe_upload_basename("notes/report.pdf") == "report.pdf"


def test_safe_upload_basename_rejects_empty() -> None:
    """Empty or dot-only filenames are rejected."""
    with pytest.raises(ValueError, match="Invalid filename"):
        _safe_upload_basename("")
    with pytest.raises(ValueError, match="Invalid filename"):
        _safe_upload_basename("..")


def test_disk_path_for_stored_url_rejects_traversal() -> None:
    """Path traversal in a stored URL is rejected."""
    with pytest.raises(ValueError, match="Invalid attachment path"):
        _disk_path_for_stored_url("/static/chat/../../etc/passwd")


def test_disk_path_for_stored_url_rejects_non_chat_prefix() -> None:
    """Stored URLs outside the chat prefix are rejected."""
    with pytest.raises(ValueError, match="Invalid attachment path"):
        _disk_path_for_stored_url("/static/other/file.txt")


def test_attachment_download_url_uses_api_route() -> None:
    """Attachment URLs point at the authenticated download route."""
    assert attachment_download_url(42) == "/api/chat/attachments/42/download"
