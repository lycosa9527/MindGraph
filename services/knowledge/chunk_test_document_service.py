"""Chunk Test Document Service.

Author: lycosa9527
Made by: MindSpring Team

Manages documents specifically for chunk testing, separate from knowledge space.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from pathlib import Path
from typing import List, Optional
import logging
import os
import shutil

from sqlalchemy import and_, select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from clients.dashscope_embedding import get_embedding_client
from models.domain.knowledge_space import ChunkTestDocument, ChunkTestDocumentChunk
from services.infrastructure.rate_limiting.kb_rate_limiter import get_kb_rate_limiter
from services.knowledge.chunking_service import get_chunking_service
from services.knowledge.document_cleaner import get_document_cleaner
from services.knowledge.document_processor import get_document_processor
from services.knowledge.document_processing import generate_embeddings_with_cache
from services.knowledge.rag_chunk_test.chunk_comparator import ChunkComparator
from services.llm.qdrant_service import get_qdrant_service
from services.knowledge.progress_tracking import (
    format_progress_string,
    get_progress_percent,
    validate_progress,
    ensure_completion_progress,
)


logger = logging.getLogger(__name__)


class ChunkTestDocumentService:
    """
    Chunk test document management service.

    Handles document uploads, processing, and deletion for chunk testing.
    Separate from knowledge space documents.
    """

    def __init__(self, db: AsyncSession, user_id: int):
        """
        Initialize service for specific user.

        Args:
            db: Database session
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
        self.chunk_comparator = ChunkComparator()

        # Default chunking methods for testing (5 methods)
        self.chunking_methods = [
            "spacy",
            "semchunk",
            "chonkie",
            "langchain",
            "mindchunk",
        ]

        # Configuration
        self.max_documents = int(os.getenv("MAX_CHUNK_TEST_DOCUMENTS_PER_USER", "5"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
        self.storage_dir = Path(os.getenv("CHUNK_TEST_STORAGE_DIR", "./storage/chunk_test_documents"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    async def get_document_count(self) -> int:
        """Get current document count for user."""
        result = await self.db.execute(
            select(func.count(ChunkTestDocument.id)).where(ChunkTestDocument.user_id == self.user_id)
        )
        return result.scalar_one()

    async def upload_document(
        self, file_name: str, file_path: str, file_type: str, file_size: int
    ) -> ChunkTestDocument:
        """
        Upload document (creates record, actual processing happens manually).

        Args:
            file_name: Original filename
            file_path: Temporary file path
            file_type: MIME type
            file_size: File size in bytes

        Returns:
            ChunkTestDocument instance
        """
        count = await self.get_document_count()
        if count >= self.max_documents:
            raise ValueError(f"Maximum {self.max_documents} documents allowed. Please delete a document first.")

        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({self.max_file_size} bytes)")

        if not self.processor.is_supported(file_type):
            raise ValueError(f"Unsupported file type: {file_type}")

        result = await self.db.execute(
            select(ChunkTestDocument).where(
                and_(
                    ChunkTestDocument.user_id == self.user_id,
                    ChunkTestDocument.file_name == file_name,
                )
            )
        )
        existing = result.scalars().first()

        if existing:
            raise ValueError(f"Document with name '{file_name}' already exists")

        user_dir = self.storage_dir / str(self.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        document = ChunkTestDocument(
            user_id=self.user_id,
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
            "[ChunkTestDocument] ✓ Upload: doc_id=%s, file='%s', type=%s, size=%s bytes, user=%s",
            document.id,
            file_name,
            file_type,
            file_size,
            self.user_id,
        )
        return document

    async def get_user_documents(self) -> List[ChunkTestDocument]:
        """Get all documents for user."""
        result = await self.db.execute(
            select(ChunkTestDocument)
            .where(ChunkTestDocument.user_id == self.user_id)
            .order_by(ChunkTestDocument.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_document(self, document_id: int) -> Optional[ChunkTestDocument]:
        """
        Get document by ID (verifies ownership).

        Args:
            document_id: Document ID

        Returns:
            ChunkTestDocument instance or None
        """
        result = await self.db.execute(
            select(ChunkTestDocument).where(
                and_(
                    ChunkTestDocument.id == document_id,
                    ChunkTestDocument.user_id == self.user_id,
                )
            )
        )
        return result.scalars().first()

    def _extract_and_clean_text(self, document: ChunkTestDocument) -> str:
        """
        Extract and clean text from document.

        Args:
            document: ChunkTestDocument instance

        Returns:
            Cleaned text string
        """
        if document.file_type == "application/pdf":
            text, _ = self.processor.extract_text_with_pages(document.file_path, document.file_type)
        else:
            text = self.processor.extract_text(document.file_path, document.file_type)

        if isinstance(text, list):
            text = "\n".join(str(item) for item in text)
        if not isinstance(text, str):
            text = str(text) if text else ""

        cleaned_text: str = self.cleaner.clean(text, remove_extra_spaces=True, remove_urls_emails=False)

        return cleaned_text

    def _chunk_text(self, text: str, document_id: int) -> List:
        """
        Chunk text using mindchunk (default for testing).

        Args:
            text: Cleaned text to chunk
            document_id: Document ID for logging

        Returns:
            List of chunks
        """
        chunks = self.chunking.chunk_text(text=text)

        logger.info(
            "[ChunkTestDocument] Created %s chunks for document %s",
            len(chunks),
            document_id,
        )

        return chunks

    async def process_document(self, document_id: int) -> None:
        """
        Process document: extract text, chunk with all 5 methods, embed, store.

        For RAG chunk testing, processes each document with 5 chunking methods:
        - spacy, semchunk, chonkie, langchain, mindchunk

        Stores chunks, embeddings, and indexing separately for each method.

        Args:
            document_id: Document ID
        """
        document = await self.get_document(document_id)
        if not document:
            raise ValueError("Document not found or access denied")

        if document.status == "processing":
            logger.warning("[ChunkTestDocument] Document %s is already processing", document_id)
            return

        try:
            document.status = "processing"
            document.processing_progress = format_progress_string("starting")
            document.processing_progress_percent = get_progress_percent("starting")
            await self.db.commit()
            await self.db.refresh(document)

            logger.info("[ChunkTestDocument] Extracting text from document %s", document_id)
            document.processing_progress = format_progress_string("extracting")
            document.processing_progress_percent = get_progress_percent("extracting")
            await self.db.commit()
            await self.db.refresh(document)

            cleaned_text = self._extract_and_clean_text(document)

            if not cleaned_text or not cleaned_text.strip():
                raise ValueError("No text extracted from document")

            await self.db.execute(
                delete(ChunkTestDocumentChunk).where(ChunkTestDocumentChunk.document_id == document_id)
            )
            await self.db.flush()

            total_methods = len(self.chunking_methods)
            total_chunks = 0
            method_metadata = {}
            successful_methods = []
            failed_methods = []
            previous_progress = 0

            for method_idx, method_name in enumerate(self.chunking_methods):
                document.processing_progress = format_progress_string("chunking", method_name)
                new_progress = get_progress_percent("chunking", method_index=method_idx, total_methods=total_methods)
                validated_progress, _ = validate_progress(new_progress, previous_progress, f"chunking ({method_name})")
                document.processing_progress_percent = validated_progress
                previous_progress = validated_progress
                await self.db.commit()
                await self.db.refresh(document)

                logger.info(
                    "[ChunkTestDocument] Processing document %s with method %s (%d/%d)",
                    document_id,
                    method_name,
                    method_idx + 1,
                    total_methods,
                )

                try:
                    chunks, _ = self.chunk_comparator.chunk_with_method(
                        cleaned_text,
                        method_name,
                        metadata={
                            "document_id": document_id,
                            "file_name": document.file_name,
                        },
                    )

                    if not chunks:
                        logger.warning(
                            "[ChunkTestDocument] No chunks generated for method %s on document %s",
                            method_name,
                            document_id,
                        )
                        continue

                    chunk_ids = []
                    for idx, chunk in enumerate(chunks):
                        chunk_metadata = dict(chunk.metadata) if chunk.metadata else {}
                        chunk_metadata["chunking_method"] = method_name

                        chunk_record = ChunkTestDocumentChunk(
                            document_id=document_id,
                            chunk_index=chunk.chunk_index if hasattr(chunk, "chunk_index") else idx,
                            text=chunk.text,
                            start_char=chunk.start_char if hasattr(chunk, "start_char") else 0,
                            end_char=chunk.end_char if hasattr(chunk, "end_char") else len(chunk.text),
                            chunking_method=method_name,
                            meta_data=chunk_metadata,
                        )
                        self.db.add(chunk_record)
                        await self.db.flush()
                        chunk_ids.append(chunk_record.id)

                    document.processing_progress = format_progress_string("embedding", method_name)
                    new_progress = get_progress_percent(
                        "embedding",
                        method_index=method_idx,
                        total_methods=total_methods,
                    )
                    validated_progress, _ = validate_progress(
                        new_progress, previous_progress, f"embedding ({method_name})"
                    )
                    document.processing_progress_percent = validated_progress
                    previous_progress = validated_progress
                    await self.db.commit()
                    await self.db.refresh(document)

                    texts = [chunk.text for chunk in chunks]
                    embeddings = await generate_embeddings_with_cache(
                        self.embedding_client,
                        self.kb_rate_limiter,
                        texts,
                        self.user_id,
                        self.db,
                    )

                    qdrant_metadata = []
                    for idx, chunk in enumerate(chunks):
                        metadata = {
                            "document_id": document_id,
                            "chunk_index": chunk.chunk_index if hasattr(chunk, "chunk_index") else idx,
                            "file_name": document.file_name,
                            "file_type": document.file_type,
                            "chunking_method": method_name,
                            "is_chunk_test": True,
                        }
                        if chunk.metadata:
                            metadata.update(chunk.metadata)
                        qdrant_metadata.append(metadata)

                    document.processing_progress = format_progress_string("indexing", method_name)
                    new_progress = get_progress_percent(
                        "indexing", method_index=method_idx, total_methods=total_methods
                    )
                    validated_progress, _ = validate_progress(
                        new_progress, previous_progress, f"indexing ({method_name})"
                    )
                    document.processing_progress_percent = validated_progress
                    previous_progress = validated_progress
                    await self.db.commit()
                    await self.db.refresh(document)

                    self.qdrant.add_documents(
                        user_id=self.user_id,
                        chunk_ids=chunk_ids,
                        embeddings=embeddings,
                        document_ids=[document_id] * len(chunk_ids),
                        metadata=qdrant_metadata,
                        chunking_method=method_name,
                    )

                    total_chunks += len(chunks)
                    method_metadata[method_name] = {
                        "chunk_count": len(chunks),
                        "chunk_ids": chunk_ids,
                    }
                    successful_methods.append(method_name)

                    logger.info(
                        "[ChunkTestDocument] ✓ Method %s: %d chunks stored and indexed",
                        method_name,
                        len(chunks),
                    )

                except Exception as method_error:
                    error_msg = str(method_error)
                    failed_methods.append({"method": method_name, "error": error_msg})
                    logger.error(
                        "[ChunkTestDocument] ✗ Method %s failed for document %s: %s",
                        method_name,
                        document_id,
                        error_msg,
                        exc_info=True,
                    )
                    if method_idx < total_methods - 1:
                        next_method_progress = get_progress_percent(
                            "chunking",
                            method_index=method_idx + 1,
                            total_methods=total_methods,
                        )
                        validated_progress, _ = validate_progress(
                            next_method_progress,
                            previous_progress,
                            f"chunking (skipped {method_name})",
                        )
                        document.processing_progress_percent = validated_progress
                        previous_progress = validated_progress
                        await self.db.commit()
                        await self.db.refresh(document)
                    continue

            if total_chunks == 0:
                raise ValueError("No chunks generated from any chunking method")

            processing_results = {
                "successful_methods": successful_methods,
                "failed_methods": failed_methods,
                "total_methods_attempted": total_methods,
                "total_methods_succeeded": len(successful_methods),
                "total_methods_failed": len(failed_methods),
            }

            if document.meta_data is None:
                document.meta_data = {}
            document.meta_data["processing_results"] = processing_results

            document.status = "completed"
            document.chunk_count = total_chunks
            document.processing_progress = format_progress_string("completed")
            final_progress = ensure_completion_progress(get_progress_percent("completed"), 100)
            validated_progress, _ = validate_progress(final_progress, previous_progress, "completed")
            document.processing_progress_percent = validated_progress

            logger.info(
                "[ChunkTestDocument] Processing complete for document %s: %d/%d methods succeeded, %d total chunks",
                document_id,
                len(successful_methods),
                total_methods,
                total_chunks,
            )
            if failed_methods:
                logger.warning(
                    "[ChunkTestDocument] Failed methods for document %s: %s",
                    document_id,
                    [f["method"] for f in failed_methods],
                )
            await self.db.commit()
            await self.db.refresh(document)

            logger.info(
                "[ChunkTestDocument] ✓ Processed: doc_id=%s, total_chunks=%s, methods=%s, user=%s",
                document_id,
                total_chunks,
                list(method_metadata.keys()),
                self.user_id,
            )

        except Exception as e:
            logger.error(
                "[ChunkTestDocument] ✗ Processing failed: doc_id=%s, error=%s",
                document_id,
                e,
                exc_info=True,
            )
            document.status = "failed"
            document.error_message = str(e)
            document.processing_progress_percent = 0
            await self.db.commit()
            raise

    async def delete_document(self, document_id: int) -> None:
        """
        Delete document and all associated data.

        Args:
            document_id: Document ID
        """
        document = await self.get_document(document_id)
        if not document:
            raise ValueError("Document not found or access denied")

        result = await self.db.execute(
            select(ChunkTestDocumentChunk).where(ChunkTestDocumentChunk.document_id == document_id)
        )
        chunks = list(result.scalars().all())

        if chunks:
            chunks_by_method = {}
            for chunk in chunks:
                method = chunk.chunking_method or "unknown"
                if method not in chunks_by_method:
                    chunks_by_method[method] = []
                chunks_by_method[method].append(chunk.id)

            for method, chunk_ids in chunks_by_method.items():
                try:
                    self.qdrant.delete_chunks(
                        self.user_id,
                        chunk_ids,
                        chunking_method=method if method != "unknown" else None,
                    )
                except Exception as e:
                    logger.warning(
                        "[ChunkTestDocument] Failed to delete Qdrant points for method %s: %s",
                        method,
                        e,
                    )

        try:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
        except Exception as e:
            logger.warning("[ChunkTestDocument] Failed to delete file: %s", e)

        await self.db.delete(document)
        await self.db.commit()

        logger.info(
            "[ChunkTestDocument] ✓ Deleted: doc_id=%s, user=%s",
            document_id,
            self.user_id,
        )

    async def cleanup_incomplete_processing(self, document_id: int) -> None:
        """
        Clean up incomplete processing for a document (e.g., after kill -9).

        This method:
        1. Deletes any partial chunks from database
        2. Deletes any partial Qdrant data for all chunking methods
        3. Resets document status to 'pending' so it can be retried

        Args:
            document_id: Document ID
        """
        document = await self.get_document(document_id)
        if not document:
            logger.warning("[ChunkTestDocument] Document %s not found for cleanup", document_id)
            return

        if document.status != "processing":
            logger.debug(
                "[ChunkTestDocument] Document %s is not in processing status, skipping cleanup",
                document_id,
            )
            return

        logger.info(
            "[ChunkTestDocument] Cleaning up incomplete processing for document %s",
            document_id,
        )

        result = await self.db.execute(
            select(ChunkTestDocumentChunk).where(ChunkTestDocumentChunk.document_id == document_id)
        )
        chunks = list(result.scalars().all())

        if chunks:
            chunks_by_method = {}
            for chunk in chunks:
                method = chunk.chunking_method or "unknown"
                if method not in chunks_by_method:
                    chunks_by_method[method] = []
                chunks_by_method[method].append(chunk.id)

            for method, chunk_ids in chunks_by_method.items():
                try:
                    self.qdrant.delete_chunks(
                        self.user_id,
                        chunk_ids,
                        chunking_method=method if method != "unknown" else None,
                    )
                    logger.debug(
                        "[ChunkTestDocument] Deleted %d Qdrant points for method %s",
                        len(chunk_ids),
                        method,
                    )
                except Exception as e:
                    logger.warning(
                        "[ChunkTestDocument] Failed to delete Qdrant points for method %s: %s",
                        method,
                        e,
                    )

        if chunks:
            await self.db.execute(
                delete(ChunkTestDocumentChunk).where(ChunkTestDocumentChunk.document_id == document_id)
            )
            await self.db.flush()
            logger.debug("[ChunkTestDocument] Deleted %d chunks from database", len(chunks))

        document.status = "pending"
        document.processing_progress = None
        document.processing_progress_percent = 0
        document.error_message = "Processing was interrupted and cleaned up. Please retry."
        await self.db.commit()

        logger.info(
            "[ChunkTestDocument] ✓ Cleaned up incomplete processing for document %s, reset to 'pending' status",
            document_id,
        )
