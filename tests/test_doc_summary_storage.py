"""Tests for Document Summary COS/local extracted-content storage."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from services.knowledge.doc_summary_storage import (
    STORAGE_LOCAL,
    build_cos_key,
    build_local_fallback_path,
    build_storage_metadata,
    cos_documents_enabled,
    delete_extracted_content_sync,
    fetch_extracted_markdown_sync,
    store_extracted_markdown_sync,
)


def test_build_cos_key_uses_documents_prefix() -> None:
    """COS object keys live under the configured documents prefix."""
    with patch("services.knowledge.doc_summary_storage.config") as mock_config:
        mock_config.COS_DOCUMENTS_PREFIX = "documents/mindgraph-test"
        key = build_cos_key(42, 7)
    assert key == "documents/mindgraph-test/user_42/pkg_7/extracted.md"


def test_local_store_and_fetch(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Local fallback writes markdown to disk and round-trips fetch/delete."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    with patch("services.knowledge.doc_summary_storage.cos_documents_enabled", return_value=False):
        info = store_extracted_markdown_sync(1, 2, "# Hello\n\nWorld")
    assert info["storage"] == STORAGE_LOCAL
    local_path = info["local_path"]
    meta = {"storage": STORAGE_LOCAL, "local_path": local_path}
    text = fetch_extracted_markdown_sync(meta)
    assert text == "# Hello\n\nWorld"
    delete_extracted_content_sync(meta)
    assert fetch_extracted_markdown_sync(meta) is None


def test_build_storage_metadata_local(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Local metadata marks doc_summary_lite and records extract size."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    with patch("services.knowledge.doc_summary_storage.cos_documents_enabled", return_value=False):
        meta = build_storage_metadata(
            user_id=5,
            package_id=9,
            markdown="Sample text",
            source_filename="notes.md",
            source_mime="text/markdown",
            ingest_source="paste",
        )
    assert meta["doc_summary_lite"] is True
    assert meta["storage"] == STORAGE_LOCAL
    assert meta["local_path"] == str(build_local_fallback_path(5, 9))
    assert meta["extract_char_count"] == len("Sample text")


def test_cos_disabled_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS uploads stay disabled when credentials are missing."""
    monkeypatch.setenv("COS_DOCUMENTS_ENABLED", "true")
    with patch("services.knowledge.doc_summary_storage.cos_credentials_configured", return_value=False):
        assert cos_documents_enabled() is False
