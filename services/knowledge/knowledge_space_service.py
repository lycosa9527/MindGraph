"""Knowledge Space Service.

Author: lycosa9527
Made by: MindSpring Team

Manages user knowledge spaces, document uploads, and processing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib
import logging
import os
import shutil

from sqlalchemy import and_, select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dashscope_embedding import get_embedding_client
from models.domain.knowledge_space import (
    KnowledgeSpace,
    KnowledgeDocument,
    DocumentChunk,
    DocumentBatch,
    DocumentVersion,
)
from services.infrastructure.rate_limiting.kb_rate_limiter import get_kb_rate_limiter
from services.knowledge.chunking_service import get_chunking_service
from services.knowledge.document_cleaner import get_document_cleaner
from services.knowledge.document_processor import get_document_processor
from services.knowledge.document_processing import (
    extract_and_clean_text,
    chunk_text_with_mode,
    generate_embeddings_with_cache,
    prepare_qdrant_metadata,
)
from services.knowledge.document_reindexing import (
    chunk_text_for_reindexing,
    compare_chunks,
    process_updated_chunks,
    process_new_chunks,
)
from services.knowledge.document_versioning import (
    rollback_document as rollback_document_helper,
    get_document_versions as get_document_versions_helper,
)
from services.knowledge.document_batch_service import (
    batch_upload_documents as batch_upload_documents_helper,
    update_batch_progress as update_batch_progress_helper,
)
from services.llm.qdrant_service import get_qdrant_service


logger = logging.getLogger(__name__)


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
        self.chunking = get_chunking_service()
        self.cleaner = get_document_cleaner()
        self.qdrant = get_qdrant_service()
        self.embedding_client = get_embedding_client()
        self.kb_rate_limiter = get_kb_rate_limiter()

        # Configuration
        self.max_documents = int(os.getenv("MAX_DOCUMENTS_PER_USER", "5"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
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
        """Get current document count for user."""
        space = await self.create_knowledge_space()
        result = await self.db.execute(
            select(func.count(KnowledgeDocument.id)).where(KnowledgeDocument.space_id == space.id)
        )
        return result.scalar_one()

    async def upload_document(
        self, file_name: str, file_path: str, file_type: str, file_size: int
    ) -> KnowledgeDocument:
        """
        Upload document (creates record, actual processing happens in background).

        Args:
            file_name: Original filename
            file_path: Temporary file path
            file_type: MIME type
            file_size: File size in bytes

        Returns:
            KnowledgeDocument instance
        """
        count = await self.get_document_count()
        if count >= self.max_documents:
            raise ValueError(f"Maximum {self.max_documents} documents allowed. Please delete a document first.")

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
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        final_path = user_dir / f"{document.id}_{file_name}"
        shutil.move(file_path, final_path)
        document.file_path = str(final_path)
        await self.db.commit()

        logger.info(
            "[RAG] ✓ Upload: doc_id=%s, file='%s', type=%s, size=%s bytes, user=%s",
            document.id,
            file_name,
            file_type,
            file_size,
            self.user_id,
        )
        return document

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
            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            logger.info(
                "[RAG] → Processing: doc_id=%s, file='%s', type=%s, chunking_engine=%s, chunking_method=%s",
                document_id,
                document.file_name,
                document.file_type,
                chunking_engine,
                chunking_method,
            )
            if chunking_method == "mindchunk":
                logger.info(
                    "[RAG] 🧠 MindChunk ACTIVE: LLM-based semantic chunking will be used for doc_id=%s",
                    document_id,
                )

            document.status = "processing"
            document.processing_progress = "extracting"
            document.processing_progress_percent = 10
            await self.db.commit()

            result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == document.space_id))
            space = result.scalars().first()
            processing_rules = space.processing_rules if space and space.processing_rules else None

            try:
                cleaned_text, page_info = await extract_and_clean_text(
                    self.processor, self.cleaner, document, self.db, processing_rules
                )
            except ValueError:
                raise
            except Exception as extract_error:
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

            mode = "automatic"
            if processing_rules:
                mode = processing_rules.get("mode", "automatic")

            chunks = chunk_text_with_mode(
                self.chunking,
                cleaned_text,
                document,
                processing_rules,
                page_info,
                document_id,
            )

            if len(chunks) == 0:
                raise ValueError(
                    f"Chunking returned 0 chunks for document {document_id}. "
                    "This may indicate an issue with MindChunk or document content. "
                    "Check logs above for chunking errors."
                )
            if not self.chunking.validate_chunk_count(len(chunks), self.user_id):
                raise ValueError(f"Chunk count ({len(chunks)}) exceeds limit")

            logger.info(
                "[RAG] ✓ Chunking: doc_id=%s, created %s chunks, method=%s, mode=%s",
                document_id,
                len(chunks),
                chunking_method,
                mode,
            )
            if chunking_method == "mindchunk" and chunks:
                sample_chunk = chunks[0]
                logger.debug(
                    "[RAG] MindChunk sample metadata for doc_id=%s: keys=%s, structure_type=%s, has_token_count=%s",
                    document_id,
                    list(sample_chunk.metadata.keys()),
                    sample_chunk.metadata.get("structure_type"),
                    "token_count" in sample_chunk.metadata,
                )

            document.processing_progress = "chunking"
            document.processing_progress_percent = 40
            await self.db.commit()

            document.processing_progress = "embedding"
            document.processing_progress_percent = 50
            await self.db.commit()

            texts = [chunk.text for chunk in chunks]
            embeddings = await generate_embeddings_with_cache(
                self.embedding_client,
                self.kb_rate_limiter,
                texts,
                self.user_id,
                self.db,
            )

            document.processing_progress_percent = 80
            await self.db.commit()
            logger.info(
                "[RAG] ✓ Embedding: doc=%s, %s vectors generated",
                document_id,
                len(embeddings),
            )

            if len(embeddings) != len(chunks):
                raise ValueError(f"Embedding count ({len(embeddings)}) != chunk count ({len(chunks)})")

            document.processing_progress = "indexing"
            document.processing_progress_percent = 85
            await self.db.commit()

            try:
                chunk_ids = []
                for chunk, _ in zip(chunks, embeddings):
                    db_chunk = DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                    )
                    self.db.add(db_chunk)
                    await self.db.flush()
                    chunk_ids.append(db_chunk.id)
                logger.info(
                    "[RAG] ✓ Chunking: doc=%s, %s chunks saved to database",
                    document_id,
                    len(chunk_ids),
                )
            except Exception as chunk_db_error:
                error_msg = f"保存分块数据失败: {str(chunk_db_error)}"
                logger.error(
                    "[RAG] ✗ Chunking FAILED: doc=%s, error=%s",
                    document_id,
                    chunk_db_error,
                )
                raise ValueError(error_msg) from chunk_db_error

            try:
                try:
                    qdrant_metadata = prepare_qdrant_metadata(chunks, document)
                    self.qdrant.add_documents(
                        user_id=self.user_id,
                        chunk_ids=chunk_ids,
                        embeddings=embeddings,
                        document_ids=[document.id] * len(chunk_ids),
                        metadata=qdrant_metadata,
                    )
                    logger.info(
                        "[RAG] ✓ Vector Store: doc=%s, %s vectors stored in Qdrant",
                        document_id,
                        len(chunk_ids),
                    )
                except Exception as qdrant_insert_error:
                    error_msg = f"向量存储失败: {str(qdrant_insert_error)}"
                    logger.error(
                        "[RAG] ✗ Vector Store FAILED: doc=%s, error=%s",
                        document_id,
                        qdrant_insert_error,
                    )
                    raise ValueError(error_msg) from qdrant_insert_error

                document.status = "completed"
                document.chunk_count = len(chunks)
                document.processing_progress = None
                document.processing_progress_percent = 100
                await self.db.commit()

            except ValueError:
                raise
            except Exception as qdrant_error:
                error_msg = f"数据保存失败: {str(qdrant_error)}"
                logger.error(
                    "[KnowledgeSpace] Qdrant write succeeded but database commit failed: %s",
                    qdrant_error,
                )
                try:
                    await self.db.rollback()
                    self.qdrant.delete_document(self.user_id, document.id)
                    logger.info(
                        "[KnowledgeSpace] Cleaned up orphaned Qdrant vectors for document %s",
                        document_id,
                    )
                except Exception as cleanup_error:
                    logger.error(
                        "[KnowledgeSpace] Failed to cleanup Qdrant after database failure: %s",
                        cleanup_error,
                    )
                raise ValueError(error_msg) from qdrant_error

            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            logger.info(
                "[RAG] ✓ Processing complete: doc_id=%s, file='%s', chunks=%s, method=%s, user=%s",
                document_id,
                document.file_name,
                len(chunks),
                chunking_method,
                self.user_id,
            )

            try:
                if document.file_type == "application/pdf":
                    text, _ = self.processor.extract_text_with_pages(document.file_path, document.file_type)
                else:
                    text = self.processor.extract_text(document.file_path, document.file_type)
                if isinstance(text, list):
                    text = "\n".join(str(item) for item in text)
                if not isinstance(text, str):
                    text = str(text) if text else ""
                references = self.processor.extract_references(text, document.id)
                for ref in references:
                    logger.debug(
                        "[KnowledgeSpace] Found reference in document %s: %s",
                        document.id,
                        ref["text"],
                    )
            except Exception as ref_error:
                logger.warning(
                    "[KnowledgeSpace] Failed to extract references for document %s: %s",
                    document_id,
                    ref_error,
                )

        except Exception as e:
            logger.error("[KnowledgeSpace] Failed to process document %s: %s", document_id, e)
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            await self.db.commit()
            raise

    async def batch_upload_documents(self, files: List[Dict[str, Any]]) -> DocumentBatch:
        """
        Upload multiple documents in a batch.

        Args:
            files: List of dicts with keys: file_name, file_path, file_type, file_size

        Returns:
            DocumentBatch instance
        """
        current_count = await self.get_document_count()
        if current_count + len(files) > self.max_documents:
            raise ValueError(
                f"Cannot upload {len(files)} documents. Current count: {current_count}, Max: {self.max_documents}"
            )

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
            self.qdrant.delete_document(self.user_id, document_id)

            if document.file_path and Path(document.file_path).exists():
                Path(document.file_path).unlink()

            await self.db.delete(document)
            await self.db.commit()

            logger.info(
                "[KnowledgeSpace] Deleted document %s for user %s",
                document_id,
                self.user_id,
            )

        except Exception as e:
            logger.error("[KnowledgeSpace] Failed to delete document %s: %s", document_id, e)
            await self.db.rollback()
            raise

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
            except Exception as version_error:
                logger.warning(
                    "[KnowledgeSpace] Failed to create version for document %s: %s",
                    document.id,
                    version_error,
                )

            if old_file_path != document.file_path and Path(old_file_path).exists():
                try:
                    Path(old_file_path).unlink()
                except Exception as e:
                    logger.warning(
                        "[KnowledgeSpace] Failed to delete old file %s: %s",
                        old_file_path,
                        e,
                    )

            change_summary = await self._reindex_chunks(document, new_content_hash)

            if "version" in locals() and change_summary:
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

        except Exception as e:
            logger.error("[KnowledgeSpace] Failed to update document %s: %s", document_id, e)
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            await self.db.commit()
            raise

    async def _reindex_chunks(self, document: KnowledgeDocument, content_hash: str) -> Dict[str, int]:
        """
        Reindex document chunks with partial reindexing support.

        Only changed chunks are reindexed. Chunks are compared by text hash.

        Args:
            document: KnowledgeDocument instance
            content_hash: Hash of new content

        Returns:
            Dict with change summary: {"added": count, "updated": count, "deleted": count}
        """
        try:
            document.processing_progress = "extracting"
            document.processing_progress_percent = 10
            await self.db.commit()

            result = await self.db.execute(select(KnowledgeSpace).where(KnowledgeSpace.id == document.space_id))
            space = result.scalars().first()
            processing_rules = space.processing_rules if space and space.processing_rules else None

            try:
                cleaned_text, page_info = await extract_and_clean_text(
                    self.processor, self.cleaner, document, self.db, processing_rules
                )
            except ValueError:
                raise
            except Exception as extract_error:
                error_msg = f"文本提取失败: {str(extract_error)}"
                logger.error(
                    "[KnowledgeSpace] Text extraction failed for document %s: %s",
                    document.id,
                    extract_error,
                    exc_info=True,
                )
                raise ValueError(error_msg) from extract_error

            document.processing_progress = "cleaning"
            document.processing_progress_percent = 20
            await self.db.commit()

            document.processing_progress = "chunking"
            document.processing_progress_percent = 30
            await self.db.commit()

            new_chunks = chunk_text_for_reindexing(self.chunking, cleaned_text, document, processing_rules, page_info)

            if not self.chunking.validate_chunk_count(len(new_chunks), self.user_id):
                raise ValueError(f"Chunk count ({len(new_chunks)}) exceeds limit")

            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            mode = processing_rules.get("mode", "automatic") if processing_rules else "automatic"
            logger.info(
                "[RAG] ✓ Chunking (update): doc_id=%s, created %s chunks, method=%s, mode=%s",
                document.id,
                len(new_chunks),
                chunking_method,
                mode,
            )

            result = await self.db.execute(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == document.id)
                .order_by(DocumentChunk.chunk_index)
            )
            existing_chunks = list(result.scalars().all())

            existing_chunk_map: Dict[int, DocumentChunk] = {}
            for chunk in existing_chunks:
                existing_chunk_map[chunk.chunk_index] = chunk

            document.processing_progress = "comparing"
            document.processing_progress_percent = 40
            await self.db.commit()

            chunks_to_add, chunks_to_update, chunks_to_delete = compare_chunks(
                new_chunks, existing_chunks, self._calculate_chunk_hash
            )

            logger.info(
                "[RAG] ✓ Chunk comparison: doc_id=%s, added=%s, updated=%s, deleted=%s",
                document.id,
                len(chunks_to_add),
                len(chunks_to_update),
                len(chunks_to_delete),
            )

            if chunks_to_delete:
                chunk_ids_to_delete = [existing_chunk_map[i].id for i in chunks_to_delete]
                self.qdrant.delete_chunks(self.user_id, chunk_ids_to_delete)
                await self.db.execute(delete(DocumentChunk).where(DocumentChunk.id.in_(chunk_ids_to_delete)))
                await self.db.commit()

            if chunks_to_update:
                document.processing_progress = "updating_chunks"
                document.processing_progress_percent = 50
                await self.db.commit()

                updated_chunk_ids, updated_embeddings, updated_chunks = await process_updated_chunks(
                    chunks_to_update,
                    existing_chunk_map,
                    document,
                    self.embedding_client,
                    self.kb_rate_limiter,
                    self.user_id,
                    self.db,
                )

                if updated_chunk_ids:
                    updated_metadata = prepare_qdrant_metadata(updated_chunks, document)
                    self.qdrant.update_documents(
                        user_id=self.user_id,
                        chunk_ids=updated_chunk_ids,
                        embeddings=updated_embeddings,
                        document_ids=[document.id] * len(updated_chunk_ids),
                        metadata=updated_metadata,
                    )
                    await self.db.commit()

            if chunks_to_add:
                document.processing_progress = "adding_chunks"
                document.processing_progress_percent = 70
                await self.db.commit()

                new_chunk_ids, new_embeddings, new_chunks_list = await process_new_chunks(
                    chunks_to_add,
                    document,
                    self.embedding_client,
                    self.kb_rate_limiter,
                    self.user_id,
                    self.db,
                )

                if new_chunk_ids:
                    new_metadata = prepare_qdrant_metadata(new_chunks_list, document)
                    self.qdrant.add_documents(
                        user_id=self.user_id,
                        chunk_ids=new_chunk_ids,
                        embeddings=new_embeddings,
                        document_ids=[document.id] * len(new_chunk_ids),
                        metadata=new_metadata,
                    )
                    await self.db.commit()

            document.status = "completed"
            document.chunk_count = len(new_chunks)
            document.last_updated_hash = content_hash
            document.processing_progress = None
            document.processing_progress_percent = 100
            await self.db.commit()

            change_summary = {
                "added": len(chunks_to_add),
                "updated": len(chunks_to_update),
                "deleted": len(chunks_to_delete),
            }

            logger.info(
                "[RAG] ✓ Reindexing complete: doc_id=%s, added=%s, updated=%s, deleted=%s, total_chunks=%s",
                document.id,
                change_summary["added"],
                change_summary["updated"],
                change_summary["deleted"],
                document.chunk_count,
            )

            return change_summary

        except Exception as e:
            logger.error(
                "[KnowledgeSpace] Failed to reindex chunks for document %s: %s",
                document.id,
                e,
            )
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            await self.db.commit()
            return {"added": 0, "updated": 0, "deleted": 0}
