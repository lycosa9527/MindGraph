"""Tests for Document Summary COS/local extracted-content storage."""

from __future__ import annotations

from pathlib import Path
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


def test_build_cos_key_is_uuid_based_not_user_id() -> None:
    """COS keys use opaque object ids so overlapping MG user ids cannot collide."""
    with patch("services.knowledge.doc_summary_storage.config") as mock_config:
        mock_config.COS_DOCUMENTS_PREFIX = "documents/mindgraph"
        key = build_cos_key("a1b2c3d4e5f6789012345678abcdef01")
    assert key == "documents/mindgraph/a1b2c3d4e5f6789012345678abcdef01.md"
    assert "user_" not in key


def test_local_store_and_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Local fallback writes markdown to disk and round-trips fetch/delete."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    with patch("services.knowledge.doc_summary_storage.cos_documents_enabled", return_value=False):
        info = store_extracted_markdown_sync("# Hello\n\nWorld", object_id="abc123")
    assert info["storage"] == STORAGE_LOCAL
    assert info["object_id"] == "abc123"
    local_path = info["local_path"]
    meta = {"storage": STORAGE_LOCAL, "local_path": local_path, "object_id": "abc123"}
    text = fetch_extracted_markdown_sync(meta)
    assert text == "# Hello\n\nWorld"
    delete_extracted_content_sync(meta)
    assert fetch_extracted_markdown_sync(meta) is None


def test_build_storage_metadata_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Local metadata marks doc_summary_lite and records extract size."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    with patch("services.knowledge.doc_summary_storage.cos_documents_enabled", return_value=False):
        meta = build_storage_metadata(
            object_id="obj99",
            markdown="Sample text",
            source_filename="notes.md",
            source_mime="text/markdown",
            ingest_source="paste",
        )
    assert meta["doc_summary_lite"] is True
    assert meta["storage"] == STORAGE_LOCAL
    assert meta["object_id"] == "obj99"
    assert meta["local_path"] == str(build_local_fallback_path("obj99"))
    assert meta["extract_char_count"] == len("Sample text")


def test_cos_disabled_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """COS uploads stay disabled when credentials are missing."""
    monkeypatch.setenv("COS_DOCUMENTS_ENABLED", "true")
    with patch("services.knowledge.doc_summary_storage.cos_credentials_configured", return_value=False):
        assert cos_documents_enabled() is False


def test_local_store_keeps_full_extracted_markdown_under_model_cap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extracted markdown under the model input cap is stored without 32k truncation."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    long_text = ("段落内容 " * 8_000).strip()  # well above the old 32_000 cap
    assert len(long_text) > 32_000
    with patch("services.knowledge.doc_summary_storage.cos_documents_enabled", return_value=False):
        info = store_extracted_markdown_sync(long_text, object_id="longdoc01")
        meta = build_storage_metadata(
            object_id="longdoc01",
            markdown=long_text,
            source_filename="book.md",
            source_mime="text/markdown",
            ingest_source="file",
        )
    assert meta["extract_char_count"] == len(long_text)
    loaded = fetch_extracted_markdown_sync(
        {"storage": STORAGE_LOCAL, "local_path": info["local_path"], "object_id": "longdoc01"}
    )
    assert loaded == long_text
