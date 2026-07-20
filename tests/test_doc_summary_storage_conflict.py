"""PG ↔ COS conflict handling for Document Summary extracts."""

from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from services.knowledge.doc_summary_limits import (
    DOC_SUMMARY_STORAGE_CONFLICT_CODE,
    DocSummaryStorageConflictError,
    storage_conflict_detail,
)


def _ingest_service_cls():
    """Import DocSummaryIngestService without KnowledgeSpaceService → LLM cycle."""
    sys.modules.setdefault("services.knowledge.knowledge_space_service", MagicMock())
    module = importlib.import_module("services.knowledge.doc_summary_ingest")
    return module.DocSummaryIngestService


@pytest.mark.asyncio
async def test_fetch_reconciles_missing_blob_and_raises_conflict() -> None:
    """Completed PG row with missing COS/local blob is cleared for the owner."""
    service_cls = _ingest_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    package = SimpleNamespace(id=5, source="doc_summary", user_id=7)
    document = SimpleNamespace(
        id=9,
        batch_id=5,
        status="completed",
        doc_metadata={
            "doc_summary_lite": True,
            "storage": "cos",
            "object_id": "abc123",
            "cos_key": "documents/mindgraph/abc123.md",
        },
    )
    service.get_package = AsyncMock(return_value=package)
    service.list_package_documents = AsyncMock(return_value=[document])
    service.reconcile_missing_extract = AsyncMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.fetch_extracted_markdown_cached",
            AsyncMock(return_value=None),
        )
        with pytest.raises(DocSummaryStorageConflictError) as exc_info:
            await service.fetch_package_markdown(5)

    assert exc_info.value.package_id == 5
    assert exc_info.value.object_id == "abc123"
    service.reconcile_missing_extract.assert_awaited_once_with(5, document)


@pytest.mark.asyncio
async def test_reconcile_missing_extract_deletes_cos_and_pg_row() -> None:
    """Owner-scoped reconcile deletes residual blob, Redis, and the broken row."""
    service_cls = _ingest_service_cls()
    db = MagicMock()
    db.delete = AsyncMock()
    db.commit = AsyncMock()
    service = service_cls(db, user_id=7)
    package = SimpleNamespace(id=5, source="doc_summary", user_id=7)
    document = SimpleNamespace(
        id=9,
        batch_id=5,
        status="completed",
        doc_metadata={
            "storage": "cos",
            "object_id": "abc123",
            "cos_key": "documents/mindgraph/abc123.md",
            "temp_job_dir": None,
        },
    )
    service.get_package = AsyncMock(return_value=package)

    with pytest.MonkeyPatch.context() as monkeypatch:
        delete_extracted = AsyncMock()
        clear_redis = AsyncMock()
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.delete_extracted_content",
            delete_extracted,
        )
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.clear_package_redis",
            clear_redis,
        )
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.remove_job_dir",
            MagicMock(),
        )
        await service.reconcile_missing_extract(5, document)

    delete_extracted.assert_awaited_once()
    clear_redis.assert_awaited_once_with(5)
    db.delete.assert_awaited_once_with(document)
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_reconcile_rejects_foreign_document_batch() -> None:
    """Documents from another package cannot be reconciled via this session."""
    service_cls = _ingest_service_cls()
    db = MagicMock()
    service = service_cls(db, user_id=7)
    service.get_package = AsyncMock(return_value=SimpleNamespace(id=5, source="doc_summary"))
    document = SimpleNamespace(id=9, batch_id=99, doc_metadata={})

    with pytest.raises(ValueError, match="does not belong"):
        await service.reconcile_missing_extract(5, document)


@pytest.mark.asyncio
async def test_persist_deletes_orphan_blob_when_commit_fails() -> None:
    """COS upload rolled back when Postgres commit fails after store."""
    service_cls = _ingest_service_cls()
    db = MagicMock()
    db.commit = AsyncMock(side_effect=RuntimeError("db down"))
    db.refresh = AsyncMock()
    space_result = MagicMock()
    space_result.scalars.return_value.first.return_value = SimpleNamespace(id=1)
    db.execute = AsyncMock(return_value=space_result)
    service = service_cls(db, user_id=7)
    existing = SimpleNamespace(
        id=1,
        batch_id=5,
        doc_metadata={},
        file_path="",
        status="processing",
        processing_progress=None,
        processing_progress_percent=0,
        error_message=None,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        store = AsyncMock(
            return_value={
                "storage": "cos",
                "object_id": "obj1",
                "cos_key": "documents/mindgraph/obj1.md",
            }
        )
        delete_extracted = AsyncMock()
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.store_extracted_markdown",
            store,
        )
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.delete_extracted_content",
            delete_extracted,
        )
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.build_storage_metadata",
            MagicMock(
                return_value={
                    "storage": "cos",
                    "object_id": "obj1",
                    "cos_key": "documents/mindgraph/obj1.md",
                    "extract_char_count": 5,
                }
            ),
        )
        monkeypatch.setattr(
            "services.knowledge.doc_summary_ingest.new_object_id",
            MagicMock(return_value="obj1"),
        )
        with pytest.raises(RuntimeError, match="db down"):
            await service.persist_extracted(
                package_id=5,
                markdown="hello",
                source_filename="a.md",
                source_mime="text/markdown",
                file_size=5,
                ingest_source="paste",
                existing_document=existing,
                skip_replace=True,
            )

    delete_extracted.assert_awaited_once()
    assert delete_extracted.await_args is not None
    deleted_meta = delete_extracted.await_args.args[0]
    assert deleted_meta["object_id"] == "obj1"
    assert deleted_meta["cos_key"] == "documents/mindgraph/obj1.md"


def test_storage_conflict_detail_code() -> None:
    """API detail uses the stable conflict code for FE notifications."""
    detail = storage_conflict_detail(package_id=3, object_id="x")
    assert detail["code"] == DOC_SUMMARY_STORAGE_CONFLICT_CODE
    assert detail["package_id"] == 3
    assert detail["object_id"] == "x"
