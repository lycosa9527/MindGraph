"""Knowledge Space Service.

Author: lycosa9527
Made by: MindSpring Team

Manages user knowledge spaces, document uploads, and processing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import asyncio
import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import (
    DocumentBatch,
    DocumentChunk,
    DocumentVersion,
    KnowledgeDocument,
    KnowledgeSpace,
)
from services.knowledge.chunking_policy import resolve_chunking_policy
from services.knowledge.document_batch_service import batch_upload_documents as batch_upload_documents_helper
from services.knowledge.document_batch_service import update_batch_progress as update_batch_progress_helper
from services.knowledge.document_cleaner import get_document_cleaner
from services.knowledge.document_processing import extract_and_clean_text
from services.knowledge.document_processor import get_document_processor
from services.knowledge.doc_summary_storage import clear_package_redis, delete_extracted_content
from services.knowledge.doc_summary_temp import remove_job_dir
from services.knowledge.document_quota import documents_toward_cap_stmt, over_quota_message
from services.knowledge.package_rag_scope import PERSONAL_KNOWLEDGE_SOURCES
from services.knowledge.personal_knowledge_log import log_personal_knowledge
from services.utils.safe_upload import ensure_within_directory, safe_upload_basename
from services.knowledge.personal_knowledge_publish import publish_personal_knowledge
from services.knowledge.vibeflow_store import delete_document_objects
from services.knowledge.document_versioning import get_document_versions as get_document_versions_helper
from services.knowledge.document_versioning import rollback_document as rollback_document_helper

logger = logging.getLogger(__name__)

# Three folders, ten sources each. The per-user cap is the product of those two.
MAX_DOCUMENTS_PER_PACKAGE = 10
MAX_DOCUMENTS_PER_USER_DEFAULT = MAX_DOCUMENTS_PER_PACKAGE * 3


class KnowledgeSpaceService:
    """
    Knowledge space management service.

    Handles document uploads, processing, and deletion with user isolation.
    """

    def __init__(self, db: AsyncSession, user_id: int):
        """
        Initialize service for specific user.

        Args:
            db: Async database session
            user_id: User ID (all operations scoped to this user)
        """
        self.db = db
        self.user_id = user_id
        self.processor = get_document_processor()
        self.cleaner = get_document_cleaner()

        # Configuration
        self.max_documents = int(os.getenv("MAX_DOCUMENTS_PER_USER", str(MAX_DOCUMENTS_PER_USER_DEFAULT)))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "52428800"))  # 50MB
        self.storage_dir = Path(os.getenv("KNOWLEDGE_STORAGE_DIR", "./storage/knowledge_documents"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def create_knowledge_space(self) -> KnowledgeSpace:
        """
        Create or get knowledge space for user.

        Returns:
            KnowledgeSpace instance
        """
        result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.user_id == self.user_id))
        space = result.scalars().first()

        if not space:
            space = KnowledgeSpace(user_id=self.user_id)
            self.db.add(space)
            await self.db.commit()
            await self.db.refresh(space)
            logger.info("[KnowledgeSpace] Created knowledge space for user %s", self.user_id)

        return space

    async def rollback_document(self, document_id: int, version_number: int) -> KnowledgeDocument:
        """
        Rollback document to a previous version.

        Args:
            document_id: Document ID
            version_number: Version number to rollback to

        Returns:
            Rolled back KnowledgeDocument instance
        """
        return await rollback_document_helper(
            self.db,
            self.user_id,
            document_id,
            version_number,
            self.storage_dir,
            self._reindex_chunks,
        )

    async def get_document_versions(self, document_id: int) -> List[DocumentVersion]:
        """
        Get all versions for a document.

        Args:
            document_id: Document ID

        Returns:
            List of DocumentVersion instances
        """
        return await get_document_versions_helper(self.db, self.user_id, document_id)

    async def get_document_count(self) -> int:
        """Count files that consume this user's document cap.

        Personal-knowledge folders share the count. Document Summary extracts
        and rows whose folder is gone do not.
        """
        space = await self.create_knowledge_space()
        result = await self.db.execute(documents_toward_cap_stmt(space.id))
        return int(result.scalar_one())

    async def ensure_upload_quota(self, incoming: int = 1) -> None:
        """Reject the upload when this user's library cannot take ``incoming`` more files."""
        count = await self.get_document_count()
        if count + incoming > self.max_documents:
            raise ValueError(over_quota_message(self.max_documents, count))

    async def count_documents_in_batch(self, batch_id: int) -> int:
        """How many sources are already stored in one folder."""
        result = await self.db.execute(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.batch_id == batch_id)
        )
        return int(result.scalar_one())

    async def upload_document(
        self,
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int,
        batch_id: Optional[int] = None,
    ) -> KnowledgeDocument:
        """
        Upload document (creates record, actual processing happens in background).

        Args:
            file_name: Original filename
            file_path: Temporary file path
            file_type: MIME type
            file_size: File size in bytes
            batch_id: Optional File Center package (DocumentBatch) to attach the source to

        Returns:
            KnowledgeDocument instance
        """
        file_name = safe_upload_basename(file_name)
        await self.ensure_upload_quota()

        if batch_id is not None:
            batch_count = await self.count_documents_in_batch(batch_id)
            if batch_count >= MAX_DOCUMENTS_PER_PACKAGE:
                raise ValueError(
                    f"Maximum {MAX_DOCUMENTS_PER_PACKAGE} documents allowed in a folder. Please delete a source first."
                )

        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({self.max_file_size} bytes)")

        if not self.processor.is_supported(file_type):
            raise ValueError(f"Unsupported file type: {file_type}")

        space = await self.create_knowledge_space()

        result = await self.db.execute(
            select(KnowledgeDocument).where(
                and_(
                    KnowledgeDocument.space_id == space.id,
                    KnowledgeDocument.file_name == file_name,
                )
            )
        )
        existing = result.scalars().first()

        if existing:
            raise ValueError(f"Document with name '{file_name}' already exists")

        user_dir = self.storage_dir / str(self.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        document = KnowledgeDocument(
            space_id=space.id,
            file_name=file_name,
            file_path=str(user_dir / file_name),
            file_type=file_type,
            file_size=file_size,
            status="pending",
            batch_id=batch_id,
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        final_path = ensure_within_directory(user_dir / f"{document.id}_{file_name}", user_dir)
        shutil.move(file_path, str(final_path))
        document.file_path = str(final_path)
        await self.db.commit()

        batch = await self.db.get(DocumentBatch, batch_id) if batch_id is not None else None
        if batch is not None and batch.source in PERSONAL_KNOWLEDGE_SOURCES:
            logger.info(
                "[PersonalKnowledge] upload user=%s package=%s document=%s file=%r type=%s bytes=%s source=%s",
                self.user_id,
                batch_id,
                document.id,
                file_name,
                file_type,
                file_size,
                batch.source,
            )
        else:
            logger.info(
                "[RAG] ✓ Upload: doc_id=%s, file='%s', type=%s, size=%s bytes, user=%s",
                document.id,
                file_name,
                file_type,
                file_size,
                self.user_id,
            )
        return document

    async def _apply_file_center_chunking_policy(
        self, document: KnowledgeDocument, processing_rules: Optional[dict]
    ) -> Optional[dict]:
        """Apply the per-source chunking policy for File Center package sources.

        For sources that belong to a named package (File Center), choose the
        chunking mode by file type — hierarchical for PDF/DOCX, flat for web and
        pasted text — unless the space pins an explicit mode. The resolved engine
        and mode are recorded on the document so the UI can surface them. Plain
        Knowledge Space uploads (no package) keep their existing behavior.
        """
        if document.batch_id is None:
            return processing_rules

        result = await self.db.execute(select(DocumentBatch).where(DocumentBatch.id == document.batch_id))
        batch = result.scalars().first()
        if not batch or not batch.name:
            return processing_rules

        policy = resolve_chunking_policy(
            document.file_type,
            processing_rules,
            ingest_source=(document.doc_metadata or {}).get("ingest_source"),
        )
        effective_rules = dict(processing_rules or {})
        effective_rules["mode"] = policy.mode

        metadata = dict(document.doc_metadata or {})
        metadata["chunking_engine"] = policy.engine
        metadata["chunking_mode"] = policy.mode
        document.doc_metadata = metadata
        await self.db.commit()

        logger.info(
            "[FileCenter] Chunking policy doc_id=%s type=%s → mode=%s engine=%s",
            document.id,
            document.file_type,
            policy.mode,
            policy.engine,
        )
        return effective_rules

    async def process_document(self, document_id: int) -> None:
        """
        Process document: extract text, chunk, embed, store.

        Args:
            document_id: Document ID
        """
        result = await self.db.execute(
            select(KnowledgeDocument)
            .join(KnowledgeSpace)
            .where(
                and_(
                    KnowledgeDocument.id == document_id,
                    KnowledgeSpace.user_id == self.user_id,
                )
            )
        )
        document = result.scalars().first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        try:
            await self._clear_document_index_if_present(document_id)

            logger.info(
                "[RAG] → Processing: doc_id=%s, file='%s', type=%s, chunking_method=semchunk",
                document_id,
                document.file_name,
                document.file_type,
            )

            document.status = "processing"
            document.processing_progress = "extracting"
            document.processing_progress_percent = 10
            await self.db.commit()
            batch = await self.db.get(DocumentBatch, document.batch_id) if document.batch_id else None
            if batch is not None and batch.source in PERSONAL_KNOWLEDGE_SOURCES:
                log_personal_knowledge(
                    "extracting",
                    user=self.user_id,
                    package=batch.id,
                    document=document.id,
                    file=document.file_name,
                    source=batch.source,
                )

            result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == document.space_id))
            space = result.scalars().first()
            processing_rules = space.processing_rules if space and space.processing_rules else None
            processing_rules = await self._apply_file_center_chunking_policy(document, processing_rules)

            try:
                cleaned_text, page_info, structure_headings = await extract_and_clean_text(
                    self.processor, self.cleaner, document, self.db, processing_rules
                )
            except ValueError as value_error:
                raise value_error
            except OSError as extract_error:
                error_msg = f"文本提取失败: {str(extract_error)}"
                logger.error(
                    "[KnowledgeSpace] Text extraction failed for document %s: %s",
                    document_id,
                    extract_error,
                )
                raise ValueError(error_msg) from extract_error

            document.processing_progress = "cleaning"
            document.processing_progress_percent = 20
            await self.db.commit()

            if await publish_personal_knowledge(
                self.db,
                self.user_id,
                document,
                cleaned_text,
                structure_headings,
                page_info,
            ):
                return

            batch = await self.db.get(DocumentBatch, document.batch_id) if document.batch_id else None
            if batch is not None and batch.source == "doc_summary":
                raise ValueError("Document summary uses its own ingest")
            raise ValueError("Only a personal knowledge folder is indexed")

        except (OSError, RuntimeError, ValueError) as e:
            log_personal_knowledge(
                "failed",
                user=self.user_id,
                package=document.batch_id,
                document=document_id,
                file=document.file_name,
                error=str(e),
            )
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            await self.db.commit()
            raise e

    async def batch_upload_documents(self, files: List[Dict[str, Any]]) -> DocumentBatch:
        """
        Upload multiple documents in a batch.

        Args:
            files: List of dicts with keys: file_name, file_path, file_type, file_size

        Returns:
            DocumentBatch instance
        """
        await self.ensure_upload_quota(incoming=len(files))

        space = await self.create_knowledge_space()

        return await batch_upload_documents_helper(
            self.db,
            self.user_id,
            space.id,
            files,
            self.storage_dir,
            self.max_file_size,
            self.processor,
        )

    async def update_batch_progress(self, batch_id: int, completed: int = 0, failed: int = 0) -> None:
        """
        Update batch processing progress.

        Args:
            batch_id: Batch ID
            completed: Number of completed documents (increment)
            failed: Number of failed documents (increment)
        """
        await update_batch_progress_helper(self.db, self.user_id, batch_id, completed, failed)

    async def _clear_document_index_if_present(self, document_id: int) -> None:
        """Remove leftover database chunks before a full reprocess."""
        result = await self.db.execute(select(DocumentChunk.id).where(DocumentChunk.document_id == document_id))
        chunk_ids = [row[0] for row in result.all()]
        if not chunk_ids:
            return

        await self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document_id))
        await self.db.commit()
        logger.info(
            "[KnowledgeSpace] Cleared %s existing chunks for doc_id=%s before reprocess",
            len(chunk_ids),
            document_id,
        )

    async def delete_document(self, document_id: int) -> None:
        """
        Delete document and all associated data.

        Args:
            document_id: Document ID
        """
        result = await self.db.execute(
            select(KnowledgeDocument)
            .join(KnowledgeSpace)
            .where(
                and_(
                    KnowledgeDocument.id == document_id,
                    KnowledgeSpace.user_id == self.user_id,
                )
            )
        )
        document = result.scalars().first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        try:
            metadata = document.doc_metadata or {}
            if metadata.get("doc_summary_lite") or metadata.get("temp_job_dir"):
                # Document Summary lite: drop COS/local markdown + any in-flight temp upload.
                remove_job_dir(metadata.get("temp_job_dir"))
                await delete_extracted_content(metadata)
                if document.batch_id is not None:
                    await clear_package_redis(document.batch_id)
            elif metadata.get("vibeflow") and document.batch_id is not None:
                await asyncio.to_thread(
                    delete_document_objects,
                    self.user_id,
                    document.batch_id,
                    document_id,
                )
                if document.file_path and Path(document.file_path).exists():
                    Path(document.file_path).unlink()
            else:
                if document.batch_id is not None:
                    await asyncio.to_thread(
                        delete_document_objects,
                        self.user_id,
                        document.batch_id,
                        document_id,
                    )
                if document.file_path and Path(document.file_path).exists():
                    Path(document.file_path).unlink()

            await self.db.delete(document)
            await self.db.commit()

            logger.info(
                "[KnowledgeSpace] Deleted document %s for user %s",
                document_id,
                self.user_id,
            )

        except OSError as e:
            logger.error("[KnowledgeSpace] Failed to delete document %s: %s", document_id, e)
            await self.db.rollback()
            raise e

    async def get_user_documents(self) -> List[KnowledgeDocument]:
        """Get all documents for user."""
        space = await self.create_knowledge_space()
        result = await self.db.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.space_id == space.id)
            .order_by(KnowledgeDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, document_id: int) -> Optional[KnowledgeDocument]:
        """
        Get document by ID (with ownership check).

        Args:
            document_id: Document ID

        Returns:
            KnowledgeDocument or None
        """
        result = await self.db.execute(
            select(KnowledgeDocument)
            .join(KnowledgeSpace)
            .where(
                and_(
                    KnowledgeDocument.id == document_id,
                    KnowledgeSpace.user_id == self.user_id,
                )
            )
        )
        return result.scalars().first()

    def _calculate_content_hash(self, file_path: str) -> str:
        """
        Calculate hash of file content for change detection.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash string
        """
        with open(file_path, "rb") as f:
            content = f.read()
        return hashlib.md5(content).hexdigest()

    def _calculate_chunk_hash(self, text: str) -> str:
        """
        Calculate hash of chunk text for change detection.

        Args:
            text: Chunk text

        Returns:
            MD5 hash string
        """
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def update_document(
        self, document_id: int, file_path: str, file_name: Optional[str] = None
    ) -> KnowledgeDocument:
        """
        Update document with new file content.

        Supports partial reindexing - only changed chunks are reindexed.

        Args:
            document_id: Document ID
            file_path: Path to new file
            file_name: Optional new filename (if None, keeps original)

        Returns:
            Updated KnowledgeDocument instance
        """
        result = await self.db.execute(
            select(KnowledgeDocument)
            .join(KnowledgeSpace)
            .where(
                and_(
                    KnowledgeDocument.id == document_id,
                    KnowledgeSpace.user_id == self.user_id,
                )
            )
        )
        document = result.scalars().first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        logger.info(
            "[RAG] → Update: doc_id=%s, file='%s', new_file='%s', type=%s, user=%s",
            document_id,
            document.file_name,
            file_name or document.file_name,
            document.file_type,
            self.user_id,
        )

        file_size = Path(file_path).stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({self.max_file_size} bytes)")

        file_type = self.processor.get_file_type(file_path)

        if file_type != document.file_type:
            logger.warning(
                "[KnowledgeSpace] File type changed from %s to %s for document %s. Full reindexing will be performed.",
                document.file_type,
                file_type,
                document_id,
            )

        new_content_hash = self._calculate_content_hash(file_path)

        if document.last_updated_hash == new_content_hash:
            logger.info(
                "[KnowledgeSpace] Document %s content unchanged, skipping update",
                document_id,
            )
            return document

        try:
            document.status = "processing"
            document.processing_progress = "updating"
            document.processing_progress_percent = 0
            if file_name:
                document.file_name = file_name
            document.file_size = file_size
            document.file_type = file_type
            document.version += 1
            await self.db.commit()

            user_dir = self.storage_dir / str(self.user_id)
            user_dir.mkdir(parents=True, exist_ok=True)

            old_file_path = document.file_path

            final_path = user_dir / f"{document.id}_{document.file_name}"
            shutil.move(file_path, final_path)
            document.file_path = str(final_path)
            await self.db.commit()

            version: DocumentVersion | None = None
            try:
                version_dir = self.storage_dir / str(self.user_id) / "versions" / str(document.id)
                version_dir.mkdir(parents=True, exist_ok=True)

                old_file_hash = document.last_updated_hash or self._calculate_content_hash(old_file_path)

                version_file_path = version_dir / f"v{document.version}_{document.file_name}"
                if Path(old_file_path).exists():
                    shutil.copy2(old_file_path, version_file_path)

                    version = DocumentVersion(
                        document_id=document.id,
                        version_number=document.version,
                        file_path=str(version_file_path),
                        file_hash=old_file_hash,
                        chunk_count=document.chunk_count or 0,
                        created_by=self.user_id,
                    )
                    self.db.add(version)
                    await self.db.commit()
                    logger.info(
                        "[KnowledgeSpace] Created version %s for document %s",
                        document.version,
                        document.id,
                    )
            except OSError as version_error:
                logger.warning(
                    "[KnowledgeSpace] Failed to create version for document %s: %s",
                    document.id,
                    version_error,
                )

            if old_file_path != document.file_path and Path(old_file_path).exists():
                try:
                    Path(old_file_path).unlink()
                except OSError as e:
                    logger.warning(
                        "[KnowledgeSpace] Failed to delete old file %s: %s",
                        old_file_path,
                        e,
                    )

            change_summary = await self._reindex_chunks(document, new_content_hash)

            if version is not None and change_summary:
                version.change_summary = change_summary
                await self.db.commit()

            logger.info(
                "[RAG] ✓ Update complete: doc_id=%s, version=%s, chunks=%s, user=%s",
                document_id,
                document.version,
                document.chunk_count,
                self.user_id,
            )
            return document

        except (OSError, RuntimeError, ValueError) as e:
            logger.error("[KnowledgeSpace] Failed to update document %s: %s", document_id, e)
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            await self.db.commit()
            raise e

    async def _reindex_chunks(self, document: KnowledgeDocument, content_hash: str) -> Dict[str, int]:
        """Republish one edited document into the personal knowledge store."""
        try:
            document.processing_progress = "extracting"
            document.processing_progress_percent = 10
            await self.db.commit()

            cleaned_text, page_info, structure_headings = await extract_and_clean_text(
                self.processor,
                self.cleaner,
                document,
                self.db,
                None,
            )
            published = await publish_personal_knowledge(
                self.db,
                self.user_id,
                document,
                cleaned_text,
                structure_headings,
                page_info,
            )
            if not published:
                raise ValueError("Only a personal knowledge folder is indexed")

            document.status = "completed"
            document.last_updated_hash = content_hash
            document.processing_progress = None
            document.processing_progress_percent = 100
            await self.db.commit()
            return {"added": document.chunk_count or 0, "updated": 0, "deleted": 0}

        except (OSError, ValueError) as e:
            log_personal_knowledge(
                "failed",
                user=self.user_id,
                package=document.batch_id,
                document=document.id,
                file=document.file_name,
                error=str(e),
            )
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            await self.db.commit()
            return {"added": 0, "updated": 0, "deleted": 0}
