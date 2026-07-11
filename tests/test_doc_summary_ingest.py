"""Tests for Document Summary lite ingest service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.knowledge.doc_summary_ingest import DocSummaryIngestService


def _package() -> SimpleNamespace:
    """Build a minimal doc_summary package stub for ingest tests."""
    return SimpleNamespace(id=9, user_id=1, source="doc_summary", name="Test")


@pytest.mark.asyncio
async def test_ingest_text_persists_completed_document() -> None:
    """Pasted text delegates to _persist_extracted and returns the completed document."""
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
        patch.object(service, "_persist_extracted", new_callable=AsyncMock) as persist,
        patch("services.knowledge.doc_summary_ingest.set_package_status", new_callable=AsyncMock),
    ):
        doc = SimpleNamespace(id=55, status="completed")
        persist.return_value = doc
        result = await service.ingest_text(9, "Hello world", title="Note")
    assert result is doc
    persist.assert_awaited_once()


@pytest.mark.asyncio
async def test_ingest_file_releases_db_before_ocr() -> None:
    """Slow OCR must not hold the request-scoped SQLAlchemy transaction open."""
    db = AsyncMock()
    db.commit = AsyncMock()
    pkg = _package()
    db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=pkg))))
    )

    service = DocSummaryIngestService(db, user_id=1)
    release = AsyncMock()
    with (
        patch("services.knowledge.doc_summary_ingest.release_open_transaction", release),
        patch.object(service.processor, "extract_text", return_value="extracted text"),
        patch.object(service, "_persist_extracted", new_callable=AsyncMock) as persist,
        patch("services.knowledge.doc_summary_ingest.set_package_status", new_callable=AsyncMock),
        patch("pathlib.Path.unlink"),
    ):
        persist.return_value = SimpleNamespace(id=12, status="completed")
        await service.ingest_file(9, "/tmp/x.png", "x.png", "image/png", 128)
    release.assert_awaited_once_with(db)


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
