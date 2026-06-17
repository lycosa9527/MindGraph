"""Tests for organization storage estimate helpers."""

from utils.auth.org_storage_estimate import _column_bytes_fn


def test_column_bytes_fn_uses_pg_on_postgresql():
    """Test column bytes fn uses pg on postgresql."""
    assert _column_bytes_fn("postgresql").__name__ == "_pg_column_bytes"


def test_column_bytes_fn_falls_back_off_postgresql():
    """Test column bytes fn falls back off postgresql."""
    assert _column_bytes_fn("sqlite").__name__ == "_text_fallback_bytes"
