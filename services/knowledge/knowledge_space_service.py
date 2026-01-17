from pathlib import Path
from typing import List, Optional, Dict, Set, Any
import hashlib
import logging
import os
import shutil

from sqlalchemy import and_
from sqlalchemy.orm import Session

from clients.dashscope_embedding import get_embedding_client
from models.knowledge_space import KnowledgeSpace, KnowledgeDocument, DocumentChunk, DocumentBatch, DocumentVersion
from services.infrastructure.kb_rate_limiter import get_kb_rate_limiter
from services.knowledge.chunking_service import get_chunking_service
from services.knowledge.document_cleaner import get_document_cleaner
from services.knowledge.document_processor import get_document_processor
from services.llm.qdrant_service import get_qdrant_service

"""
Knowledge Space Service
Author: lycosa9527
Made by: MindSpring Team

Manages user knowledge spaces, document uploads, and processing.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""


logger = logging.getLogger(__name__)


class KnowledgeSpaceService:
    """
    Knowledge space management service.

    Handles document uploads, processing, and deletion with user isolation.
    """

    def __init__(self, db: Session, user_id: int):
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

        # Configuration
        self.max_documents = int(os.getenv("MAX_DOCUMENTS_PER_USER", "5"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", "10485760"))  # 10MB
        self.storage_dir = Path(os.getenv("KNOWLEDGE_STORAGE_DIR", "./storage/knowledge_documents"))
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def create_knowledge_space(self) -> KnowledgeSpace:
        """
        Create or get knowledge space for user.

        Returns:
            KnowledgeSpace instance
        """
        space = self.db.query(KnowledgeSpace).filter(
            KnowledgeSpace.user_id == self.user_id
        ).first()

        if not space:
            space = KnowledgeSpace(user_id=self.user_id)
            self.db.add(space)
            self.db.commit()
            self.db.refresh(space)
            logger.info(f"[KnowledgeSpace] Created knowledge space for user {self.user_id}")

        return space

    def rollback_document(self, document_id: int, version_number: int) -> KnowledgeDocument:
        """
        Rollback document to a previous version.

        Args:
            document_id: Document ID
            version_number: Version number to rollback to

        Returns:
            Rolled back KnowledgeDocument instance
        """
        # Verify ownership
        document = self.db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
            and_(
                KnowledgeDocument.id == document_id,
                KnowledgeSpace.user_id == self.user_id
            )
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        # Get version
        version = self.db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document_id,
            DocumentVersion.version_number == version_number
        ).first()

        if not version:
            raise ValueError(f"Version {version_number} not found for document {document_id}")

        # Check if version file exists
        if not Path(version.file_path).exists():
            raise ValueError(f"Version file not found: {version.file_path}")

        try:
            # Update document status
            document.status = 'processing'
            document.processing_progress = 'rollback'
            document.processing_progress_percent = 0
            self.db.commit()

            # Copy version file to document location
            user_dir = self.storage_dir / str(self.user_id)
            final_path = user_dir / f"{document.id}_{document.file_name}"
            shutil.copy2(version.file_path, final_path)
            document.file_path = str(final_path)
            document.last_updated_hash = version.file_hash
            document.version += 1
            self.db.commit()

            # Reindex from version file
            self._reindex_chunks(document, version.file_hash)

            logger.info(f"[KnowledgeSpace] Rolled back document {document_id} to version {version_number}")
            return document

        except Exception as e:
            logger.error(f"[KnowledgeSpace] Failed to rollback document {document_id}: {e}")
            document.status = 'failed'
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            self.db.commit()
            raise

    def get_document_versions(self, document_id: int) -> List[DocumentVersion]:
        """
        Get all versions for a document.

        Args:
            document_id: Document ID

        Returns:
            List of DocumentVersion instances
        """
        # Verify ownership
        document = self.db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
            and_(
                KnowledgeDocument.id == document_id,
                KnowledgeSpace.user_id == self.user_id
            )
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        return self.db.query(DocumentVersion).filter(
            DocumentVersion.document_id == document_id
        ).order_by(DocumentVersion.version_number.desc()).all()

    def get_document_count(self) -> int:
        """Get current document count for user."""
        space = self.create_knowledge_space()
        return self.db.query(KnowledgeDocument).filter(
            KnowledgeDocument.space_id == space.id
        ).count()

    def upload_document(
        self,
        file_name: str,
        file_path: str,
        file_type: str,
        file_size: int
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
        # Check document limit
        count = self.get_document_count()
        if count >= self.max_documents:
            raise ValueError(f"Maximum {self.max_documents} documents allowed. Please delete a document first.")

        # Check file size
        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({self.max_file_size} bytes)")

        # Check file type
        if not self.processor.is_supported(file_type):
            raise ValueError(f"Unsupported file type: {file_type}")

        # Get or create knowledge space
        space = self.create_knowledge_space()

        # Check for duplicate filename
        existing = self.db.query(KnowledgeDocument).filter(
            and_(
                KnowledgeDocument.space_id == space.id,
                KnowledgeDocument.file_name == file_name
            )
        ).first()

        if existing:
            raise ValueError(f"Document with name '{file_name}' already exists")

        # Move file to storage
        user_dir = self.storage_dir / str(self.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        # Create document record
        document = KnowledgeDocument(
            space_id=space.id,
            file_name=file_name,
            file_path=str(user_dir / file_name),
            file_type=file_type,
            file_size=file_size,
            status='pending'
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)

        # Move file to final location
        final_path = user_dir / f"{document.id}_{file_name}"
        shutil.move(file_path, final_path)
        document.file_path = str(final_path)
        self.db.commit()

        logger.info(
            f"[RAG] ✓ Upload: doc_id={document.id}, file='{file_name}', "
            f"type={file_type}, size={file_size} bytes, user={self.user_id}"
        )
        return document

    def process_document(self, document_id: int) -> None:
        """
        Process document: extract text, chunk, embed, store.

        Args:
            document_id: Document ID
        """
        # Verify ownership
        document = self.db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
            and_(
                KnowledgeDocument.id == document_id,
                KnowledgeSpace.user_id == self.user_id
            )
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        try:
            # Log processing start
            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            logger.info(
                f"[RAG] → Processing: doc_id={document_id}, file='{document.file_name}', "
                f"type={document.file_type}, chunking_engine={chunking_engine}, "
                f"chunking_method={chunking_method}"
            )
            if chunking_method == "mindchunk":
                logger.info(
                    f"[RAG] 🧠 MindChunk ACTIVE: LLM-based semantic chunking will be used "
                    f"for doc_id={document_id}"
                )

            # Update status
            document.status = 'processing'
            document.processing_progress = 'extracting'
            document.processing_progress_percent = 10
            self.db.commit()

            # Extract text and metadata
            try:
                # Extract text with page information for PDFs
                if document.file_type == 'application/pdf':
                    text, page_info = self.processor.extract_text_with_pages(document.file_path, document.file_type)
                else:
                    text = self.processor.extract_text(document.file_path, document.file_type)
                    page_info = None

                # Detect language (ensure text is string before detection)
                if isinstance(text, list):
                    logger.warning(f"[KnowledgeSpace] Text is list, converting to string for doc_id={document_id}")
                    text = "\n".join(str(item) for item in text)
                if not isinstance(text, str):
                    text = str(text) if text else ""
                detected_language = self.processor.detect_language(text)
                if detected_language:
                    document.language = detected_language

                # Extract metadata from document
                extracted_metadata = self.processor.extract_metadata(document.file_path, document.file_type)
                if extracted_metadata:
                    # Merge extracted metadata with existing metadata
                    existing_metadata = document.doc_metadata or {}
                    existing_metadata.update(extracted_metadata)
                    document.doc_metadata = existing_metadata
                    # Extract title for document name if available
                    if 'title' in extracted_metadata and not document.file_name:
                        # Title can be used as a hint, but we keep the original filename
                        pass
                    self.db.commit()
            except Exception as extract_error:
                error_msg = f"文本提取失败: {str(extract_error)}"
                logger.error(f"[KnowledgeSpace] Text extraction failed for document {document_id}: {extract_error}")
                raise ValueError(error_msg) from extract_error

            # Get processing rules from space (if configured)
            space = self.db.query(KnowledgeSpace).filter(KnowledgeSpace.id == document.space_id).first()
            processing_rules = space.processing_rules if space and space.processing_rules else None

            # Clean text with processing rules
            document.processing_progress = 'cleaning'
            document.processing_progress_percent = 20
            self.db.commit()

            try:
                if processing_rules and "rules" in processing_rules:
                    cleaned_text = self.cleaner.clean_with_rules(text, processing_rules.get("rules"))
                else:
                    # Default cleaning
                    cleaned_text = self.cleaner.clean(
                        text,
                        remove_extra_spaces=True,
                        remove_urls_emails=False  # Keep URLs/emails by default
                    )
            except Exception as clean_error:
                error_msg = f"文本清理失败: {str(clean_error)}"
                logger.error(f"[KnowledgeSpace] Text cleaning failed for document {document_id}: {clean_error}")
                raise ValueError(error_msg) from clean_error

            # Determine segmentation mode, strategy, and parameters
            mode = "automatic"
            chunking_strategy = "recursive"
            chunk_size = None
            chunk_overlap = None
            separator = None

            if processing_rules:
                mode = processing_rules.get("mode", "automatic")
                chunking_strategy = processing_rules.get("chunking_strategy", "recursive")
                if "rules" in processing_rules:
                    rules = processing_rules.get("rules", {})
                    if "segmentation" in rules:
                        seg = rules["segmentation"]
                        chunk_size = seg.get("max_tokens", 500)
                        chunk_overlap = seg.get("chunk_overlap", 50)
                        separator = seg.get("separator") or seg.get("delimiter")

            # Log chunking configuration
            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            logger.info(
                f"[RAG] → Chunking: doc_id={document_id}, method={chunking_method} "
                f"(CHUNKING_ENGINE={chunking_engine}), "
                f"mode={mode}, strategy={chunking_strategy}, "
                f"chunk_size={chunk_size or 500}, overlap={chunk_overlap or 50}"
            )
            if chunking_method == "mindchunk":
                logger.info(
                    f"[RAG] 🧠 MindChunk enabled: Using LLM-based semantic chunking "
                    f"with qwen-plus-latest for doc_id={document_id}"
                )

            # Use appropriate chunking service based on mode
            # Note: All modes now respect CHUNKING_ENGINE env var (semchunk vs mindchunk)
            try:
                # Check if we need a custom chunking service instance (for hierarchical/custom modes)
                # or if we can use the default service (respects CHUNKING_ENGINE)
                if mode == "hierarchical":
                    # Hierarchical mode - use custom instance if semchunk, otherwise use default
                    # NOTE: Direct ChunkingService() instantiation only for semchunk in hierarchical mode.
                    # For mindchunk, falls back to self.chunking (which respects CHUNKING_ENGINE).
                    if chunking_engine == "semchunk":
                        from services.knowledge.chunking_service import ChunkingService
                        hierarchical_chunking = ChunkingService(
                            chunk_size=chunk_size or 500,
                            overlap=chunk_overlap or 50,
                            mode="automatic"
                        )
                        chunks = hierarchical_chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                    else:
                        # NOTE: mindchunk (LLM-based chunking) doesn't support hierarchical mode yet.
                        # Hierarchical mode requires parent-child structure detection which is not
                        # fully implemented in LLMSemanticChunker. Falls back to default automatic
                        # chunking mode with mindchunk engine.
                        logger.warning(
                            f"[RAG] Hierarchical mode not supported with mindchunk, "
                            f"falling back to default automatic chunking for doc_id={document_id}"
                        )
                        chunks = self.chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                elif mode == "custom" and (chunk_size or chunk_overlap or separator):
                    # Custom mode with user-defined rules
                    # NOTE: Direct ChunkingService() instantiation only for semchunk in custom mode.
                    # For mindchunk, falls back to self.chunking (which respects CHUNKING_ENGINE).
                    if chunking_engine == "semchunk":
                        from services.knowledge.chunking_service import ChunkingService
                        custom_chunking = ChunkingService(
                            chunk_size=chunk_size or 500,
                            overlap=chunk_overlap or 50,
                            mode="custom"
                        )
                        chunks = custom_chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                    else:
                        # NOTE: mindchunk (LLM-based chunking) doesn't support custom mode yet.
                        # Custom mode requires user-defined chunk_size/overlap/separator which
                        # conflicts with LLM-based semantic boundary detection. Falls back to
                        # default automatic chunking mode with mindchunk engine.
                        logger.warning(
                            f"[RAG] Custom mode not supported with mindchunk, "
                            f"falling back to default automatic chunking for doc_id={document_id}"
                        )
                        chunks = self.chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                else:
                    # Automatic mode (default) - respects CHUNKING_ENGINE via self.chunking
                    # NOTE: Direct ChunkingService() instantiation only for semchunk with non-recursive strategy.
                    # For mindchunk or recursive strategy, uses self.chunking (which respects CHUNKING_ENGINE).
                    if chunking_strategy != "recursive" and chunking_engine == "semchunk":
                        # Only create custom instance for semchunk with non-recursive strategy
                        from services.knowledge.chunking_service import ChunkingService
                        strategy_chunking = ChunkingService(
                            chunk_size=chunk_size or 500,
                            overlap=chunk_overlap or 50,
                            mode="automatic"
                        )
                        chunks = strategy_chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                    else:
                        # Default chunking (respects CHUNKING_ENGINE)
                        logger.info(
                            f"[RAG] Calling chunk_text: doc_id={document_id}, "
                            f"text_length={len(cleaned_text)}, "
                            f"chunking_engine={chunking_engine}, "
                            f"chunking_type={type(self.chunking).__name__}"
                        )
                        chunks = self.chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                        logger.info(
                            f"[RAG] chunk_text returned: doc_id={document_id}, "
                            f"chunks_count={len(chunks) if chunks else 0}, "
                            f"chunks_type={type(chunks).__name__ if chunks else 'None'}"
                        )
            except Exception as chunk_error:
                import traceback
                error_msg = f"文本分块失败: {str(chunk_error)}"
                logger.error(f"[KnowledgeSpace] ✗ Chunking failed for document {document_id}: {chunk_error}")
                logger.error(f"[KnowledgeSpace] Full traceback:")
                logger.error(traceback.format_exc())
                logger.error(f"[KnowledgeSpace] Exception type: {type(chunk_error).__name__}")
                logger.error(f"[KnowledgeSpace] Exception args: {chunk_error.args}")
                raise ValueError(error_msg) from chunk_error

            # Validate chunk count
            if len(chunks) == 0:
                raise ValueError(
                    f"Chunking returned 0 chunks for document {document_id}. "
                    "This may indicate an issue with MindChunk or document content. "
                    "Check logs above for chunking errors."
                )
            if not self.chunking.validate_chunk_count(len(chunks), self.user_id):
                raise ValueError(f"Chunk count ({len(chunks)}) exceeds limit")

            # Log chunking results
            logger.info(
                f"[RAG] ✓ Chunking: doc_id={document_id}, created {len(chunks)} chunks, "
                f"method={chunking_method}, mode={mode}"
            )
            # Debug log for mindchunk metadata compatibility
            if chunking_method == "mindchunk" and chunks:
                sample_chunk = chunks[0]
                logger.debug(
                    f"[RAG] MindChunk sample metadata for doc_id={document_id}: "
                    f"keys={list(sample_chunk.metadata.keys())}, "
                    f"structure_type={sample_chunk.metadata.get('structure_type')}, "
                    f"has_token_count={'token_count' in sample_chunk.metadata}"
                )

            # Update progress: chunking complete
            document.processing_progress = 'chunking'
            document.processing_progress_percent = 40
            self.db.commit()

            # Generate embeddings with caching
            document.processing_progress = 'embedding'
            document.processing_progress_percent = 50
            self.db.commit()

            texts = [chunk.text for chunk in chunks]
            embeddings = []
            from services.llm.embedding_cache import get_embedding_cache
            embedding_cache = get_embedding_cache()

            # Check cache for each text, generate only for uncached
            # Collect all uncached texts first, then check rate limit for batch
            texts_to_embed = []
            indices_to_embed = []
            total_texts = len(texts)
            for i, text in enumerate(texts):
                cached_embedding = embedding_cache.get_document_embedding(self.db, text)
                if cached_embedding:
                    embeddings.append(cached_embedding)
                else:
                    # Add placeholder and collect for batch embedding
                    embeddings.append(None)  # Placeholder
                    texts_to_embed.append(text)
                    indices_to_embed.append(i)

                # Update progress during embedding check (50-70%)
                if total_texts > 0:
                    progress = 50 + int((i + 1) / total_texts * 20)
                    document.processing_progress_percent = progress
                    if i % 10 == 0:  # Commit every 10 chunks to avoid too many DB writes
                        self.db.commit()

            # Generate embeddings for uncached texts
            # Note: embed_texts() handles batching internally, but we need to respect rate limits
            if texts_to_embed:
                from config.settings import config
                from utils.dashscope_error_handler import DashScopeError
                dimensions = config.EMBEDDING_DIMENSIONS  # Will use optimized default (768)

                # Check rate limit for the entire batch upfront
                # embed_texts() batches internally, so we need to estimate how many API calls it will make
                embedding_rpm = int(os.getenv("KB_EMBEDDING_RPM", "100"))
                # Get batch size from embedding client (v4 uses 10, v1/v2 uses 25)
                client_batch_size = getattr(self.embedding_client, 'batch_size', 10)
                estimated_api_calls = (len(texts_to_embed) + client_batch_size - 1) // client_batch_size

                # Check if we have enough rate limit capacity
                # Note: The rate limiter tracks per check_and_record() call, not per API call
                # So we need to check for each batch that embed_texts() will make
                # For now, we check upfront and let embed_texts() handle batching
                # If rate limit is exceeded during processing, embed_texts() will raise an error
                remaining, _ = self.kb_rate_limiter.get_embedding_remaining(self.user_id)
                if remaining < estimated_api_calls:
                    error_msg = (
                        f"嵌入向量生成速率限制: 需要约 {estimated_api_calls} 次API调用（{len(texts_to_embed)} 个文本，"
                        f"批次大小 {client_batch_size}），但当前仅剩 {remaining} 次可用。"
                        f"请稍后重试或增加 KB_EMBEDDING_RPM 配置值（当前: {embedding_rpm}/分钟）。"
                    )
                    logger.error(
                        f"[KnowledgeSpace] Cannot process {len(texts_to_embed)} uncached texts: "
                        f"rate limit insufficient (need ~{estimated_api_calls} API calls, have {remaining} remaining)"
                    )
                    raise ValueError(error_msg)

                try:
                    # embed_texts() handles batching internally and respects API limits
                    new_embeddings = self.embedding_client.embed_texts(
                        texts_to_embed,
                        dimensions=dimensions
                    )

                    # Verify we got embeddings for all texts
                    if len(new_embeddings) != len(texts_to_embed):
                        error_msg = (
                            f"嵌入向量生成不完整: 期望 {len(texts_to_embed)} 个向量，"
                            f"实际生成 {len(new_embeddings)} 个。"
                        )
                        logger.error(
                            f"[KnowledgeSpace] Embedding count mismatch: "
                            f"expected {len(texts_to_embed)}, got {len(new_embeddings)}"
                        )
                        raise ValueError(error_msg)

                    # Store in cache and fill in embeddings list
                    for text, embedding, idx in zip(texts_to_embed, new_embeddings, indices_to_embed):
                        # Cache the embedding
                        embedding_cache.cache_document_embedding(self.db, text, embedding)
                        # Fill in the placeholder
                        embeddings[idx] = embedding

                    logger.debug(
                        f"[KnowledgeSpace] Successfully embedded {len(new_embeddings)} texts "
                        f"for document {document_id}"
                    )
                except DashScopeError as e:
                    # Provide user-friendly error message
                    error_msg = f"生成向量失败: {e.message}"
                    if e.error_type and e.error_type.value == "Arrearage":
                        error_msg = "账号欠费，请充值后重试"
                    elif e.error_type and e.error_type.value == "InvalidApiKey":
                        error_msg = "API密钥无效，请检查配置"
                    elif e.error_type and e.error_type.value == "Throttling":
                        error_msg = "请求频率过高，请稍后重试"
                    raise ValueError(error_msg) from e

            # Update progress: embedding complete
            document.processing_progress_percent = 80
            self.db.commit()
            logger.info(f"[RAG] ✓ Embedding: doc={document_id}, {len(embeddings)} vectors generated")

            if len(embeddings) != len(chunks):
                raise ValueError(f"Embedding count ({len(embeddings)}) != chunk count ({len(chunks)})")

            # Store chunks in database and get IDs BEFORE Qdrant insertion
            document.processing_progress = 'indexing'
            document.processing_progress_percent = 85
            self.db.commit()

            try:
                chunk_ids = []
                for chunk, embedding in zip(chunks, embeddings):
                    db_chunk = DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        text=chunk.text,
                        start_char=chunk.start_char,
                        end_char=chunk.end_char,
                        meta_data=chunk.metadata
                    )
                    self.db.add(db_chunk)
                    self.db.flush()  # Flush to get ID before Qdrant insertion
                    chunk_ids.append(db_chunk.id)
                logger.info(f"[RAG] ✓ Chunking: doc={document_id}, {len(chunk_ids)} chunks saved to SQLite")
            except Exception as chunk_db_error:
                error_msg = f"保存分块数据失败: {str(chunk_db_error)}"
                logger.error(f"[RAG] ✗ Chunking FAILED: doc={document_id}, error={chunk_db_error}")
                raise ValueError(error_msg) from chunk_db_error

            # Now all chunk IDs are generated - safe to insert into Qdrant
            # Use try-except to rollback Qdrant if SQLite commit fails
            try:
                # Store embeddings in Qdrant with document and chunk metadata
                try:
                    # Prepare metadata for Qdrant payload
                    # chunks and chunk_ids are in the same order from the loop above
                    qdrant_metadata = []
                    for chunk, _chunk_id in zip(chunks, chunk_ids):
                        chunk_meta = {}

                        # Document-level metadata
                        if document.category:
                            chunk_meta['category'] = document.category
                        if document.tags:
                            chunk_meta['tags'] = document.tags
                        if document.file_type:
                            chunk_meta['document_type'] = document.file_type

                        # Chunk-level structure metadata
                        if chunk and chunk.metadata:
                            chunk_data = chunk.metadata
                            if 'page_number' in chunk_data:
                                chunk_meta['page_number'] = chunk_data['page_number']
                            if 'section_title' in chunk_data:
                                chunk_meta['section_title'] = chunk_data['section_title']
                            if 'section_level' in chunk_data:
                                chunk_meta['section_level'] = chunk_data['section_level']
                            if 'has_table' in chunk_data:
                                chunk_meta['has_table'] = chunk_data['has_table']
                            if 'has_code' in chunk_data:
                                chunk_meta['has_code'] = chunk_data['has_code']

                        qdrant_metadata.append(chunk_meta)

                    self.qdrant.add_documents(
                        user_id=self.user_id,
                        chunk_ids=chunk_ids,
                        embeddings=embeddings,
                        document_ids=[document.id] * len(chunk_ids),
                        metadata=qdrant_metadata
                    )
                    logger.info(f"[RAG] ✓ Vector Store: doc={document_id}, {len(chunk_ids)} vectors stored in Qdrant")
                except Exception as qdrant_insert_error:
                    error_msg = f"向量存储失败: {str(qdrant_insert_error)}"
                    logger.error(f"[RAG] ✗ Vector Store FAILED: doc={document_id}, error={qdrant_insert_error}")
                    raise ValueError(error_msg) from qdrant_insert_error

                # Update document status
                document.status = 'completed'
                document.chunk_count = len(chunks)
                document.processing_progress = None
                document.processing_progress_percent = 100
                self.db.commit()  # Commit SQLite transaction

            except ValueError:
                # Re-raise ValueError (already has user-friendly message)
                raise
            except Exception as qdrant_error:
                # If Qdrant succeeded but SQLite commit fails, we need to clean up Qdrant
                error_msg = f"数据保存失败: {str(qdrant_error)}"
                logger.error(f"[KnowledgeSpace] Qdrant write succeeded but SQLite commit failed: {qdrant_error}")
                try:
                    # Rollback SQLite transaction
                    self.db.rollback()
                    # Clean up Qdrant vectors (they were added but SQLite failed)
                    self.qdrant.delete_document(self.user_id, document.id)
                    logger.info(f"[KnowledgeSpace] Cleaned up orphaned Qdrant vectors for document {document_id}")
                except Exception as cleanup_error:
                    logger.error(f"[KnowledgeSpace] Failed to cleanup Qdrant after SQLite failure: {cleanup_error}")
                raise ValueError(error_msg) from qdrant_error

            # Log processing completion
            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            logger.info(
                f"[RAG] ✓ Processing complete: doc_id={document_id}, file='{document.file_name}', "
                f"chunks={len(chunks)}, method={chunking_method}, user={self.user_id}"
            )

            # Extract references and create relationships
            try:
                references = self.processor.extract_references(text, document.id)
                for ref in references:
                    # Try to find target document by filename or title
                    # For now, just log - full relationship creation requires document matching logic
                    logger.debug(f"[KnowledgeSpace] Found reference in document {document.id}: {ref['text']}")
            except Exception as ref_error:
                logger.warning(f"[KnowledgeSpace] Failed to extract references for document {document_id}: {ref_error}")

        except Exception as e:
            logger.error(f"[KnowledgeSpace] Failed to process document {document_id}: {e}")
            document.status = 'failed'
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            self.db.commit()
            raise

    def batch_upload_documents(
        self,
        files: List[Dict[str, Any]]
    ) -> DocumentBatch:
        """
        Upload multiple documents in a batch.

        Args:
            files: List of dicts with keys: file_name, file_path, file_type, file_size

        Returns:
            DocumentBatch instance
        """
        if not files:
            raise ValueError("No files provided for batch upload")

        # Check document limit
        current_count = self.get_document_count()
        if current_count + len(files) > self.max_documents:
            raise ValueError(
                f"Cannot upload {len(files)} documents. "
                f"Current count: {current_count}, Max: {self.max_documents}"
            )

        # Validate all files before processing
        for file_info in files:
            file_size = file_info.get('file_size', 0)
            file_type = file_info.get('file_type', '')

            if file_size > self.max_file_size:
                raise ValueError(
                    f"File '{file_info.get('file_name', 'unknown')}' size ({file_size} bytes) "
                    f"exceeds maximum ({self.max_file_size} bytes)"
                )

            if not self.processor.is_supported(file_type):
                raise ValueError(f"Unsupported file type: {file_type} for file '{file_info.get('file_name', 'unknown')}'")

        # Get or create knowledge space
        space = self.create_knowledge_space()

        # Check for duplicate filenames
        existing_filenames = {
            doc.file_name for doc in self.db.query(KnowledgeDocument).filter(
                KnowledgeDocument.space_id == space.id
            ).all()
        }

        for file_info in files:
            file_name = file_info.get('file_name', '')
            if file_name in existing_filenames:
                raise ValueError(f"Document with name '{file_name}' already exists")

        # Create batch record
        batch = DocumentBatch(
            user_id=self.user_id,
            status='pending',
            total_count=len(files),
            completed_count=0,
            failed_count=0
        )
        self.db.add(batch)
        self.db.commit()
        self.db.refresh(batch)

        # Upload all documents
        user_dir = self.storage_dir / str(self.user_id)
        user_dir.mkdir(parents=True, exist_ok=True)

        documents = []
        for file_info in files:
            file_name = file_info['file_name']
            file_path = file_info['file_path']
            file_type = file_info['file_type']
            file_size = file_info['file_size']

            # Create document record
            document = KnowledgeDocument(
                space_id=space.id,
                file_name=file_name,
                file_path=str(user_dir / file_name),
                file_type=file_type,
                file_size=file_size,
                status='pending',
                batch_id=batch.id
            )
            self.db.add(document)
            self.db.flush()

            # Move file to final location
            final_path = user_dir / f"{document.id}_{file_name}"
            shutil.move(file_path, final_path)
            document.file_path = str(final_path)
            documents.append(document)

        self.db.commit()

        logger.info(f"[KnowledgeSpace] Created batch {batch.id} with {len(documents)} documents for user {self.user_id}")
        return batch

    def update_batch_progress(self, batch_id: int, completed: int = 0, failed: int = 0) -> None:
        """
        Update batch processing progress.

        Args:
            batch_id: Batch ID
            completed: Number of completed documents (increment)
            failed: Number of failed documents (increment)
        """
        batch = self.db.query(DocumentBatch).filter(
            DocumentBatch.id == batch_id,
            DocumentBatch.user_id == self.user_id
        ).first()

        if not batch:
            logger.warning(f"[KnowledgeSpace] Batch {batch_id} not found for user {self.user_id}")
            return

        batch.completed_count += completed
        batch.failed_count += failed

        # Update status
        if batch.completed_count + batch.failed_count >= batch.total_count:
            if batch.failed_count == 0:
                batch.status = 'completed'
            elif batch.completed_count == 0:
                batch.status = 'failed'
            else:
                batch.status = 'completed'  # Partial success is still considered completed
        else:
            batch.status = 'processing'

        self.db.commit()

    def delete_document(self, document_id: int) -> None:
        """
        Delete document and all associated data.

        Args:
            document_id: Document ID
        """
        # Verify ownership
        document = self.db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
            and_(
                KnowledgeDocument.id == document_id,
                KnowledgeSpace.user_id == self.user_id
            )
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        try:
            # Delete Qdrant vectors
            self.qdrant.delete_document(self.user_id, document_id)

            # Delete file
            if document.file_path and Path(document.file_path).exists():
                Path(document.file_path).unlink()

            # Delete database records (cascade will handle chunks)
            self.db.delete(document)
            self.db.commit()

            logger.info(f"[KnowledgeSpace] Deleted document {document_id} for user {self.user_id}")

        except Exception as e:
            logger.error(f"[KnowledgeSpace] Failed to delete document {document_id}: {e}")
            self.db.rollback()
            raise

    def get_user_documents(self) -> List[KnowledgeDocument]:
        """Get all documents for user."""
        space = self.create_knowledge_space()
        return self.db.query(KnowledgeDocument).filter(
            KnowledgeDocument.space_id == space.id
        ).order_by(KnowledgeDocument.created_at.desc()).all()

    def get_document(self, document_id: int) -> Optional[KnowledgeDocument]:
        """
        Get document by ID (with ownership check).

        Args:
            document_id: Document ID

        Returns:
            KnowledgeDocument or None
        """
        return self.db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
            and_(
                KnowledgeDocument.id == document_id,
                KnowledgeSpace.user_id == self.user_id
            )
        ).first()

    def _calculate_content_hash(self, file_path: str) -> str:
        """
        Calculate hash of file content for change detection.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash string
        """
        with open(file_path, 'rb') as f:
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
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    def update_document(
        self,
        document_id: int,
        file_path: str,
        file_name: Optional[str] = None
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
        # Verify ownership
        document = self.db.query(KnowledgeDocument).join(KnowledgeSpace).filter(
            and_(
                KnowledgeDocument.id == document_id,
                KnowledgeSpace.user_id == self.user_id
            )
        ).first()

        if not document:
            raise ValueError(f"Document {document_id} not found or access denied")

        # Log update start
        logger.info(
            f"[RAG] → Update: doc_id={document_id}, file='{document.file_name}', "
            f"new_file='{file_name or document.file_name}', type={document.file_type}, user={self.user_id}"
        )

        # Check file size
        file_size = Path(file_path).stat().st_size
        if file_size > self.max_file_size:
            raise ValueError(f"File size ({file_size} bytes) exceeds maximum ({self.max_file_size} bytes)")

        # Get file type
        file_type = self.processor.get_file_type(file_path)

        # Check file type compatibility
        if file_type != document.file_type:
            logger.warning(
                f"[KnowledgeSpace] File type changed from {document.file_type} to {file_type} "
                f"for document {document_id}. Full reindexing will be performed."
            )

        # Calculate content hash
        new_content_hash = self._calculate_content_hash(file_path)

        # Check if content actually changed
        if document.last_updated_hash == new_content_hash:
            logger.info(f"[KnowledgeSpace] Document {document_id} content unchanged, skipping update")
            return document

        try:
            # Update document metadata
            document.status = 'processing'
            document.processing_progress = 'updating'
            document.processing_progress_percent = 0
            if file_name:
                document.file_name = file_name
            document.file_size = file_size
            document.file_type = file_type
            document.version += 1
            self.db.commit()

            # Move new file to storage location
            user_dir = self.storage_dir / str(self.user_id)
            user_dir.mkdir(parents=True, exist_ok=True)

            # Backup old file path
            old_file_path = document.file_path

            # Move new file to final location
            final_path = user_dir / f"{document.id}_{document.file_name}"
            shutil.move(file_path, final_path)
            document.file_path = str(final_path)
            self.db.commit()

            # Create version from old document before updating
            try:
                # Copy old file to version storage
                version_dir = self.storage_dir / str(self.user_id) / "versions" / str(document.id)
                version_dir.mkdir(parents=True, exist_ok=True)

                # Get old file hash
                old_file_hash = document.last_updated_hash or self._calculate_content_hash(old_file_path)

                # Copy old file to version location
                version_file_path = version_dir / f"v{document.version}_{document.file_name}"
                if Path(old_file_path).exists():
                    shutil.copy2(old_file_path, version_file_path)

                    # Create version record
                    version = DocumentVersion(
                        document_id=document.id,
                        version_number=document.version,  # Current version before increment
                        file_path=str(version_file_path),
                        file_hash=old_file_hash,
                        chunk_count=document.chunk_count or 0,
                        created_by=self.user_id
                    )
                    self.db.add(version)
                    self.db.commit()
                    logger.info(f"[KnowledgeSpace] Created version {document.version} for document {document.id}")
            except Exception as version_error:
                logger.warning(f"[KnowledgeSpace] Failed to create version for document {document.id}: {version_error}")
                # Continue with update even if version creation fails

            # Delete old file if different
            if old_file_path != document.file_path and Path(old_file_path).exists():
                try:
                    Path(old_file_path).unlink()
                except Exception as e:
                    logger.warning(f"[KnowledgeSpace] Failed to delete old file {old_file_path}: {e}")

            # Perform reindexing and track changes
            change_summary = self._reindex_chunks(document, new_content_hash)

            # Update version change summary if version was created
            if 'version' in locals() and change_summary:
                version.change_summary = change_summary
                self.db.commit()

            # Log update completion
            logger.info(
                f"[RAG] ✓ Update complete: doc_id={document_id}, version={document.version}, "
                f"chunks={document.chunk_count}, user={self.user_id}"
            )
            return document

        except Exception as e:
            logger.error(f"[KnowledgeSpace] Failed to update document {document_id}: {e}")
            document.status = 'failed'
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            self.db.commit()
            raise

    def _reindex_chunks(
        self,
        document: KnowledgeDocument,
        content_hash: str
    ) -> Dict[str, int]:
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
            # Update status
            document.processing_progress = 'extracting'
            document.processing_progress_percent = 10
            self.db.commit()

            # Extract text from new file with page information
            try:
                # Extract text with page information for PDFs
                if document.file_type == 'application/pdf':
                    text, page_info = self.processor.extract_text_with_pages(document.file_path, document.file_type)
                else:
                    text = self.processor.extract_text(document.file_path, document.file_type)
                    page_info = None

                # Ensure text is a string (defensive check)
                if isinstance(text, list):
                    logger.warning(f"[KnowledgeSpace] Text extraction returned list for doc_id={document.id}, converting")
                    text = "\n".join(str(item) for item in text)
                if not isinstance(text, str):
                    text = str(text) if text else ""
            except Exception as extract_error:
                error_msg = f"文本提取失败: {str(extract_error)}"
                logger.error(
                    f"[KnowledgeSpace] Text extraction failed for document {document.id}: {extract_error}",
                    exc_info=True
                )
                raise ValueError(error_msg) from extract_error

            # Get processing rules
            space = self.db.query(KnowledgeSpace).filter(KnowledgeSpace.id == document.space_id).first()
            processing_rules = space.processing_rules if space and space.processing_rules else None

            # Clean text
            document.processing_progress = 'cleaning'
            document.processing_progress_percent = 20
            self.db.commit()

            try:
                if processing_rules and "rules" in processing_rules:
                    cleaned_text = self.cleaner.clean_with_rules(text, processing_rules.get("rules"))
                else:
                    cleaned_text = self.cleaner.clean(
                        text,
                        remove_extra_spaces=True,
                        remove_urls_emails=False
                    )
            except Exception as clean_error:
                error_msg = f"文本清理失败: {str(clean_error)}"
                logger.error(f"[KnowledgeSpace] Text cleaning failed for document {document.id}: {clean_error}")
                raise ValueError(error_msg) from clean_error

            # Determine segmentation mode
            mode = "automatic"
            chunk_size = None
            chunk_overlap = None
            separator = None

            if processing_rules:
                mode = processing_rules.get("mode", "automatic")
                if "rules" in processing_rules:
                    rules = processing_rules.get("rules", {})
                    if "segmentation" in rules:
                        seg = rules["segmentation"]
                        chunk_size = seg.get("max_tokens", 500)
                        chunk_overlap = seg.get("chunk_overlap", 50)
                        separator = seg.get("separator") or seg.get("delimiter")

            # Log chunking configuration for update
            chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
            chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
            logger.info(
                f"[RAG] → Chunking (update): doc_id={document.id}, method={chunking_method}, "
                f"mode={mode}, chunk_size={chunk_size or 500}, overlap={chunk_overlap or 50}"
            )

            # Chunk text
            document.processing_progress = 'chunking'
            document.processing_progress_percent = 30
            self.db.commit()

            try:
                # Check chunking engine to determine which service to use
                if mode == "hierarchical":
                    # NOTE: Direct ChunkingService() instantiation only for semchunk in hierarchical mode.
                    # For mindchunk, falls back to self.chunking (which respects CHUNKING_ENGINE).
                    if chunking_engine == "semchunk":
                        from services.knowledge.chunking_service import ChunkingService
                        hierarchical_chunking = ChunkingService(
                            chunk_size=chunk_size or 500,
                            overlap=chunk_overlap or 50,
                            mode="hierarchical"
                        )
                        new_chunks = hierarchical_chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                    else:
                        # NOTE: mindchunk (LLM-based chunking) doesn't support hierarchical mode yet.
                        # Hierarchical mode requires parent-child structure detection which is not
                        # fully implemented in LLMSemanticChunker. Falls back to default automatic
                        # chunking mode with mindchunk engine.
                        logger.warning(
                            f"[RAG] Hierarchical mode not supported with mindchunk, "
                            f"falling back to default automatic chunking for doc_id={document.id}"
                        )
                        new_chunks = self.chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                elif mode == "custom" and (chunk_size or chunk_overlap or separator):
                    # NOTE: Direct ChunkingService() instantiation only for semchunk in custom mode.
                    # For mindchunk, falls back to self.chunking (which respects CHUNKING_ENGINE).
                    if chunking_engine == "semchunk":
                        from services.knowledge.chunking_service import ChunkingService
                        custom_chunking = ChunkingService(
                            chunk_size=chunk_size or 500,
                            overlap=chunk_overlap or 50,
                            mode="custom"
                        )
                        new_chunks = custom_chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                    else:
                        # NOTE: mindchunk (LLM-based chunking) doesn't support custom mode yet.
                        # Custom mode requires user-defined chunk_size/overlap/separator which
                        # conflicts with LLM-based semantic boundary detection. Falls back to
                        # default automatic chunking mode with mindchunk engine.
                        logger.warning(
                            f"[RAG] Custom mode not supported with mindchunk, "
                            f"falling back to default automatic chunking for doc_id={document.id}"
                        )
                        new_chunks = self.chunking.chunk_text(
                            cleaned_text,
                            metadata={"document_id": document.id},
                            separator=separator,
                            extract_structure=True,
                            page_info=page_info,
                            language=document.language
                        )
                else:
                    # Default chunking (respects CHUNKING_ENGINE)
                    new_chunks = self.chunking.chunk_text(
                        cleaned_text,
                        metadata={"document_id": document.id},
                        separator=separator,
                        extract_structure=True,
                        page_info=page_info,
                        language=document.language
                    )
            except Exception as chunk_error:
                error_msg = f"文本分块失败: {str(chunk_error)}"
                logger.error(f"[KnowledgeSpace] Chunking failed for document {document.id}: {chunk_error}")
                raise ValueError(error_msg) from chunk_error

            # Validate chunk count
            if not self.chunking.validate_chunk_count(len(new_chunks), self.user_id):
                raise ValueError(f"Chunk count ({len(new_chunks)}) exceeds limit")

            # Log chunking results for update
            logger.info(
                f"[RAG] ✓ Chunking (update): doc_id={document.id}, created {len(new_chunks)} chunks, "
                f"method={chunking_method}, mode={mode}"
            )

            # Get existing chunks
            existing_chunks = self.db.query(DocumentChunk).filter(
                DocumentChunk.document_id == document.id
            ).order_by(DocumentChunk.chunk_index).all()

            # Build hash map of existing chunks (by chunk_index and text hash)
            existing_chunk_map: Dict[int, DocumentChunk] = {}
            existing_chunk_hashes: Dict[int, str] = {}
            for chunk in existing_chunks:
                existing_chunk_map[chunk.chunk_index] = chunk
                existing_chunk_hashes[chunk.chunk_index] = self._calculate_chunk_hash(chunk.text)

            # Compare new chunks with existing chunks
            chunks_to_add: List = []
            chunks_to_update: List = []
            chunks_to_delete: Set[int] = set(existing_chunk_map.keys())

            document.processing_progress = 'comparing'
            document.processing_progress_percent = 40
            self.db.commit()

            for i, new_chunk in enumerate(new_chunks):
                new_chunk_hash = self._calculate_chunk_hash(new_chunk.text)

                if i in existing_chunk_map:
                    # Chunk at this index exists
                    existing_hash = existing_chunk_hashes[i]
                    if new_chunk_hash == existing_hash:
                        # Chunk unchanged, keep it
                        chunks_to_delete.discard(i)
                    else:
                        # Chunk changed, update it
                        chunks_to_update.append((i, new_chunk, new_chunk_hash))
                        chunks_to_delete.discard(i)
                else:
                    # New chunk
                    chunks_to_add.append((i, new_chunk, new_chunk_hash))

            # Log chunk comparison results
            logger.info(
                f"[RAG] ✓ Chunk comparison: doc_id={document.id}, "
                f"added={len(chunks_to_add)}, updated={len(chunks_to_update)}, deleted={len(chunks_to_delete)}"
            )

            # Delete removed chunks
            if chunks_to_delete:
                chunk_ids_to_delete = [existing_chunk_map[i].id for i in chunks_to_delete]
                # Delete from Qdrant
                self.qdrant.delete_chunks(self.user_id, chunk_ids_to_delete)
                # Delete from database
                self.db.query(DocumentChunk).filter(
                    DocumentChunk.id.in_(chunk_ids_to_delete)
                ).delete(synchronize_session=False)
                self.db.commit()

            # Update changed chunks
            if chunks_to_update:
                document.processing_progress = 'updating_chunks'
                document.processing_progress_percent = 50
                self.db.commit()

                updated_chunk_ids = []
                updated_embeddings = []
                updated_texts = []
                updated_chunks = []  # Track chunks for metadata preparation

                from services.llm.embedding_cache import get_embedding_cache
                embedding_cache = get_embedding_cache()

                for chunk_index, new_chunk, _chunk_hash in chunks_to_update:
                    existing_chunk = existing_chunk_map[chunk_index]

                    # Get or generate embedding
                    cached_embedding = embedding_cache.get_document_embedding(self.db, new_chunk.text)
                    if not cached_embedding:
                        # Check rate limit
                        allowed, _count, error_msg = self.kb_rate_limiter.check_embedding_limit(self.user_id)
                        if not allowed:
                            logger.warning(
                                f"[KnowledgeSpace] Embedding rate limit exceeded during update. "
                                f"Skipping remaining chunks."
                            )
                            break

                        # Generate embedding
                        from config.settings import config
                        dimensions = config.EMBEDDING_DIMENSIONS
                        try:
                            embeddings = self.embedding_client.embed_texts([new_chunk.text], dimensions=dimensions)
                            if embeddings:
                                cached_embedding = embeddings[0]
                                embedding_cache.cache_document_embedding(self.db, new_chunk.text, cached_embedding)
                        except Exception as e:
                            logger.error(f"[KnowledgeSpace] Failed to generate embedding for chunk {chunk_index}: {e}")
                            continue

                    if cached_embedding:
                        # Update chunk in database
                        existing_chunk.text = new_chunk.text
                        existing_chunk.start_char = new_chunk.start_char
                        existing_chunk.end_char = new_chunk.end_char
                        existing_chunk.meta_data = new_chunk.metadata or {}

                        updated_chunk_ids.append(existing_chunk.id)
                        updated_embeddings.append(cached_embedding)
                        updated_texts.append(new_chunk.text)
                        updated_chunks.append(new_chunk)  # Track chunk for metadata

                # Update Qdrant vectors with metadata
                if updated_chunk_ids:
                    # Prepare metadata for updated chunks
                    # updated_chunk_ids and updated_chunks are in the same order
                    updated_metadata = []
                    for chunk, _chunk_id in zip(updated_chunks, updated_chunk_ids):
                        chunk_meta = {}

                        # Document-level metadata
                        if document.category:
                            chunk_meta['category'] = document.category
                        if document.tags:
                            chunk_meta['tags'] = document.tags
                        if document.file_type:
                            chunk_meta['document_type'] = document.file_type

                        # Chunk-level structure metadata
                        if chunk and chunk.metadata:
                            chunk_data = chunk.metadata
                            if 'page_number' in chunk_data:
                                chunk_meta['page_number'] = chunk_data['page_number']
                            if 'section_title' in chunk_data:
                                chunk_meta['section_title'] = chunk_data['section_title']
                            if 'section_level' in chunk_data:
                                chunk_meta['section_level'] = chunk_data['section_level']
                            if 'has_table' in chunk_data:
                                chunk_meta['has_table'] = chunk_data['has_table']
                            if 'has_code' in chunk_data:
                                chunk_meta['has_code'] = chunk_data['has_code']

                        updated_metadata.append(chunk_meta)

                    self.qdrant.update_documents(
                        user_id=self.user_id,
                        chunk_ids=updated_chunk_ids,
                        embeddings=updated_embeddings,
                        document_ids=[document.id] * len(updated_chunk_ids),
                        metadata=updated_metadata
                    )
                    self.db.commit()

            # Add new chunks
            if chunks_to_add:
                document.processing_progress = 'adding_chunks'
                document.processing_progress_percent = 70
                self.db.commit()

                new_chunk_ids = []
                new_embeddings = []
                new_texts = []
                new_chunks_list = []  # Track chunks for metadata preparation

                from services.llm.embedding_cache import get_embedding_cache
                embedding_cache = get_embedding_cache()

                for chunk_index, new_chunk, chunk_hash in chunks_to_add:
                    # Get or generate embedding
                    cached_embedding = embedding_cache.get_document_embedding(self.db, new_chunk.text)
                    if not cached_embedding:
                        # Check rate limit
                        allowed, _count, error_msg = self.kb_rate_limiter.check_embedding_limit(self.user_id)
                        if not allowed:
                            logger.warning(
                                f"[KnowledgeSpace] Embedding rate limit exceeded during update. "
                                f"Skipping remaining chunks."
                            )
                            break

                        # Generate embedding
                        from config.settings import config
                        dimensions = config.EMBEDDING_DIMENSIONS
                        try:
                            embeddings = self.embedding_client.embed_texts([new_chunk.text], dimensions=dimensions)
                            if embeddings:
                                cached_embedding = embeddings[0]
                                embedding_cache.cache_document_embedding(self.db, new_chunk.text, cached_embedding)
                        except Exception as e:
                            logger.error(f"[KnowledgeSpace] Failed to generate embedding for new chunk {chunk_index}: {e}")
                            continue

                    if cached_embedding:
                        # Create chunk in database
                        db_chunk = DocumentChunk(
                            document_id=document.id,
                            chunk_index=chunk_index,
                            text=new_chunk.text,
                            start_char=new_chunk.start_char,
                            end_char=new_chunk.end_char,
                            meta_data=new_chunk.metadata
                        )
                        self.db.add(db_chunk)
                        self.db.flush()

                        new_chunk_ids.append(db_chunk.id)
                        new_embeddings.append(cached_embedding)
                        new_texts.append(new_chunk.text)
                        new_chunks_list.append(new_chunk)  # Track chunk for metadata

                # Add to Qdrant with metadata
                if new_chunk_ids:
                    # Prepare metadata for new chunks
                    # new_chunk_ids and new_chunks_list are in the same order
                    new_metadata = []
                    for chunk_id, chunk in zip(new_chunk_ids, new_chunks_list):
                        chunk_meta = {}

                        # Document-level metadata
                        if document.category:
                            chunk_meta['category'] = document.category
                        if document.tags:
                            chunk_meta['tags'] = document.tags
                        if document.file_type:
                            chunk_meta['document_type'] = document.file_type

                        # Chunk-level structure metadata
                        if chunk and chunk.metadata:
                            chunk_data = chunk.metadata
                            if 'page_number' in chunk_data:
                                chunk_meta['page_number'] = chunk_data['page_number']
                            if 'section_title' in chunk_data:
                                chunk_meta['section_title'] = chunk_data['section_title']
                            if 'section_level' in chunk_data:
                                chunk_meta['section_level'] = chunk_data['section_level']
                            if 'has_table' in chunk_data:
                                chunk_meta['has_table'] = chunk_data['has_table']
                            if 'has_code' in chunk_data:
                                chunk_meta['has_code'] = chunk_data['has_code']

                        new_metadata.append(chunk_meta)

                    self.qdrant.add_documents(
                        user_id=self.user_id,
                        chunk_ids=new_chunk_ids,
                        embeddings=new_embeddings,
                        document_ids=[document.id] * len(new_chunk_ids),
                        metadata=new_metadata
                    )
                    self.db.commit()

            # Update document status
            document.status = 'completed'
            document.chunk_count = len(new_chunks)
            document.last_updated_hash = content_hash
            document.processing_progress = None
            document.processing_progress_percent = 100
            self.db.commit()

            change_summary = {
                "added": len(chunks_to_add),
                "updated": len(chunks_to_update),
                "deleted": len(chunks_to_delete)
            }

            # Log reindexing completion
            logger.info(
                f"[RAG] ✓ Reindexing complete: doc_id={document.id}, "
                f"added={change_summary['added']}, updated={change_summary['updated']}, "
                f"deleted={change_summary['deleted']}, total_chunks={document.chunk_count}"
            )

            return change_summary

        except Exception as e:
            logger.error(f"[KnowledgeSpace] Failed to reindex chunks for document {document.id}: {e}")
            document.status = 'failed'
            document.error_message = str(e)
            document.processing_progress = None
            document.processing_progress_percent = 0
            self.db.commit()
            # Return empty change summary on error
            return {"added": 0, "updated": 0, "deleted": 0}
