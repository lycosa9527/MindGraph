"""Knowledge base configuration settings.

This module provides knowledge base related configuration properties.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from typing import TYPE_CHECKING, Any, Optional

logger = logging.getLogger(__name__)


class KnowledgeConfigMixin:
    """Mixin class for knowledge base configuration properties.

    This mixin expects the class to inherit from BaseConfig or provide
    a _get_cached_value method.
    """

    if TYPE_CHECKING:

        def _get_cached_value(self, _key: str, _default: Any = None) -> Any:
            """Type stub: method provided by BaseConfig."""
            raise NotImplementedError

        @property
        def server_url(self) -> str:
            """Type stub: property provided by BaseConfig."""
            raise NotImplementedError

    @property
    def QDRANT_COLLECTION_PREFIX(self) -> str:
        """Qdrant collection name prefix"""
        return self._get_cached_value("QDRANT_COLLECTION_PREFIX", "user_")

    @property
    def QDRANT_COMPRESSION(self) -> str:
        """Qdrant compression method (SQ8, IVF_SQ8, or None for no compression)"""
        return self._get_cached_value("QDRANT_COMPRESSION", "SQ8")

    @property
    def DASHSCOPE_EMBEDDING_MODEL(self) -> str:
        """DashScope embedding model (text-embedding-v4 recommended)"""
        return self._get_cached_value("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v4")

    @property
    def EMBEDDING_DIMENSIONS(self) -> Optional[int]:
        """
        Custom embedding dimensions (for v3, v4). Options: 64, 128, 256, 512, 768, 1024, 1536, 2048
        Default: 768 for optimal compression ratio while maintaining quality
        """
        val = self._get_cached_value("EMBEDDING_DIMENSIONS", None)
        if val is not None:
            try:
                dim = int(val)
                valid_dims = [64, 128, 256, 512, 768, 1024, 1536, 2048]
                if dim in valid_dims:
                    return dim
                logger.warning(
                    "[Config] Invalid EMBEDDING_DIMENSIONS %s, must be one of %s",
                    dim,
                    valid_dims,
                )
            except (ValueError, TypeError):
                logger.warning("[Config] Invalid EMBEDDING_DIMENSIONS value: %s", val)
        return 768

    @property
    def EMBEDDING_OUTPUT_TYPE(self) -> str:
        """Embedding output type: 'dense', 'sparse', or 'dense&sparse' (for v3, v4)"""
        val = self._get_cached_value("EMBEDDING_OUTPUT_TYPE", "dense")
        if val not in ["dense", "sparse", "dense&sparse"]:
            logger.warning("[Config] Invalid EMBEDDING_OUTPUT_TYPE %s, using 'dense'", val)
            return "dense"
        return val

    @property
    def DASHSCOPE_RERANK_MODEL(self) -> str:
        """DashScope rerank model (qwen3-rerank recommended)"""
        return self._get_cached_value("DASHSCOPE_RERANK_MODEL", "qwen3-rerank")

    @property
    def EMBEDDING_BATCH_SIZE(self) -> int:
        """Batch size for embedding API calls"""
        return int(self._get_cached_value("EMBEDDING_BATCH_SIZE", "50"))

    @property
    def DEFAULT_RETRIEVAL_METHOD(self) -> str:
        """Default retrieval method (semantic, keyword, hybrid)"""
        return self._get_cached_value("DEFAULT_RETRIEVAL_METHOD", "hybrid")

    @property
    def HYBRID_VECTOR_WEIGHT(self) -> float:
        """Weight for vector search in hybrid search"""
        return float(self._get_cached_value("HYBRID_VECTOR_WEIGHT", "0.5"))

    @property
    def HYBRID_KEYWORD_WEIGHT(self) -> float:
        """Weight for keyword search in hybrid search"""
        return float(self._get_cached_value("HYBRID_KEYWORD_WEIGHT", "0.5"))

    @property
    def USE_RERANK_MODEL(self) -> bool:
        """Use rerank model vs weighted scores (deprecated: use RERANKING_MODE instead)"""
        return self._get_cached_value("USE_RERANK_MODEL", "true").lower() == "true"

    @property
    def RERANKING_MODE(self) -> str:
        """Reranking mode: 'reranking_model', 'weighted_score', or 'none'"""
        return self._get_cached_value("RERANKING_MODE", "reranking_model")

    @property
    def KB_RETRIEVAL_RPM(self) -> int:
        """Knowledge base retrieval requests per minute per user"""
        try:
            return int(self._get_cached_value("KB_RETRIEVAL_RPM", "60"))
        except (ValueError, TypeError):
            return 60

    @property
    def KB_EMBEDDING_RPM(self) -> int:
        """Knowledge base embedding generation per minute per user"""
        try:
            return int(self._get_cached_value("KB_EMBEDDING_RPM", "100"))
        except (ValueError, TypeError):
            return 100

    @property
    def KB_UPLOAD_PER_HOUR(self) -> int:
        """Knowledge base document uploads per hour per user"""
        try:
            return int(self._get_cached_value("KB_UPLOAD_PER_HOUR", "10"))
        except (ValueError, TypeError):
            return 10

    @property
    def DASHSCOPE_MULTIMODAL_MODEL(self) -> str:
        """DashScope multimodal embedding model (for image/video embeddings)"""
        return self._get_cached_value("DASHSCOPE_MULTIMODAL_MODEL", "tongyi-embedding-vision-plus")

    @property
    def DASHSCOPE_VISION_MODEL(self) -> str:
        """DashScope multimodal model for image OCR / understanding (document ingestion).

        Native vision-language model used by the document processor to read image
        sources and OCR rasterized scanned-PDF pages. Defaults to ``qwen3.6-flash``;
        override with ``DASHSCOPE_VISION_MODEL``.
        """
        return self._get_cached_value("DASHSCOPE_VISION_MODEL", "qwen3.6-flash")

    @property
    def LIBREOFFICE_PATH(self) -> str:
        """Optional absolute path to LibreOffice ``soffice`` for legacy .doc/.ppt/.xls."""
        return self._get_cached_value("LIBREOFFICE_PATH", "")

    @property
    def DASHSCOPE_ASR_FILETRANS_MODEL(self) -> str:
        """DashScope async recording-file transcription model for audio sources.

        Used for batch (submit/poll) transcription of uploaded audio files.
        Defaults to ``fun-asr-flash-2026-06-15``; override with
        ``DASHSCOPE_ASR_FILETRANS_MODEL``.
        """
        return self._get_cached_value("DASHSCOPE_ASR_FILETRANS_MODEL", "fun-asr-flash-2026-06-15")

    @property
    def KNOWLEDGE_AUDIO_PUBLIC_BASE(self) -> str:
        """Public base URL DashScope uses to fetch hosted audio for transcription.

        The async ASR API only accepts publicly reachable URLs. When the server
        sits behind a reverse proxy / HTTPS, set ``KNOWLEDGE_AUDIO_PUBLIC_BASE``
        (e.g. ``https://app.example.com``); otherwise the server's external URL
        (``EXTERNAL_HOST`` + port) is used. Must be reachable from Alibaba Cloud.
        """
        override = self._get_cached_value("KNOWLEDGE_AUDIO_PUBLIC_BASE", "")
        if isinstance(override, str) and override.strip():
            return override.strip().rstrip("/")
        return self.server_url.rstrip("/")

    @property
    def RERANK_SCORE_THRESHOLD(self) -> float:
        """Minimum score threshold for reranked results"""
        return float(self._get_cached_value("RERANK_SCORE_THRESHOLD", "0.5"))

    @property
    def RETRIEVAL_PARALLEL_WORKERS(self) -> int:
        """Number of parallel workers for hybrid search"""
        return int(self._get_cached_value("RETRIEVAL_PARALLEL_WORKERS", "2"))

    @property
    def CHUNK_SIZE(self) -> int:
        """Tokens per chunk"""
        return int(self._get_cached_value("CHUNK_SIZE", "500"))

    @property
    def CHUNK_OVERLAP(self) -> int:
        """Overlap tokens between chunks"""
        return int(self._get_cached_value("CHUNK_OVERLAP", "50"))

    @property
    def MAX_DOCUMENTS_PER_USER(self) -> int:
        """Maximum documents per user"""
        return int(self._get_cached_value("MAX_DOCUMENTS_PER_USER", "5"))

    @property
    def MAX_FILE_SIZE(self) -> int:
        """Maximum file size in bytes (10MB)"""
        return int(self._get_cached_value("MAX_FILE_SIZE", "10485760"))

    @property
    def MAX_STORAGE_PER_USER(self) -> int:
        """Maximum storage per user in bytes (50MB)"""
        return int(self._get_cached_value("MAX_STORAGE_PER_USER", "52428800"))

    @property
    def MAX_CHUNKS_PER_USER(self) -> int:
        """Maximum chunks per user"""
        return int(self._get_cached_value("MAX_CHUNKS_PER_USER", "1000"))

    @property
    def KNOWLEDGE_STORAGE_DIR(self) -> str:
        """Directory for storing knowledge documents"""
        return self._get_cached_value("KNOWLEDGE_STORAGE_DIR", "./storage/knowledge_documents")

    @property
    def COS_DOCUMENTS_ENABLED(self) -> bool:
        """Store Document Summary extracted markdown in Tencent COS when configured."""
        return self._get_cached_value("COS_DOCUMENTS_ENABLED", "true").lower() == "true"

    @property
    def COS_DOCUMENTS_PREFIX(self) -> str:
        """COS key prefix for Document Summary extracted markdown.

        Objects are UUID-keyed (not MG user id), e.g.
        ``documents/mindgraph/{uuid}.md``, so test/prod can share one bucket.
        Access is always via ownership-checked APIs — never a public COS URL.
        """
        return self._get_cached_value("COS_DOCUMENTS_PREFIX", "documents/mindgraph").strip().rstrip("/")

    @property
    def COS_SHOWCASE_ENABLED(self) -> bool:
        """Private-bucket Showcase media (presigned PUT/GET). Default on; local if COS auth missing."""
        return self._get_cached_value("COS_SHOWCASE_ENABLED", "true").lower() == "true"

    @property
    def COS_SHOWCASE_PREFIX(self) -> str:
        """COS key prefix for Showcase posts (private bucket objects)."""
        return self._get_cached_value("COS_SHOWCASE_PREFIX", "showcase/mindgraph").strip().rstrip("/")

    @property
    def COS_SHOWCASE_PRESIGN_PUT_TTL(self) -> int:
        """Seconds for browser→COS presigned PUT URLs (short-lived)."""
        return int(self._get_cached_value("COS_SHOWCASE_PRESIGN_PUT_TTL", "900"))

    @property
    def COS_SHOWCASE_PRESIGN_GET_TTL(self) -> int:
        """Seconds for COS→browser presigned GET URLs (short-lived)."""
        return int(self._get_cached_value("COS_SHOWCASE_PRESIGN_GET_TTL", "300"))

    @property
    def FILE_CENTER_WIKI_COMPILE(self) -> bool:
        """Compile a per-package wiki (markdown on disk) after chunk indexing (v2a)."""
        return self._get_cached_value("FILE_CENTER_WIKI_COMPILE", "true").lower() == "true"
