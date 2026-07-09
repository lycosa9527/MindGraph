"""Document Summary lite ingest: extract once, store markdown, skip RAG indexing.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import DocumentBatch, KnowledgeDocument, KnowledgeSpace
from services.knowledge.doc_summary_storage import (
    build_storage_metadata,
    cache_extracted_text,
    clear_package_redis,
    delete_extracted_content,
    fetch_extracted_markdown_cached,
    set_package_status,
    store_extracted_markdown,
)
from services.knowledge.document_processor import DocumentProcessor
from services.utils.error_types import DATABASE_ERRORS, FILE_IO_ERRORS, REDIS_ERRORS
from services.utils.safe_upload import safe_upload_basename

logger = logging.getLogger(__name__)

DOC_SUMMARY_SOURCE = "doc_summary"
TEXT_SOURCE_FILE_TYPE = "text/markdown"
DOC_SUMMARY_MAX_FILE_BYTES = 20 * 1024 * 1024

_DOC_SUMMARY_INGEST_ERRORS: tuple[type[Exception], ...] = (
    ImportError,
    AttributeError,
    KeyError,
    TypeError,
    *DATABASE_ERRORS,
    *FILE_IO_ERRORS,
    *REDIS_ERRORS,
)


class DocSummaryIngestService:
    """Extract-only ingest for Document Summary packages."""

    def __init__(self, db: AsyncSession, user_id: int):
        self.db = db
        self.user_id = user_id
        self.processor = DocumentProcessor()

    async def get_package(self, package_id: int) -> Optional[DocumentBatch]:
        """Fetch a package owned by this user."""
        result = await self.db.execute(
            select(DocumentBatch).where(
                and_(
                    DocumentBatch.id == package_id,
                    DocumentBatch.user_id == self.user_id,
                )
            )
        )
        return result.scalars().first()

    def is_doc_summary_package(self, package: DocumentBatch) -> bool:
        """True when the package belongs to the canvas Document Summary flow."""
        return package.source == DOC_SUMMARY_SOURCE

    async def ingest_file(
        self,
        package_id: int,
        tmp_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
    ) -> KnowledgeDocument:
        """Extract text from a temp upload, store markdown to COS, discard original."""
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")
        if not self.is_doc_summary_package(package):
            raise ValueError("Package is not a Document Summary session")

        if file_size > DOC_SUMMARY_MAX_FILE_BYTES:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({DOC_SUMMARY_MAX_FILE_BYTES} bytes)")
        if not self.processor.is_supported(file_type):
            raise ValueError(f"Unsupported file type: {file_type}")

        safe_name = safe_upload_basename(file_name)
        await set_package_status(package_id, "processing")
        try:
            extracted = await asyncio.to_thread(
                self.processor.extract_text,
                tmp_path,
                file_type,
            )
            if not extracted or not extracted.strip():
                raise ValueError("No text could be extracted from the file")

            return await self._persist_extracted(
                package_id=package_id,
                markdown=extracted,
                source_filename=safe_name,
                source_mime=file_type,
                file_size=file_size,
                ingest_source="upload",
            )
        except _DOC_SUMMARY_INGEST_ERRORS:
            await set_package_status(package_id, "failed")
            raise
        finally:
            try:
                Path(tmp_path).unlink(missing_ok=True)
            except OSError:
                pass

    async def ingest_text(
        self,
        package_id: int,
        content: str,
        title: str,
        source_kind: str = "paste",
        page_url: Optional[str] = None,
        language: Optional[str] = None,
        extra_metadata: Optional[dict] = None,
    ) -> KnowledgeDocument:
        """Store pasted or fetched text as extracted markdown (no file parse)."""
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")
        if not self.is_doc_summary_package(package):
            raise ValueError("Package is not a Document Summary session")

        text = (content or "").strip()
        if not text:
            raise ValueError("Cannot ingest empty content")

        safe_title = safe_upload_basename(title or source_kind or "source")
        await set_package_status(package_id, "processing")
        try:
            return await self._persist_extracted(
                package_id=package_id,
                markdown=text,
                source_filename=f"{safe_title}.md",
                source_mime=TEXT_SOURCE_FILE_TYPE,
                file_size=len(text.encode("utf-8")),
                ingest_source=source_kind,
                page_url=page_url,
                language=language,
                extra_metadata=extra_metadata,
            )
        except _DOC_SUMMARY_INGEST_ERRORS:
            await set_package_status(package_id, "failed")
            raise

    async def fetch_package_markdown(self, package_id: int) -> Optional[str]:
        """Return extracted markdown for the single source in a doc_summary package."""
        documents = await self._package_documents(package_id)
        for document in documents:
            if document.status != "completed":
                continue
            text = await fetch_extracted_markdown_cached(package_id, document.doc_metadata)
            if text and text.strip():
                return text.strip()
        return None

    async def delete_package_source(self, document: KnowledgeDocument) -> None:
        """Remove extracted content and DB row for a doc_summary source."""
        await delete_extracted_content(document.doc_metadata)
        if document.batch_id is not None:
            await clear_package_redis(document.batch_id)
        await self.db.delete(document)
        await self.db.commit()

    async def _persist_extracted(
        self,
        *,
        package_id: int,
        markdown: str,
        source_filename: str,
        source_mime: str,
        file_size: int,
        ingest_source: str,
        page_url: Optional[str] = None,
        language: Optional[str] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> KnowledgeDocument:
        await self._replace_existing_sources(package_id)
        space = await self._ensure_space()

        document = KnowledgeDocument(
            space_id=space.id,
            file_name=source_filename,
            file_path="",
            file_type=source_mime,
            file_size=file_size,
            status="processing",
            batch_id=package_id,
            language=language,
            doc_metadata={"ingest_source": ingest_source},
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        await store_extracted_markdown(self.user_id, package_id, markdown)

        metadata = build_storage_metadata(
            user_id=self.user_id,
            package_id=package_id,
            markdown=markdown,
            source_filename=source_filename,
            source_mime=source_mime,
            ingest_source=ingest_source,
            page_url=page_url,
        )
        if extra_metadata:
            metadata.update(extra_metadata)
        document.doc_metadata = metadata
        document.status = "completed"
        document.processing_progress = "extracted"
        document.processing_progress_percent = 100
        document.error_message = None
        await self.db.commit()
        await self.db.refresh(document)

        await cache_extracted_text(package_id, markdown)
        await set_package_status(package_id, "ready")

        logger.info(
            "[DocSummary] Stored extract package=%s doc_id=%s chars=%s user=%s storage=%s",
            package_id,
            document.id,
            metadata.get("extract_char_count"),
            self.user_id,
            metadata.get("storage"),
        )
        return document

    async def _replace_existing_sources(self, package_id: int) -> None:
        existing = await self._package_documents(package_id)
        for document in existing:
            await delete_extracted_content(document.doc_metadata)
            await self.db.delete(document)
        if existing:
            await self.db.commit()
        await clear_package_redis(package_id)

    async def _package_documents(self, package_id: int) -> list[KnowledgeDocument]:
        result = await self.db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.batch_id == package_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def _ensure_space(self) -> KnowledgeSpace:
        result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.user_id == self.user_id))
        space = result.scalars().first()
        if space:
            return space
        space = KnowledgeSpace(user_id=self.user_id)
        self.db.add(space)
        await self.db.commit()
        await self.db.refresh(space)
        return space
