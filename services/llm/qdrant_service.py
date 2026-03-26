"""
Qdrant Service for Knowledge Space
Author: lycosa9527
Made by: MindSpring Team

Qdrant integration for storing document embeddings with compression support (SQ8/IVF_SQ8).
Requires Qdrant server (QDRANT_HOST or QDRANT_URL must be set).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from typing import List, Optional, Dict, Any
import logging
import os

import qdrant_client
from qdrant_client.http import models as rest
from qdrant_client.http.models import Distance

# Try to import QuantizationType, fallback to string literal if not available
try:
    from qdrant_client.http.models import QuantizationType
except ImportError:
    # QuantizationType not available in this version, use string literal instead
    QuantizationType = None

from config.settings import config

from services.llm.qdrant_diagnostics import QdrantDiagnosticsMixin
from services.llm.qdrant_startup import parse_qdrant_host_port

logger = logging.getLogger(__name__)


def _append_metadata_filter_conditions(
    metadata_filter: Dict[str, Any],
    filter_conditions: list,
) -> None:
    """Append Qdrant FieldConditions derived from metadata_filter."""
    for key, value in metadata_filter.items():
        if key == "document_id":
            filter_conditions.append(
                rest.FieldCondition(
                    key="document_id",
                    match=rest.MatchValue(value=str(value)),
                )
            )
        elif key == "document_type":
            filter_conditions.append(
                rest.FieldCondition(
                    key="document_type",
                    match=rest.MatchValue(value=str(value)),
                )
            )
        elif key == "category":
            filter_conditions.append(
                rest.FieldCondition(
                    key="category",
                    match=rest.MatchValue(value=str(value)),
                )
            )
        elif key == "tags" and isinstance(value, (list, tuple)):
            pass
        elif key == "created_at" and isinstance(value, dict):
            pass
        elif isinstance(value, dict) and (
            "gte" in value or "lte" in value or "gt" in value or "lt" in value
        ):
            pass
        elif isinstance(value, (list, tuple)):
            filter_conditions.append(
                rest.FieldCondition(
                    key=key,
                    match=rest.MatchAny(any=[str(v) for v in value]),
                )
            )
        else:
            filter_conditions.append(
                rest.FieldCondition(
                    key=key,
                    match=rest.MatchValue(value=str(value)),
                )
            )


def _chunk_results_from_query_points(results: Any) -> List[Dict[str, Any]]:
    """Map Qdrant query point results to chunk id / score / metadata dicts."""
    chunk_results: List[Dict[str, Any]] = []
    for result in results:
        if not result.payload:
            continue
        chunk_id_str = result.payload.get("chunk_id", "")
        try:
            chunk_id = int(chunk_id_str)
        except (ValueError, TypeError):
            payload_keys = list(result.payload.keys()) if result.payload else []
            logger.debug(
                "[Qdrant] Skipping result with invalid chunk_id: "
                "%s, payload keys: %s",
                chunk_id_str,
                payload_keys
            )
            continue

        chunk_results.append({
            "id": chunk_id,
            "score": float(result.score),
            "metadata": result.payload,
        })
    return chunk_results


class QdrantService(QdrantDiagnosticsMixin):
    """
    Qdrant service for vector storage and retrieval.

    Requires Qdrant server (set QDRANT_HOST or QDRANT_URL).
    Creates separate collections per user for data isolation.
    Supports SQ8 compression for ~4x storage savings.
    """

    def __init__(self):
        """
        Initialize Qdrant client (server mode only).

        Requires one of:
        - QDRANT_URL: Full URL (e.g., 'http://localhost:6333')
        - QDRANT_HOST: Host:port (e.g., 'localhost:6333')

        Raises:
            ValueError: If neither QDRANT_URL nor QDRANT_HOST is configured
        """
        qdrant_host = os.getenv("QDRANT_HOST", "")
        qdrant_url = os.getenv("QDRANT_URL", "")

        if qdrant_url:
            # Full URL specified (e.g., http://localhost:6333)
            logger.info("[Qdrant] Connecting to server: %s", qdrant_url)
            self.client = qdrant_client.QdrantClient(url=qdrant_url)
        elif qdrant_host:
            # Host:port specified (e.g., localhost:6333)
            host, port = parse_qdrant_host_port(qdrant_host)
            logger.info("[Qdrant] Connecting to server: %s:%s", host, port)
            self.client = qdrant_client.QdrantClient(host=host, port=port)
        else:
            raise ValueError(
                "Qdrant server not configured. "
                "Set QDRANT_HOST=localhost:6333 or QDRANT_URL=http://localhost:6333 in .env file. "
                "See docs/QDRANT_SETUP.md for installation instructions."
            )

        self.collection_prefix = os.getenv("QDRANT_COLLECTION_PREFIX", "user_")

        # Compression configuration - always use compression for maximum efficiency
        self.compression_type = os.getenv("QDRANT_COMPRESSION", "SQ8")  # SQ8, IVF_SQ8, or None
        self.use_compression = self.compression_type in ["SQ8", "IVF_SQ8"]

        # Validate compression is enabled (critical for storage efficiency)
        if not self.use_compression:
            logger.warning(
                "[Qdrant] Compression is DISABLED (QDRANT_COMPRESSION=%s). "
                "This will result in ~4x larger storage usage. "
                "Recommendation: Set QDRANT_COMPRESSION=SQ8 for maximum efficiency.",
                self.compression_type
            )
        else:
            logger.info(
                "[Qdrant] Initialized with compression=%s (~4x storage savings enabled)",
                self.compression_type
            )

    def _get_collection_name(self, user_id: int, chunking_method: Optional[str] = None) -> str:
        """
        Get collection name for user.
        
        Args:
            user_id: User ID
            chunking_method: Optional chunking method name for chunk test isolation
                           (e.g., 'semchunk', 'spacy'). If provided, creates separate collection.
        
        Returns:
            Collection name
        """
        if chunking_method:
            # For chunk tests, use separate collection per method for better isolation
            return f"{self.collection_prefix}{user_id}_chunk_test_{chunking_method}"
        return f"{self.collection_prefix}{user_id}_knowledge"

    def create_user_collection(
        self,
        user_id: int,
        vector_size: Optional[int] = None,
        chunking_method: Optional[str] = None
    ) -> None:
        """
        Create or get collection for user with compression support.

        Args:
            user_id: User ID
            vector_size: Embedding vector size (default: from config.EMBEDDING_DIMENSIONS or 768)
            chunking_method: Optional chunking method name for chunk test isolation
        """
        if vector_size is None:
            # Use optimized dimensions from config (default: 768 for compression efficiency)
            vector_size = config.EMBEDDING_DIMENSIONS or 768
        collection_name = self._get_collection_name(user_id, chunking_method)

        try:
            # Check if collection exists
            collections = self.client.get_collections()
            existing_names = [col.name for col in collections.collections]

            if collection_name in existing_names:
                logger.debug("[Qdrant] Collection already exists for user %s", user_id)
                return

            # Create collection with compression
            vectors_config = rest.VectorParams(
                size=vector_size,
                distance=Distance.COSINE,
            )

            # Configure HNSW index optimized for compressed vectors
            # Lower m (12-16) works better with compression (less memory overhead)
            # Higher ef_construct (200) compensates for quantization precision loss
            # Smaller full_scan_threshold (5000) leverages compression speed benefits
            hnsw_config = rest.HnswConfigDiff(
                m=14,  # Optimized for compressed vectors (balance between recall and memory)
                ef_construct=200,  # Higher for better recall with quantization
                full_scan_threshold=5000,  # Lower threshold leverages compression speed
            )

            # Configure quantization/compression if enabled
            quantization_config = None
            if self.use_compression:
                # Use QuantizationType enum if available, otherwise use string literal
                if QuantizationType is not None:
                    quantization_type = QuantizationType.INT8
                else:
                    quantization_type = "int8"  # Fallback to string literal for older qdrant-client versions

                if self.compression_type == "SQ8":
                    # SQ8: Scalar Quantization 8-bit (4x compression)
                    quantization_config = rest.ScalarQuantization(
                        scalar=rest.ScalarQuantizationConfig(
                            type=quantization_type,
                            quantile=0.99,
                            always_ram=True,
                        )
                    )
                    logger.info("[Qdrant] Configuring SQ8 compression (4x storage savings)")
                elif self.compression_type == "IVF_SQ8":
                    # IVF_SQ8: Inverted File Index + SQ8 (requires more setup)
                    # For now, use SQ8 (IVF_SQ8 needs additional index configuration)
                    quantization_config = rest.ScalarQuantization(
                        scalar=rest.ScalarQuantizationConfig(
                            type=quantization_type,
                            quantile=0.99,
                            always_ram=True,
                        )
                    )
                    logger.info("[Qdrant] Using SQ8 compression (IVF_SQ8 requires additional index setup)")
            else:
                # Compression disabled - log warning
                logger.warning(
                    "[Qdrant] Creating collection WITHOUT compression. "
                    "Storage usage will be ~4x larger than with SQ8 compression. "
                    "Set QDRANT_COMPRESSION=SQ8 to enable compression."
                )

            # Create collection with optional quantization
            create_params = {
                "collection_name": collection_name,
                "vectors_config": vectors_config,
                "hnsw_config": hnsw_config,
            }
            if quantization_config:
                create_params["quantization_config"] = quantization_config
            else:
                # Warn if compression is disabled
                logger.warning(
                    "[Qdrant] Collection created without compression. "
                    "Consider enabling SQ8 compression for ~4x storage savings."
                )

            self.client.create_collection(**create_params)

            # Create payload indexes for filtering
            try:
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="user_id",
                    field_schema=rest.PayloadSchemaType.KEYWORD,
                )
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="document_id",
                    field_schema=rest.PayloadSchemaType.KEYWORD,
                )
                self.client.create_payload_index(
                    collection_name=collection_name,
                    field_name="chunk_id",
                    field_schema=rest.PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                # Indexes might already exist, ignore
                logger.debug("[Qdrant] Payload index creation (may already exist): %s", e)

            logger.info("[Qdrant] Created collection for user %s with compression=%s", user_id, self.compression_type)

        except Exception as e:
            logger.error("[Qdrant] Failed to create collection for user %s: %s", user_id, e)
            raise

    def get_user_collection(self, user_id: int, chunking_method: Optional[str] = None) -> Optional[str]:
        """
        Get existing collection name for user.

        Args:
            user_id: User ID
            chunking_method: Optional chunking method name for chunk test isolation

        Returns:
            Collection name or None if not found
        """
        collection_name = self._get_collection_name(user_id, chunking_method)

        try:
            collections = self.client.get_collections()
            existing_names = [col.name for col in collections.collections]
            if collection_name in existing_names:
                return collection_name
            return None
        except Exception:
            return None

    def add_documents(
        self,
        user_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        document_ids: List[int],
        metadata: Optional[List[Dict[str, Any]]] = None,
        chunking_method: Optional[str] = None
    ) -> None:
        """
        Add document embeddings to user's collection.

        Args:
            user_id: User ID
            chunk_ids: List of chunk IDs (used as point IDs in Qdrant)
            embeddings: List of embedding vectors
            document_ids: List of document IDs (for metadata)
            metadata: Optional list of metadata dicts
            chunking_method: Optional chunking method name for chunk test isolation
                          (if provided, uses separate collection per method)
        """
        if not chunk_ids or not embeddings:
            logger.warning("[Qdrant] Empty chunk_ids or embeddings for user %s", user_id)
            return

        if len(chunk_ids) != len(embeddings):
            raise ValueError(f"chunk_ids length ({len(chunk_ids)}) != embeddings length ({len(embeddings)})")

        # Get vector size from first embedding or use optimized default
        vector_size = len(embeddings[0]) if embeddings else (config.EMBEDDING_DIMENSIONS or 768)

        # Create collection if needed (with method-specific collection for chunk tests)
        self.create_user_collection(user_id, vector_size, chunking_method)
        collection_name = self._get_collection_name(user_id, chunking_method)

        # Prepare points with payload (metadata)
        points = []
        for i, chunk_id in enumerate(chunk_ids):
            payload = {
                "user_id": str(user_id),
                "document_id": str(document_ids[i] if i < len(document_ids) else document_ids[0]),
                "chunk_id": str(chunk_id),
            }

            # Add custom metadata if provided
            if metadata and i < len(metadata):
                payload.update(metadata[i])

            points.append(
                rest.PointStruct(
                    id=chunk_id,  # Use chunk_id as point ID (must be int)
                    vector=embeddings[i],
                    payload=payload,
                )
            )

        try:
            # Batch upsert points
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info("[Qdrant] Added %s embeddings for user %s", len(chunk_ids), user_id)
        except Exception as e:
            logger.error("[Qdrant] Failed to add embeddings for user %s: %s", user_id, e)
            raise

    def search(
        self,
        user_id: int,
        query_embedding: List[float],
        top_k: int = 5,
        score_threshold: float = 0.0,
        document_id: Optional[int] = None,
        metadata_filter: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors in user's collection.

        Args:
            user_id: User ID
            query_embedding: Query embedding vector
            top_k: Number of results to return
            score_threshold: Minimum similarity score
            document_id: Optional document ID to filter by (deprecated, use metadata_filter)
            metadata_filter: Optional metadata filter dict (e.g., {'document_id': 1, 'document_type': 'pdf'})

        Returns:
            List of dicts with 'id' (chunk_id), 'score', and 'metadata'
        """
        collection_name = self.get_user_collection(user_id)
        if not collection_name:
            logger.warning("[Qdrant] No collection found for user %s", user_id)
            return []

        # Build filter for user_id (always required)
        filter_conditions = [
            rest.FieldCondition(
                key="user_id",
                match=rest.MatchValue(value=str(user_id)),
            )
        ]

        # Support legacy document_id parameter
        if document_id is not None:
            filter_conditions.append(
                rest.FieldCondition(
                    key="document_id",
                    match=rest.MatchValue(value=str(document_id)),
                )
            )

        if metadata_filter:
            _append_metadata_filter_conditions(metadata_filter, filter_conditions)

        query_filter = rest.Filter(must=filter_conditions) if filter_conditions else None

        logger.debug(
            "[Qdrant] search: collection=%s, top_k=%s, score_threshold=%s, filter_conditions=%s",
            collection_name, top_k, score_threshold, len(filter_conditions)
        )

        try:
            # Use query_points API (qdrant-client 1.9+)
            results = self.client.query_points(
                collection_name=collection_name,
                query=query_embedding,
                query_filter=query_filter,
                limit=top_k,
                score_threshold=score_threshold,
                with_payload=True,
            ).points

            logger.debug("[Qdrant] Raw search returned %s results", len(results))

            chunk_results = _chunk_results_from_query_points(results)

            logger.debug("[Qdrant] Found %s valid results for user %s", len(chunk_results), user_id)
            return chunk_results

        except Exception as e:
            logger.error("[Qdrant] Search failed for user %s: %s", user_id, e)
            raise

    def delete_chunks(self, user_id: int, chunk_ids: List[int], chunking_method: Optional[str] = None) -> None:
        """
        Delete specific chunks by chunk IDs from Qdrant.

        Args:
            user_id: User ID
            chunk_ids: List of chunk IDs to delete
            chunking_method: Optional chunking method name for chunk test isolation
        """
        if not chunk_ids:
            return

        collection_name = self.get_user_collection(user_id, chunking_method)
        if not collection_name:
            logger.warning("[Qdrant] No collection found for user %s (method: %s)", user_id, chunking_method)
            return

        try:
            # Delete by point IDs (chunk_ids must be int)
            self.client.delete(
                collection_name=collection_name,
                points_selector=rest.PointIdsList(
                    points=chunk_ids
                ),
            )
            logger.info("[Qdrant] Deleted %s chunks for user %s", len(chunk_ids), user_id)
        except Exception as e:
            logger.error("[Qdrant] Failed to delete chunks for user %s: %s", user_id, e)
            raise

    def update_documents(
        self,
        user_id: int,
        chunk_ids: List[int],
        embeddings: List[List[float]],
        document_ids: List[int],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        """
        Update document embeddings in Qdrant (upsert operation).

        Args:
            user_id: User ID
            chunk_ids: List of chunk IDs (used as point IDs)
            embeddings: List of embedding vectors
            document_ids: List of document IDs (for metadata)
            metadata: Optional list of metadata dicts
        """
        if not chunk_ids or not embeddings:
            logger.warning("[Qdrant] Empty chunk_ids or embeddings for update")
            return

        if len(chunk_ids) != len(embeddings):
            raise ValueError(f"chunk_ids length ({len(chunk_ids)}) != embeddings length ({len(embeddings)})")

        # Get vector size from first embedding
        vector_size = len(embeddings[0]) if embeddings else None
        if not vector_size:
            raise ValueError("Cannot determine vector size from empty embeddings")

        # Create collection if needed
        self.create_user_collection(user_id, vector_size)
        collection_name = self._get_collection_name(user_id)

        # Prepare points with payload (metadata)
        points = []
        for i, chunk_id in enumerate(chunk_ids):
            payload = {
                "user_id": str(user_id),
                "document_id": str(document_ids[i] if i < len(document_ids) else document_ids[0]),
                "chunk_id": str(chunk_id),
            }

            # Add custom metadata if provided
            if metadata and i < len(metadata):
                payload.update(metadata[i])

            points.append(
                rest.PointStruct(
                    id=chunk_id,  # Use chunk_id as point ID (must be int)
                    vector=embeddings[i],
                    payload=payload,
                )
            )

        try:
            # Upsert points (update if exists, insert if not)
            self.client.upsert(
                collection_name=collection_name,
                points=points,
            )
            logger.info("[Qdrant] Updated %s embeddings for user %s", len(chunk_ids), user_id)
        except Exception as e:
            logger.error("[Qdrant] Failed to update embeddings for user %s: %s", user_id, e)
            raise

    def delete_document(self, user_id: int, document_id: int) -> None:
        """
        Delete all chunks for a document from Qdrant.

        Args:
            user_id: User ID
            document_id: Document ID
        """
        collection_name = self.get_user_collection(user_id)
        if not collection_name:
            logger.warning("[Qdrant] No collection found for user %s", user_id)
            return

        try:
            # Delete by filter
            query_filter = rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="user_id",
                        match=rest.MatchValue(value=str(user_id)),
                    ),
                    rest.FieldCondition(
                        key="document_id",
                        match=rest.MatchValue(value=str(document_id)),
                    ),
                ]
            )

            self.client.delete(
                collection_name=collection_name,
                points_selector=rest.FilterSelector(filter=query_filter),
            )
            logger.info("[Qdrant] Deleted document %s for user %s", document_id, user_id)
        except Exception as e:
            logger.error("[Qdrant] Failed to delete document %s for user %s: %s", document_id, user_id, e)
            raise

    def delete_user_collection(self, user_id: int) -> None:
        """
        Delete entire collection for user (cleanup on user deletion).

        Args:
            user_id: User ID
        """
        collection_name = self._get_collection_name(user_id)

        try:
            self.client.delete_collection(collection_name=collection_name)
            logger.info("[Qdrant] Deleted collection for user %s", user_id)
        except Exception as e:
            logger.warning("[Qdrant] Failed to delete collection for user %s: %s", user_id, e)
            # Don't raise - collection might not exist

    def get_collection_size(self, user_id: int) -> int:
        """
        Get number of chunks in user's collection.

        Args:
            user_id: User ID

        Returns:
            Number of chunks
        """
        collection_name = self.get_user_collection(user_id)
        if not collection_name:
            return 0

        try:
            info = self.client.get_collection(collection_name)
            return info.points_count
        except Exception as e:
            logger.error("[Qdrant] Failed to get collection size for user %s: %s", user_id, e)
            return 0


def get_qdrant_service() -> QdrantService:
    """Get global Qdrant service instance."""
    if not hasattr(get_qdrant_service, 'instance'):
        get_qdrant_service.instance = QdrantService()
    return get_qdrant_service.instance
