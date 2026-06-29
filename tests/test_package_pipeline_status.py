"""Tests for package RAG/wiki pipeline status helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from models.domain.knowledge_space import KnowledgeDocument

from services.knowledge import package_pipeline_status as status


def test_derive_wiki_status_disabled(monkeypatch):
    """Wiki status is disabled when compile flag is off."""
    monkeypatch.setattr(
        type(status.config),
        "FILE_CENTER_WIKI_COMPILE",
        property(lambda _self: False),
    )
    assert status.derive_wiki_status(completed_count=2, wiki_page_count=0) == status.WIKI_STATUS_DISABLED


def test_derive_wiki_status_ready(monkeypatch):
    """Wiki status is ready when pages exist."""
    monkeypatch.setattr(
        type(status.config),
        "FILE_CENTER_WIKI_COMPILE",
        property(lambda _self: True),
    )
    assert status.derive_wiki_status(completed_count=1, wiki_page_count=2) == status.WIKI_STATUS_READY


def test_derive_wiki_status_pending(monkeypatch):
    """Indexed packages without wiki pages are pending compile."""
    monkeypatch.setattr(
        type(status.config),
        "FILE_CENTER_WIKI_COMPILE",
        property(lambda _self: True),
    )
    assert status.derive_wiki_status(completed_count=1, wiki_page_count=0) == status.WIKI_STATUS_PENDING


def test_derive_wiki_status_none(monkeypatch):
    """Packages without indexed sources have no wiki work yet."""
    monkeypatch.setattr(
        type(status.config),
        "FILE_CENTER_WIKI_COMPILE",
        property(lambda _self: True),
    )
    assert status.derive_wiki_status(completed_count=0, wiki_page_count=0) == status.WIKI_STATUS_NONE


def test_derive_document_rag_status_maps_processing_and_failed():
    """Document RAG badges mirror source processing lifecycle."""
    assert status.derive_document_rag_status("pending") == status.RAG_STATUS_NOT_YET
    assert status.derive_document_rag_status("processing") == status.RAG_STATUS_PROCESSING
    assert status.derive_document_rag_status("completed") == status.RAG_STATUS_COMPLETE
    assert status.derive_document_rag_status("failed") == status.RAG_STATUS_FAILED


def test_derive_document_wiki_statuses(monkeypatch, tmp_path):
    """Wiki badges track compile coverage per indexed source."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    monkeypatch.setattr(
        type(status.config),
        "FILE_CENTER_WIKI_COMPILE",
        property(lambda _self: True),
    )
    wiki_root = tmp_path / "user_1" / "packages" / "3" / "wiki"
    wiki_root.mkdir(parents=True)
    (wiki_root / "_index.json").write_text(
        '{"pages": [{"slug": "overview", "source_document_ids": [10]}]}',
        encoding="utf-8",
    )

    pending_doc = SimpleNamespace(id=9, status="pending")
    compiled_doc = SimpleNamespace(id=10, status="completed")
    waiting_doc = SimpleNamespace(id=11, status="completed")

    statuses = status.derive_document_wiki_statuses(
        1,
        3,
        cast(
            list[KnowledgeDocument],
            [pending_doc, compiled_doc, waiting_doc],
        ),
    )
    assert statuses[9] == status.WIKI_STATUS_NOT_YET
    assert statuses[10] == status.WIKI_STATUS_COMPLETE
    assert statuses[11] == status.WIKI_STATUS_PENDING
