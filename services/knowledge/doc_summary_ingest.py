"""Document Summary lite ingest: extract once, store markdown, skip RAG indexing.

File uploads run asynchronously with staged progress so the UI can poll.
Paste/web/chat stay synchronous. Original binaries live only under
``doc_summary_tmp`` and are deleted after extract succeeds or fails.

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
from services.knowledge.doc_summary_limits import (
    DOC_SUMMARY_MAX_FILE_BYTES,
    DocSummaryContentTooLongError,
    DocSummaryStorageConflictError,
    content_exceeds_model_input,
)
from services.knowledge.doc_summary_storage import (
    build_storage_metadata,
    cache_extracted_text,
    clear_package_redis,
    delete_extracted_content,
    fetch_extracted_markdown_cached,
    new_object_id,
    set_package_extract_progress,
    set_package_status,
    store_extracted_markdown,
)
from services.knowledge.doc_summary_temp import remove_job_dir, write_upload_temp
from services.knowledge.document_processor import DocumentProcessor
from services.knowledge.legacy_office_convert import convert_legacy_office, is_legacy_office_mime
from services.redis.redis_distributed_lock import DistributedLock
from services.utils.error_types import DATABASE_ERRORS, FILE_IO_ERRORS, REDIS_ERRORS
from services.utils.safe_upload import safe_upload_basename
from utils.db.session_open import release_open_transaction, user_rls_session

logger = logging.getLogger(__name__)

DOC_SUMMARY_SOURCE = "doc_summary"
TEXT_SOURCE_FILE_TYPE = "text/markdown"

_STAGE_PERCENT = {
    "starting": 5,
    "converting": 20,
    "extracting": 45,
    "ocr": 55,
    "transcribing": 55,
    "storing": 85,
    "completed": 100,
    "failed": 0,
}

_DOC_SUMMARY_INGEST_ERRORS: tuple[type[Exception], ...] = (
    ImportError,
    AttributeError,
    KeyError,
    TypeError,
    ValueError,
    RuntimeError,
    *DATABASE_ERRORS,
    *FILE_IO_ERRORS,
    *REDIS_ERRORS,
)

_IMAGE_MIMES = frozenset({"image/jpeg", "image/jpg", "image/png", "image/webp"})
_AUDIO_MIME_PREFIX = "audio/"


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

    async def _begin_exclusive_ingest(self, package_id: int) -> DistributedLock:
        """Acquire a short package lock and reject a second concurrent extract."""
        lock = DistributedLock(
            resource=f"doc_summary:ingest:{package_id}",
            ttl=120,
            max_retries=1,
            retry_base_delay=0.05,
        )
        acquired = await lock.acquire()
        if not acquired:
            raise ValueError("Document Summary extract already in progress")
        ready = False
        try:
            documents = await self._package_documents(package_id)
            if any(document.status == "processing" for document in documents):
                raise ValueError("Document Summary extract already in progress")
            ready = True
            return lock
        finally:
            if not ready:
                await lock.release()

    async def ingest_file(
        self,
        package_id: int,
        tmp_path: str,
        file_name: str,
        file_type: str,
        file_size: int,
    ) -> KnowledgeDocument:
        """Accept a temp upload, start async extract, return processing document.

        ``tmp_path`` is the router NamedTemporaryFile; bytes are copied into
        ``doc_summary_tmp`` and the router temp is deleted here.
        """
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
        source_path = Path(tmp_path)
        try:
            content = source_path.read_bytes()
        except FILE_IO_ERRORS as exc:
            raise ValueError(f"Failed to read upload: {exc}") from exc
        finally:
            try:
                source_path.unlink(missing_ok=True)
            except OSError:
                pass

        job_dir, job_file = write_upload_temp(
            user_id=self.user_id,
            package_id=package_id,
            file_name=safe_name,
            content=content,
        )

        lock = await self._begin_exclusive_ingest(package_id)
        try:
            await self._replace_existing_sources(package_id)
            space = await self._ensure_space()
            document = KnowledgeDocument(
                space_id=space.id,
                file_name=safe_name,
                file_path="",
                file_type=file_type,
                file_size=file_size,
                status="processing",
                processing_progress="starting",
                processing_progress_percent=_STAGE_PERCENT["starting"],
                batch_id=package_id,
                doc_metadata={
                    "ingest_source": "upload",
                    "temp_job_dir": str(job_dir),
                    "temp_source_path": str(job_file),
                },
            )
            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)
        finally:
            await lock.release()

        await set_package_extract_progress(package_id, "processing", "starting", _STAGE_PERCENT["starting"])
        await release_open_transaction(self.db)

        asyncio.create_task(
            _run_file_extract_job(
                user_id=self.user_id,
                package_id=package_id,
                document_id=document.id,
                source_path=str(job_file),
                job_dir=str(job_dir),
                file_type=file_type,
                source_filename=safe_name,
                file_size=file_size,
            ),
            name=f"doc_summary_extract:{package_id}:{document.id}",
        )
        return document

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
        lock = await self._begin_exclusive_ingest(package_id)
        try:
            await set_package_status(package_id, "processing")
            return await self.persist_extracted(
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
        finally:
            await lock.release()

    async def fetch_package_markdown(self, package_id: int) -> Optional[str]:
        """Return extracted markdown for the owned doc_summary package.

        When Postgres marks a source completed but the COS/local blob is missing,
        reconcile (delete residual blob + PG row) and raise
        :class:`DocSummaryStorageConflictError` so callers can notify the user.
        """
        package = await self.get_package(package_id)
        if not package:
            raise ValueError(f"Package {package_id} not found or access denied")
        if not self.is_doc_summary_package(package):
            raise ValueError("Package is not a Document Summary session")

        documents = await self._package_documents(package_id)
        for document in documents:
            if document.status != "completed":
                continue
            meta = document.doc_metadata or {}
            text = await fetch_extracted_markdown_cached(package_id, meta)
            if text and text.strip():
                return text.strip()
            if self._metadata_claims_extract_blob(meta):
                await self.reconcile_missing_extract(package_id, document)
                raise DocSummaryStorageConflictError(
                    package_id=package_id,
                    object_id=str(meta.get("object_id") or "") or None,
                )
        return None

    @staticmethod
    def _metadata_claims_extract_blob(meta: dict) -> bool:
        """True when PG metadata asserts a durable COS/local extract exists."""
        return bool(
            meta.get("object_id") or meta.get("cos_key") or meta.get("local_path") or meta.get("doc_summary_lite")
        )

    async def reconcile_missing_extract(
        self,
        package_id: int,
        document: KnowledgeDocument,
    ) -> None:
        """Owner-scoped cleanup when PG and COS/local storage disagree.

        Deletes any residual COS/local object, clears Redis, and removes the
        broken document row so the session returns to an empty upload state.
        """
        package = await self.get_package(package_id)
        if not package or not self.is_doc_summary_package(package):
            raise ValueError("Package is not a Document Summary session")
        if document.batch_id != package_id:
            raise ValueError("Document does not belong to this Document Summary package")

        meta = document.doc_metadata or {}
        logger.warning(
            "[DocSummary] PG/COS mismatch — clearing extract package=%s doc=%s object_id=%s user=%s",
            package_id,
            document.id,
            meta.get("object_id"),
            self.user_id,
        )
        remove_job_dir(meta.get("temp_job_dir"))
        await delete_extracted_content(meta)
        await clear_package_redis(package_id)
        await self.db.delete(document)
        await self.db.commit()

    async def delete_package_source(self, document: KnowledgeDocument) -> None:
        """Remove extracted content and DB row for a doc_summary source."""
        meta = document.doc_metadata or {}
        remove_job_dir(meta.get("temp_job_dir"))
        await delete_extracted_content(document.doc_metadata)
        if document.batch_id is not None:
            await clear_package_redis(document.batch_id)
        await self.db.delete(document)
        await self.db.commit()

    async def persist_extracted(
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
        existing_document: Optional[KnowledgeDocument] = None,
        skip_replace: bool = False,
    ) -> KnowledgeDocument:
        """Store extracted markdown to COS and mark the package source completed."""
        text = markdown.strip()
        if not text:
            raise ValueError("Extracted content is empty")
        if content_exceeds_model_input(len(text)):
            raise DocSummaryContentTooLongError(len(text))

        if not skip_replace:
            await self._replace_existing_sources(package_id)
        space = await self._ensure_space()

        if existing_document is None:
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
        else:
            document = existing_document

        object_id = new_object_id()
        storage_info = await store_extracted_markdown(text, object_id=object_id)
        try:
            metadata = build_storage_metadata(
                object_id=object_id,
                markdown=text,
                source_filename=source_filename,
                source_mime=source_mime,
                ingest_source=ingest_source,
                page_url=page_url,
            )
            metadata.update(storage_info)
            if extra_metadata:
                metadata.update(extra_metadata)
            # Never keep temp paths on the durable metadata blob.
            metadata.pop("temp_job_dir", None)
            metadata.pop("temp_source_path", None)
            document.doc_metadata = metadata
            document.file_path = ""
            document.status = "completed"
            document.processing_progress = "completed"
            document.processing_progress_percent = 100
            document.error_message = None
            await self.db.commit()
            await self.db.refresh(document)
        except _DOC_SUMMARY_INGEST_ERRORS:
            # COS/local was written before PG commit — delete orphan blob.
            await delete_extracted_content(
                {
                    "storage": storage_info.get("storage"),
                    "object_id": storage_info.get("object_id"),
                    "cos_key": storage_info.get("cos_key"),
                    "local_path": storage_info.get("local_path"),
                }
            )
            raise

        await cache_extracted_text(package_id, text)
        await set_package_extract_progress(package_id, "ready", "completed", 100)

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
            meta = document.doc_metadata or {}
            remove_job_dir(meta.get("temp_job_dir"))
            await delete_extracted_content(document.doc_metadata)
            await self.db.delete(document)
        if existing:
            await self.db.commit()
        await clear_package_redis(package_id)

    async def list_package_documents(self, package_id: int) -> list[KnowledgeDocument]:
        """List sources in a package (newest first)."""
        result = await self.db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.batch_id == package_id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def _package_documents(self, package_id: int) -> list[KnowledgeDocument]:
        return await self.list_package_documents(package_id)

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


async def _run_file_extract_job(
    *,
    user_id: int,
    package_id: int,
    document_id: int,
    source_path: str,
    job_dir: str,
    file_type: str,
    source_filename: str,
    file_size: int,
) -> None:
    """Background extract: convert if needed, extract, store markdown, cleanup temps."""
    try:
        async with user_rls_session(user_id) as db:
            service = DocSummaryIngestService(db, user_id)
            document = await db.get(KnowledgeDocument, document_id)
            if document is None:
                logger.warning(
                    "[DocSummary] Extract job skipped; document %s missing",
                    document_id,
                )
                return

            async def _progress(doc: KnowledgeDocument, stage: str) -> None:
                percent = _STAGE_PERCENT.get(stage, 50)
                doc.processing_progress = stage
                doc.processing_progress_percent = percent
                doc.status = "processing"
                await db.commit()
                await set_package_extract_progress(package_id, "processing", stage, percent)

            extract_path = source_path
            extract_mime = file_type
            try:
                if is_legacy_office_mime(file_type):
                    await _progress(document, "converting")
                    convert_dir = Path(job_dir) / "converted"
                    convert_dir.mkdir(parents=True, exist_ok=True)
                    converted_path, extract_mime = await asyncio.to_thread(
                        convert_legacy_office,
                        source_path,
                        file_type,
                        str(convert_dir),
                    )
                    extract_path = converted_path

                if extract_mime in _IMAGE_MIMES or extract_mime == "application/pdf":
                    await _progress(
                        document,
                        "ocr" if extract_mime in _IMAGE_MIMES else "extracting",
                    )
                elif extract_mime.startswith(_AUDIO_MIME_PREFIX):
                    await _progress(document, "transcribing")
                else:
                    await _progress(document, "extracting")

                await release_open_transaction(db)
                extracted = await asyncio.to_thread(
                    service.processor.extract_text,
                    extract_path,
                    extract_mime,
                )
                if not extracted or not extracted.strip():
                    raise ValueError("No text could be extracted from the file")

                # User may have deleted the source while extract was running.
                fresh = await db.get(KnowledgeDocument, document_id)
                if fresh is None:
                    logger.info(
                        "[DocSummary] Extract aborted; document %s deleted mid-job",
                        document_id,
                    )
                    return
                document = fresh

                await _progress(document, "storing")
                await service.persist_extracted(
                    package_id=package_id,
                    markdown=extracted,
                    source_filename=source_filename,
                    source_mime=file_type,
                    file_size=file_size,
                    ingest_source="upload",
                    existing_document=document,
                    skip_replace=True,
                )
            except _DOC_SUMMARY_INGEST_ERRORS as exc:
                logger.warning(
                    "[DocSummary] Extract failed package=%s doc=%s: %s",
                    package_id,
                    document_id,
                    exc,
                )
                fresh = await db.get(KnowledgeDocument, document_id)
                if fresh is None:
                    return
                document = fresh
                document.status = "failed"
                document.processing_progress = "failed"
                document.processing_progress_percent = 0
                document.error_message = str(exc)[:500]
                meta = dict(document.doc_metadata or {})
                meta.pop("temp_job_dir", None)
                meta.pop("temp_source_path", None)
                document.doc_metadata = meta
                document.file_path = ""
                await db.commit()
                await set_package_extract_progress(package_id, "failed", "failed", 0)
    finally:
        remove_job_dir(job_dir)
