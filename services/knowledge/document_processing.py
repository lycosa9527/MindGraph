"""Document processing helper functions.

Extracted from knowledge_space_service.py to reduce complexity.
"""
import logging
import os
import traceback
from typing import List, Optional, Tuple, Any, Dict

from config.settings import config
from utils.dashscope_error_handler import DashScopeError
from models.domain.knowledge_space import KnowledgeDocument
from services.knowledge.chunking_service import ChunkingService
from services.llm.embedding_cache import get_embedding_cache


logger = logging.getLogger(__name__)


def extract_and_clean_text(
    processor,
    cleaner,
    document: KnowledgeDocument,
    db,
    processing_rules: Optional[dict]
) -> Tuple[str, Optional[List[Dict[str, Any]]]]:
    """
    Extract and clean text from document.

    Args:
        processor: Document processor instance
        cleaner: Document cleaner instance
        document: KnowledgeDocument instance
        db: Database session
        processing_rules: Optional processing rules

    Returns:
        Tuple of (cleaned_text, page_info)
    """
    # Extract text with page information for PDFs
    if document.file_type == 'application/pdf':
        text, page_info = processor.extract_text_with_pages(document.file_path, document.file_type)
    else:
        text = processor.extract_text(document.file_path, document.file_type)
        page_info = None

    # Detect language (ensure text is string before detection)
    if isinstance(text, list):
        logger.warning(
            "[KnowledgeSpace] Text is list, converting to string for doc_id=%s",
            document.id
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
        db.commit()

    # Clean text with processing rules
    try:
        if processing_rules and "rules" in processing_rules:
            cleaned_text = cleaner.clean_with_rules(text, processing_rules.get("rules"))
        else:
            # Default cleaning
            cleaned_text = cleaner.clean(
                text,
                remove_extra_spaces=True,
                remove_urls_emails=False  # Keep URLs/emails by default
            )
    except Exception as clean_error:
        error_msg = f"文本清理失败: {str(clean_error)}"
        logger.error(
            "[KnowledgeSpace] Text cleaning failed for document %s: %s",
            document.id, clean_error
        )
        raise ValueError(error_msg) from clean_error

    return cleaned_text, page_info


def chunk_text_with_mode(
    chunking_service,
    cleaned_text: str,
    document: KnowledgeDocument,
    processing_rules: Optional[dict],
    page_info: Optional[List[Dict[str, Any]]],
    document_id: int
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
        "[RAG] → Chunking: doc_id=%s, method=%s (CHUNKING_ENGINE=%s), mode=%s, strategy=%s, "
        "chunk_size=%s, overlap=%s",
        document_id, chunking_method, chunking_engine, mode, chunking_strategy,
        chunk_size or 500, chunk_overlap or 50
    )
    if chunking_method == "mindchunk":
        logger.info(
            "[RAG] 🧠 MindChunk enabled: Using LLM-based semantic chunking with "
            "qwen-plus-latest for doc_id=%s",
            document_id
        )

    # Use appropriate chunking service based on mode
    try:
        if mode == "hierarchical":
            if chunking_engine == "semchunk":
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
                logger.warning(
                    "[RAG] Hierarchical mode not supported with mindchunk, "
                    "falling back to default automatic chunking for doc_id=%s",
                    document_id
                )
                chunks = chunking_service.chunk_text(
                    cleaned_text,
                    metadata={"document_id": document.id},
                    separator=separator,
                    extract_structure=True,
                    page_info=page_info,
                    language=document.language
                )
        elif mode == "custom" and (chunk_size or chunk_overlap or separator):
            if chunking_engine == "semchunk":
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
                logger.warning(
                    "[RAG] Custom mode not supported with mindchunk, "
                    "falling back to default automatic chunking for doc_id=%s",
                    document_id
                )
                chunks = chunking_service.chunk_text(
                    cleaned_text,
                    metadata={"document_id": document.id},
                    separator=separator,
                    extract_structure=True,
                    page_info=page_info,
                    language=document.language
                )
        else:
            # Automatic mode (default) - respects CHUNKING_ENGINE via chunking_service
            if chunking_strategy != "recursive" and chunking_engine == "semchunk":
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
                chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
                logger.info(
                    "[RAG] Calling chunk_text: doc_id=%s, text_length=%s, chunking_engine=%s, "
                    "chunking_type=%s",
                    document_id, len(cleaned_text), chunking_engine,
                    type(chunking_service).__name__
                )
                chunks = chunking_service.chunk_text(
                    cleaned_text,
                    metadata={"document_id": document.id},
                    separator=separator,
                    extract_structure=True,
                    page_info=page_info,
                    language=document.language
                )
                logger.info(
                    "[RAG] chunk_text returned: doc_id=%s, chunks_count=%s, chunks_type=%s",
                    document_id, len(chunks) if chunks else 0,
                    type(chunks).__name__ if chunks else 'None'
                )
    except Exception as chunk_error:
        error_msg = f"文本分块失败: {str(chunk_error)}"
        logger.error(
            "[KnowledgeSpace] ✗ Chunking failed for document %s: %s",
            document_id, chunk_error
        )
        logger.error("[KnowledgeSpace] Full traceback:")
        logger.error(traceback.format_exc())
        logger.error("[KnowledgeSpace] Exception type: %s", type(chunk_error).__name__)
        logger.error("[KnowledgeSpace] Exception args: %s", chunk_error.args)
        raise ValueError(error_msg) from chunk_error

    return chunks


def generate_embeddings_with_cache(
    embedding_client,
    kb_rate_limiter,
    texts: List[str],
    user_id: int,
    db
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
        cached_embedding = embedding_cache.get_document_embedding(db, text)
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
        client_batch_size = getattr(embedding_client, 'batch_size', 10)
        estimated_api_calls = (len(texts_to_embed) + client_batch_size - 1) // client_batch_size

        remaining, _ = kb_rate_limiter.get_embedding_remaining(user_id)
        if remaining < estimated_api_calls:
            error_msg = (
                f"嵌入向量生成速率限制: 需要约 {estimated_api_calls} 次API调用（{len(texts_to_embed)} 个文本，"
                f"批次大小 {client_batch_size}），但当前仅剩 {remaining} 次可用。"
                f"请稍后重试或增加 KB_EMBEDDING_RPM 配置值（当前: {embedding_rpm}/分钟）。"
            )
            logger.error(
                "[KnowledgeSpace] Cannot process %s uncached texts: "
                "rate limit insufficient (need ~%s API calls, have %s remaining)",
                len(texts_to_embed), estimated_api_calls, remaining
            )
            raise ValueError(error_msg)

        try:
            new_embeddings = embedding_client.embed_texts(
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
                    "[KnowledgeSpace] Embedding count mismatch: expected %s, got %s",
                    len(texts_to_embed), len(new_embeddings)
                )
                raise ValueError(error_msg)

            # Store in cache and fill in embeddings list
            for text, embedding, idx in zip(texts_to_embed, new_embeddings, indices_to_embed):
                embedding_cache.cache_document_embedding(db, text, embedding)
                embeddings[idx] = embedding

            logger.debug(
                "[KnowledgeSpace] Successfully embedded %s texts",
                len(new_embeddings)
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

    return embeddings


def prepare_qdrant_metadata(
    chunks: List[Any],
    document: KnowledgeDocument
) -> List[dict]:
    """
    Prepare metadata for Qdrant payload.

    Args:
        chunks: List of chunks
        document: KnowledgeDocument instance

    Returns:
        List of metadata dictionaries
    """
    qdrant_metadata = []
    for chunk in chunks:
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

    return qdrant_metadata
