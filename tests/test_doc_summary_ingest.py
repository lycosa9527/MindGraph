"""Tests for Document Summary lite ingest service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.knowledge.doc_summary_ingest import DocSummaryIngestService, _run_file_extract_job


def _package() -> SimpleNamespace:
    """Build a minimal doc_summary package stub for ingest tests."""
    return SimpleNamespace(id=9, user_id=1, source="doc_summary", name="Test")


@pytest.mark.asyncio
async def test_ingest_text_persists_completed_document() -> None:
    """Pasted text delegates to persist_extracted and returns the completed document."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.delete = MagicMock()
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=_package())))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=SimpleNamespace(id=1))))),
        ]
    )

    service = DocSummaryIngestService(db, user_id=1)
    with (
        patch.object(service, "persist_extracted", new_callable=AsyncMock) as persist,
        patch("services.knowledge.doc_summary_ingest.set_package_status", new_callable=AsyncMock),
    ):
        doc = SimpleNamespace(id=55, status="completed")
        persist.return_value = doc
        result = await service.ingest_text(9, "Hello world", title="Note")
    assert result is doc
    persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_file_schedules_background_job(tmp_path: Path) -> None:
    """File ingest copies into doc_summary_tmp and schedules async extract."""
    upload = tmp_path / "router-temp.bin"
    upload.write_bytes(b"hello-pdf")
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    pkg = _package()
    space = SimpleNamespace(id=3)
    db.execute = AsyncMock(
        side_effect=[
            MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=pkg)))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=space)))),
        ]
    )

    created: dict[str, object] = {}

    def _capture_add(obj: object) -> None:
        created["doc"] = obj
        setattr(obj, "id", 77)

    db.add = MagicMock(side_effect=_capture_add)

    service = DocSummaryIngestService(db, user_id=1)
    job_dir = tmp_path / "job"
    job_file = job_dir / "x.pdf"
    job_dir.mkdir()
    job_file.write_bytes(b"hello-pdf")

    def _close_scheduled(coro: object, **_kwargs: object) -> MagicMock:
        close = getattr(coro, "close", None)
        if callable(close):
            close()
        return MagicMock()

    with (
        patch("services.knowledge.doc_summary_ingest.write_upload_temp", return_value=(job_dir, job_file)),
        patch("services.knowledge.doc_summary_ingest.set_package_extract_progress", new_callable=AsyncMock),
        patch("services.knowledge.doc_summary_ingest.release_open_transaction", new_callable=AsyncMock),
        patch(
            "services.knowledge.doc_summary_ingest.asyncio.create_task",
            side_effect=_close_scheduled,
        ) as create_task,
        patch("services.knowledge.doc_summary_ingest.clear_package_redis", new_callable=AsyncMock),
        patch("services.knowledge.doc_summary_ingest.delete_extracted_content", new_callable=AsyncMock),
    ):
        result = await service.ingest_file(9, str(upload), "x.pdf", "application/pdf", 9)

    assert result.status == "processing"
    assert result.processing_progress == "starting"
    assert create_task.called
    assert not upload.exists()


@pytest.mark.asyncio
async def test_ingest_file_rejects_non_doc_summary_package() -> None:
    """Upload ingest rejects packages that are not doc_summary source."""
    db = AsyncMock()
    pkg = SimpleNamespace(id=9, user_id=1, source="canvas", name="Other")
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=pkg))))
    )
    service = DocSummaryIngestService(db, user_id=1)
    with pytest.raises(ValueError, match="not a Document Summary"):
        await service.ingest_file(9, "/tmp/x.pdf", "x.pdf", "application/pdf", 100)


@pytest.mark.asyncio
async def test_run_file_extract_job_cleans_temp_on_success(tmp_path: Path) -> None:
    """Background job stores markdown and removes the temp job directory."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    source = job_dir / "note.txt"
    source.write_text("hello extracted", encoding="utf-8")

    document = SimpleNamespace(
        id=12,
        status="processing",
        processing_progress="starting",
        processing_progress_percent=5,
        error_message=None,
        doc_metadata={"temp_job_dir": str(job_dir)},
        file_path="",
        file_name="note.txt",
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=document)
    db.refresh = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=db)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("services.knowledge.doc_summary_ingest.user_rls_session", return_value=session_cm),
        patch.object(DocSummaryIngestService, "persist_extracted", new_callable=AsyncMock) as persist,
        patch("services.knowledge.doc_summary_ingest.set_package_extract_progress", new_callable=AsyncMock),
        patch("services.knowledge.doc_summary_ingest.release_open_transaction", new_callable=AsyncMock),
        patch("services.knowledge.doc_summary_ingest.remove_job_dir") as remove_job,
    ):
        persist.return_value = document
        await _run_file_extract_job(
            user_id=1,
            package_id=9,
            document_id=12,
            source_path=str(source),
            job_dir=str(job_dir),
            file_type="text/plain",
            source_filename="note.txt",
            file_size=15,
        )

    persist.assert_awaited_once()
    remove_job.assert_called_once_with(str(job_dir))


@pytest.mark.asyncio
async def test_run_file_extract_job_cleans_temp_on_failure(tmp_path: Path) -> None:
    """Failed extract still deletes temporary originals."""
    job_dir = tmp_path / "job"
    job_dir.mkdir()
    source = job_dir / "bad.pdf"
    source.write_bytes(b"%PDF-1.4")

    document = SimpleNamespace(
        id=12,
        status="processing",
        processing_progress="starting",
        processing_progress_percent=5,
        error_message=None,
        doc_metadata={"temp_job_dir": str(job_dir)},
        file_path="",
        file_name="bad.pdf",
    )

    db = AsyncMock()
    db.commit = AsyncMock()
    db.get = AsyncMock(return_value=document)

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=db)
    session_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("services.knowledge.doc_summary_ingest.user_rls_session", return_value=session_cm),
        patch(
            "services.knowledge.doc_summary_ingest.DocumentProcessor.extract_text",
            side_effect=ValueError("boom"),
        ),
        patch("services.knowledge.doc_summary_ingest.set_package_extract_progress", new_callable=AsyncMock),
        patch("services.knowledge.doc_summary_ingest.release_open_transaction", new_callable=AsyncMock),
        patch("services.knowledge.doc_summary_ingest.remove_job_dir") as remove_job,
    ):
        await _run_file_extract_job(
            user_id=1,
            package_id=9,
            document_id=12,
            source_path=str(source),
            job_dir=str(job_dir),
            file_type="application/pdf",
            source_filename="bad.pdf",
            file_size=8,
        )

    assert document.status == "failed"
    remove_job.assert_called_once_with(str(job_dir))
