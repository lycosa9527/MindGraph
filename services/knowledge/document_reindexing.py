"""Document reindexing helper functions.

Extracted from knowledge_space_service.py to reduce complexity.
"""
import logging
from typing import List, Dict, Set, Tuple, Any, Optional

from config.settings import config
from models.domain.knowledge_space import KnowledgeDocument, DocumentChunk
from services.knowledge.chunking_service import ChunkingService
from services.llm.embedding_cache import get_embedding_cache


logger = logging.getLogger(__name__)


def chunk_text_for_reindexing(
    chunking_service,
    cleaned_text: str,
    document: KnowledgeDocument,
    processing_rules: Optional[dict],
    page_info: Optional[List[Dict[str, Any]]]
) -> List[Any]:
    """
    Chunk text for reindexing based on processing mode.

    Args:
        chunking_service: Default chunking service instance
        cleaned_text: Cleaned text to chunk
        document: KnowledgeDocument instance
        processing_rules: Optional processing rules
        page_info: Optional page information (list of dicts with page metadata)

    Returns:
        List of chunks
    """
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
    import os
    chunking_engine = os.getenv("CHUNKING_ENGINE", "semchunk").lower()
    chunking_method = "mindchunk" if chunking_engine == "mindchunk" else "semchunk"
    logger.info(
        "[RAG] → Chunking (update): doc_id=%s, method=%s, mode=%s, chunk_size=%s, overlap=%s",
        document.id, chunking_method, mode, chunk_size or 500, chunk_overlap or 50
    )

    # Chunk text
    try:
        if mode == "hierarchical":
            if chunking_engine == "semchunk":
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
                logger.warning(
                    "[RAG] Hierarchical mode not supported with mindchunk, "
                    "falling back to default automatic chunking for doc_id=%s",
                    document.id
                )
                new_chunks = chunking_service.chunk_text(
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
                new_chunks = custom_chunking.chunk_text(
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
                    document.id
                )
                new_chunks = chunking_service.chunk_text(
                    cleaned_text,
                    metadata={"document_id": document.id},
                    separator=separator,
                    extract_structure=True,
                    page_info=page_info,
                    language=document.language
                )
        else:
            # Default chunking (respects CHUNKING_ENGINE)
            new_chunks = chunking_service.chunk_text(
                cleaned_text,
                metadata={"document_id": document.id},
                separator=separator,
                extract_structure=True,
                page_info=page_info,
                language=document.language
            )
    except Exception as chunk_error:
        error_msg = f"文本分块失败: {str(chunk_error)}"
        logger.error(
            "[KnowledgeSpace] Chunking failed for document %s: %s",
            document.id, chunk_error
        )
        raise ValueError(error_msg) from chunk_error

    return new_chunks


def compare_chunks(
    new_chunks: List[Any],
    existing_chunks: List[DocumentChunk],
    calculate_chunk_hash
) -> Tuple[List[Tuple[int, Any, str]], List[Tuple[int, Any, str]], Set[int]]:
    """
    Compare new chunks with existing chunks.

    Args:
        new_chunks: List of new chunks
        existing_chunks: List of existing DocumentChunk instances
        calculate_chunk_hash: Function to calculate chunk hash

    Returns:
        Tuple of (chunks_to_add, chunks_to_update, chunks_to_delete)
    """
    # Build hash map of existing chunks
    existing_chunk_map: Dict[int, DocumentChunk] = {}
    existing_chunk_hashes: Dict[int, str] = {}
    for chunk in existing_chunks:
        existing_chunk_map[chunk.chunk_index] = chunk
        existing_chunk_hashes[chunk.chunk_index] = calculate_chunk_hash(chunk.text)

    # Compare new chunks with existing chunks
    chunks_to_add: List = []
    chunks_to_update: List = []
    chunks_to_delete: Set[int] = set(existing_chunk_map.keys())

    for i, new_chunk in enumerate(new_chunks):
        new_chunk_hash = calculate_chunk_hash(new_chunk.text)

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

    logger.info(
        "[RAG] ✓ Chunk comparison: added=%s, updated=%s, deleted=%s",
        len(chunks_to_add), len(chunks_to_update), len(chunks_to_delete)
    )

    return chunks_to_add, chunks_to_update, chunks_to_delete


def process_updated_chunks(
    chunks_to_update: List[Tuple[int, Any, str]],
    existing_chunk_map: Dict[int, DocumentChunk],
    document: KnowledgeDocument,
    embedding_client,
    kb_rate_limiter,
    user_id: int,
    db
) -> Tuple[List[int], List[List[float]], List[Any]]:
    """
    Process updated chunks: generate embeddings and update database.

    Args:
        chunks_to_update: List of (index, chunk, hash) tuples
        existing_chunk_map: Map of existing chunks by index
        document: KnowledgeDocument instance
        embedding_client: Embedding client instance
        kb_rate_limiter: Rate limiter instance
        user_id: User ID
        db: Database session

    Returns:
        Tuple of (chunk_ids, embeddings, chunks)
    """
    updated_chunk_ids = []
    updated_embeddings = []
    updated_chunks = []
    embedding_cache = get_embedding_cache()

    for chunk_index, new_chunk, _chunk_hash in chunks_to_update:
        existing_chunk = existing_chunk_map[chunk_index]

        # Get or generate embedding
        cached_embedding = embedding_cache.get_document_embedding(db, new_chunk.text)
        if not cached_embedding:
            # Check rate limit
            allowed, _count, _error_msg = kb_rate_limiter.check_embedding_limit(user_id)
            if not allowed:
                logger.warning(
                    "[KnowledgeSpace] Embedding rate limit exceeded during update. "
                    "Skipping remaining chunks."
                )
                break

            # Generate embedding
            dimensions = config.EMBEDDING_DIMENSIONS
            try:
                embeddings = embedding_client.embed_texts(
                    [new_chunk.text], dimensions=dimensions
                )
                if embeddings:
                    cached_embedding = embeddings[0]
                    embedding_cache.cache_document_embedding(db, new_chunk.text, cached_embedding)
            except Exception as e:
                logger.error(
                    "[KnowledgeSpace] Failed to generate embedding for chunk %s: %s",
                    chunk_index, e
                )
                continue

        if cached_embedding:
            # Update chunk in database
            existing_chunk.text = new_chunk.text
            existing_chunk.start_char = new_chunk.start_char
            existing_chunk.end_char = new_chunk.end_char

            updated_chunk_ids.append(existing_chunk.id)
            updated_embeddings.append(cached_embedding)
            updated_chunks.append(new_chunk)

    return updated_chunk_ids, updated_embeddings, updated_chunks


def process_new_chunks(
    chunks_to_add: List[Tuple[int, Any, str]],
    document: KnowledgeDocument,
    embedding_client,
    kb_rate_limiter,
    user_id: int,
    db
) -> Tuple[List[int], List[List[float]], List[Any]]:
    """
    Process new chunks: generate embeddings and create database records.

    Args:
        chunks_to_add: List of (index, chunk, hash) tuples
        document: KnowledgeDocument instance
        embedding_client: Embedding client instance
        kb_rate_limiter: Rate limiter instance
        user_id: User ID
        db: Database session

    Returns:
        Tuple of (chunk_ids, embeddings, chunks)
    """
    new_chunk_ids = []
    new_embeddings = []
    new_chunks_list = []
    embedding_cache = get_embedding_cache()

    for chunk_index, new_chunk, _chunk_hash in chunks_to_add:
        # Get or generate embedding
        cached_embedding = embedding_cache.get_document_embedding(db, new_chunk.text)
        if not cached_embedding:
            # Check rate limit
            allowed, _count, _error_msg = kb_rate_limiter.check_embedding_limit(user_id)
            if not allowed:
                logger.warning(
                    "[KnowledgeSpace] Embedding rate limit exceeded during update. "
                    "Skipping remaining chunks."
                )
                break

            # Generate embedding
            dimensions = config.EMBEDDING_DIMENSIONS
            try:
                embeddings = embedding_client.embed_texts(
                    [new_chunk.text], dimensions=dimensions
                )
                if embeddings:
                    cached_embedding = embeddings[0]
                    embedding_cache.cache_document_embedding(db, new_chunk.text, cached_embedding)
            except Exception as e:
                logger.error(
                    "[KnowledgeSpace] Failed to generate embedding for new chunk %s: %s",
                    chunk_index, e
                )
                continue

        if cached_embedding:
            # Create chunk in database
            db_chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=chunk_index,
                text=new_chunk.text,
                start_char=new_chunk.start_char,
                end_char=new_chunk.end_char
            )
            db.add(db_chunk)
            db.flush()

            new_chunk_ids.append(db_chunk.id)
            new_embeddings.append(cached_embedding)
            new_chunks_list.append(new_chunk)

    return new_chunk_ids, new_embeddings, new_chunks_list
