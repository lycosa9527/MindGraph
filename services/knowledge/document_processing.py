"""Document processing helper functions.

Extracted from knowledge_space_service.py to reduce complexity.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple

from config.settings import config
from models.domain.knowledge_space import KnowledgeDocument
from services.knowledge.chunking_service import ChunkingService
from services.knowledge.document_structure import (
    StructureHeading,
    extract_docx_headings,
    extract_document_structure,
)
from services.knowledge.knowledge_settings import segmentation_from_rules, server_defaults
from services.llm.embedding_cache import get_embedding_cache
from services.utils.error_types import QDRANT_ERRORS
from utils.dashscope_error_handler import DashScopeError

logger = logging.getLogger(__name__)


async def extract_and_clean_text(
    processor,
    cleaner,
    document: KnowledgeDocument,
    db,
    processing_rules: Optional[dict],
) -> Tuple[str, Optional[List[Dict[str, Any]]], List[StructureHeading]]:
    """
    Extract and clean text from document.

    Returns:
        Tuple of (cleaned_text, page_info, structure_headings)
    """
    structure_headings: List[StructureHeading] = []
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if document.file_type == "application/pdf":
        text, page_info = processor.extract_text_with_pages(document.file_path, document.file_type)
        structure_headings = extract_document_structure(document.file_path, document.file_type)
    elif document.file_type == docx:
        text, structure_headings = extract_docx_headings(document.file_path)
        page_info = None
    else:
        text = processor.extract_text(document.file_path, document.file_type)
        page_info = None

    # Detect language (ensure text is string before detection)
    if isinstance(text, list):
        logger.warning(
            "[KnowledgeSpace] Text is list, converting to string for doc_id=%s",
            document.id,
        )
        text = "\n".join(str(item) for item in text)
    if not isinstance(text, str):
        text = str(text) if text else ""
    detected_language = processor.detect_language(text)
    if detected_language:
        document.language = detected_language

    # Extract metadata from document
    extracted_metadata = processor.extract_metadata(document.file_path, document.file_type)
    if extracted_metadata:
        # Merge extracted metadata with existing metadata
        existing_metadata = document.doc_metadata or {}
        existing_metadata.update(extracted_metadata)
        document.doc_metadata = existing_metadata
        await db.commit()

    # Clean text with processing rules
    try:
        if processing_rules and "rules" in processing_rules:
            cleaned_text = cleaner.clean_with_rules(text, processing_rules.get("rules"))
        else:
            # Default cleaning
            cleaned_text = cleaner.clean(
                text,
                remove_extra_spaces=True,
                remove_urls_emails=False,  # Keep URLs/emails by default
            )
    except QDRANT_ERRORS as clean_error:
        error_msg = f"文本清理失败: {str(clean_error)}"
        logger.error(
            "[KnowledgeSpace] Text cleaning failed for document %s: %s",
            document.id,
            clean_error,
        )
        raise ValueError(error_msg) from clean_error

    return cleaned_text, page_info, structure_headings


async def chunk_text_with_mode(
    chunking_service,
    cleaned_text: str,
    document: KnowledgeDocument,
    processing_rules: Optional[dict],
    page_info: Optional[List[Dict[str, Any]]],
    document_id: int,
    structure_headings: Optional[List[StructureHeading]] = None,
) -> List[Any]:
    """
    Chunk text based on processing mode and rules.

    Args:
        chunking_service: Default chunking service instance
        cleaned_text: Cleaned text to chunk
        document: KnowledgeDocument instance
        processing_rules: Optional processing rules
        page_info: Optional page information
        document_id: Document ID for logging

    Returns:
        List of chunks
    """
    # Determine segmentation mode, strategy, and parameters
    mode = "automatic"
    chunking_strategy = "recursive"
    chunk_size = None
    chunk_overlap = None
    separator = None

    if processing_rules:
        mode = processing_rules.get("mode", "automatic")
        chunking_strategy = processing_rules.get("chunking_strategy", "recursive")
        chunk_size, chunk_overlap = segmentation_from_rules(processing_rules)
        rules = processing_rules.get("rules") or {}
        segmentation = rules.get("segmentation") or {}
        separator = segmentation.get("separator") or segmentation.get("delimiter")
    else:
        defaults = server_defaults()
        chunk_size = defaults["chunk_size"]
        chunk_overlap = defaults["chunk_overlap"]

    logger.info(
        "[RAG] → Chunking: doc_id=%s, method=semchunk, mode=%s, strategy=%s, chunk_size=%s, overlap=%s",
        document_id,
        mode,
        chunking_strategy,
        chunk_size or 500,
        chunk_overlap or 50,
    )

    def _chunk(service_mode: str, include_headings: bool) -> List[Any]:
        service = ChunkingService(
            chunk_size=chunk_size or 500,
            overlap=chunk_overlap or 50,
            mode=service_mode,
        )
        return service.chunk_text(
            cleaned_text,
            metadata={"document_id": document.id},
            separator=separator,
            extract_structure=True,
            page_info=page_info,
            language=document.language,
            structure_headings=structure_headings if include_headings else None,
        )

    try:
        if mode == "hierarchical":
            chunks = _chunk("hierarchical", True)
        elif mode == "custom" and (chunk_size or chunk_overlap or separator):
            chunks = _chunk("custom", True)
        elif chunking_strategy != "recursive":
            chunks = _chunk("automatic", False)
        else:
            chunks = chunking_service.chunk_text(
                text=cleaned_text,
                metadata={"document_id": document.id},
                separator=separator,
                extract_structure=True,
                page_info=page_info,
                language=document.language,
                structure_headings=structure_headings,
            )
    except QDRANT_ERRORS as chunk_error:
        error_msg = f"文本分块失败: {str(chunk_error)}"
        logger.error(
            "[KnowledgeSpace] ✗ Chunking failed for document %s: %s",
            document_id,
            chunk_error,
        )
        logger.error("[KnowledgeSpace] Full traceback:")
        logger.error(traceback.format_exc())
        logger.error("[KnowledgeSpace] Exception type: %s", type(chunk_error).__name__)
        logger.error("[KnowledgeSpace] Exception args: %s", chunk_error.args)
        raise ValueError(error_msg) from chunk_error

    return chunks


async def generate_embeddings_with_cache(
    embedding_client, kb_rate_limiter, texts: List[str], user_id: int, db
) -> List[List[float]]:
    """
    Generate embeddings with caching and rate limiting.

    Args:
        embedding_client: Embedding client instance
        kb_rate_limiter: Rate limiter instance
        texts: List of texts to embed
        user_id: User ID
        db: Database session

    Returns:
        List of embeddings
    """
    embeddings = []
    embedding_cache = get_embedding_cache()

    # Check cache for each text, generate only for uncached
    texts_to_embed = []
    indices_to_embed = []
    for i, text in enumerate(texts):
        cached_embedding = await embedding_cache.get_document_embedding(db, text)
        if cached_embedding:
            embeddings.append(cached_embedding)
        else:
            # Add placeholder and collect for batch embedding
            embeddings.append(None)  # Placeholder
            texts_to_embed.append(text)
            indices_to_embed.append(i)

    # Generate embeddings for uncached texts
    if texts_to_embed:
        dimensions = config.EMBEDDING_DIMENSIONS

        # Check rate limit for the entire batch upfront
        embedding_rpm = int(os.getenv("KB_EMBEDDING_RPM", "100"))
        client_batch_size = getattr(embedding_client, "batch_size", 10)
        estimated_api_calls = (len(texts_to_embed) + client_batch_size - 1) // client_batch_size

        remaining, _ = await kb_rate_limiter.get_embedding_remaining(user_id)
        if remaining < estimated_api_calls:
            error_msg = (
                f"嵌入向量生成速率限制: 需要约 {estimated_api_calls} 次API调用（{len(texts_to_embed)} 个文本，"
                f"批次大小 {client_batch_size}），但当前仅剩 {remaining} 次可用。"
                f"请稍后重试或增加 KB_EMBEDDING_RPM 配置值（当前: {embedding_rpm}/分钟）。"
            )
            logger.error(
                "[KnowledgeSpace] Cannot process %s uncached texts: "
                "rate limit insufficient (need ~%s API calls, have %s remaining)",
                len(texts_to_embed),
                estimated_api_calls,
                remaining,
            )
            raise ValueError(error_msg)

        try:
            new_embeddings = await embedding_client.embed_texts(texts_to_embed, dimensions=dimensions)

            # Verify we got embeddings for all texts
            if len(new_embeddings) != len(texts_to_embed):
                error_msg = (
                    f"嵌入向量生成不完整: 期望 {len(texts_to_embed)} 个向量，实际生成 {len(new_embeddings)} 个。"
                )
                logger.error(
                    "[KnowledgeSpace] Embedding count mismatch: expected %s, got %s",
                    len(texts_to_embed),
                    len(new_embeddings),
                )
                raise ValueError(error_msg)

            # Store in cache and fill in embeddings list
            for text, embedding, idx in zip(texts_to_embed, new_embeddings, indices_to_embed):
                await embedding_cache.cache_document_embedding(db, text, embedding)
                embeddings[idx] = embedding

            logger.debug("[KnowledgeSpace] Successfully embedded %s texts", len(new_embeddings))
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

    return embeddings
