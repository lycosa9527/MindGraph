"""Knowledge base configuration settings.

This module provides knowledge base related configuration properties.
"""
import logging
from typing import Optional, TYPE_CHECKING, Any

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
    def QDRANT_COLLECTION_PREFIX(self) -> str:
        """Qdrant collection name prefix"""
        return self._get_cached_value('QDRANT_COLLECTION_PREFIX', 'user_')

    @property
    def QDRANT_COMPRESSION(self) -> str:
        """Qdrant compression method (SQ8, IVF_SQ8, or None for no compression)"""
        return self._get_cached_value('QDRANT_COMPRESSION', 'SQ8')

    @property
    def DASHSCOPE_EMBEDDING_MODEL(self) -> str:
        """DashScope embedding model (text-embedding-v4 recommended)"""
        return self._get_cached_value('DASHSCOPE_EMBEDDING_MODEL', 'text-embedding-v4')

    @property
    def EMBEDDING_DIMENSIONS(self) -> Optional[int]:
        """
        Custom embedding dimensions (for v3, v4). Options: 64, 128, 256, 512, 768, 1024, 1536, 2048
        Default: 768 for optimal compression ratio while maintaining quality
        """
        val = self._get_cached_value('EMBEDDING_DIMENSIONS', None)
        if val is not None:
            try:
                dim = int(val)
                valid_dims = [64, 128, 256, 512, 768, 1024, 1536, 2048]
                if dim in valid_dims:
                    return dim
                logger.warning("[Config] Invalid EMBEDDING_DIMENSIONS %s, must be one of %s", dim, valid_dims)
            except (ValueError, TypeError):
                logger.warning("[Config] Invalid EMBEDDING_DIMENSIONS value: %s", val)
        return 768

    @property
    def EMBEDDING_OUTPUT_TYPE(self) -> str:
        """Embedding output type: 'dense', 'sparse', or 'dense&sparse' (for v3, v4)"""
        val = self._get_cached_value('EMBEDDING_OUTPUT_TYPE', 'dense')
        if val not in ['dense', 'sparse', 'dense&sparse']:
            logger.warning("[Config] Invalid EMBEDDING_OUTPUT_TYPE %s, using 'dense'", val)
            return 'dense'
        return val

    @property
    def DASHSCOPE_RERANK_MODEL(self) -> str:
        """DashScope rerank model (qwen3-rerank recommended)"""
        return self._get_cached_value('DASHSCOPE_RERANK_MODEL', 'qwen3-rerank')

    @property
    def EMBEDDING_BATCH_SIZE(self) -> int:
        """Batch size for embedding API calls"""
        return int(self._get_cached_value('EMBEDDING_BATCH_SIZE', '50'))

    @property
    def DEFAULT_RETRIEVAL_METHOD(self) -> str:
        """Default retrieval method (semantic, keyword, hybrid)"""
        return self._get_cached_value('DEFAULT_RETRIEVAL_METHOD', 'hybrid')

    @property
    def HYBRID_VECTOR_WEIGHT(self) -> float:
        """Weight for vector search in hybrid search"""
        return float(self._get_cached_value('HYBRID_VECTOR_WEIGHT', '0.5'))

    @property
    def HYBRID_KEYWORD_WEIGHT(self) -> float:
        """Weight for keyword search in hybrid search"""
        return float(self._get_cached_value('HYBRID_KEYWORD_WEIGHT', '0.5'))

    @property
    def USE_RERANK_MODEL(self) -> bool:
        """Use rerank model vs weighted scores (deprecated: use RERANKING_MODE instead)"""
        return self._get_cached_value('USE_RERANK_MODEL', 'true').lower() == 'true'

    @property
    def RERANKING_MODE(self) -> str:
        """Reranking mode: 'reranking_model', 'weighted_score', or 'none'"""
        return self._get_cached_value('RERANKING_MODE', 'reranking_model')

    @property
    def KB_RETRIEVAL_RPM(self) -> int:
        """Knowledge base retrieval requests per minute per user"""
        try:
            return int(self._get_cached_value('KB_RETRIEVAL_RPM', '60'))
        except (ValueError, TypeError):
            return 60

    @property
    def KB_EMBEDDING_RPM(self) -> int:
        """Knowledge base embedding generation per minute per user"""
        try:
            return int(self._get_cached_value('KB_EMBEDDING_RPM', '100'))
        except (ValueError, TypeError):
            return 100

    @property
    def KB_UPLOAD_PER_HOUR(self) -> int:
        """Knowledge base document uploads per hour per user"""
        try:
            return int(self._get_cached_value('KB_UPLOAD_PER_HOUR', '10'))
        except (ValueError, TypeError):
            return 10

    @property
    def DASHSCOPE_MULTIMODAL_MODEL(self) -> str:
        """DashScope multimodal embedding model (for image/video embeddings)"""
        return self._get_cached_value('DASHSCOPE_MULTIMODAL_MODEL', 'tongyi-embedding-vision-plus')

    @property
    def RERANK_SCORE_THRESHOLD(self) -> float:
        """Minimum score threshold for reranked results"""
        return float(self._get_cached_value('RERANK_SCORE_THRESHOLD', '0.5'))

    @property
    def RETRIEVAL_PARALLEL_WORKERS(self) -> int:
        """Number of parallel workers for hybrid search"""
        return int(self._get_cached_value('RETRIEVAL_PARALLEL_WORKERS', '2'))

    @property
    def CHUNK_SIZE(self) -> int:
        """Tokens per chunk"""
        return int(self._get_cached_value('CHUNK_SIZE', '500'))

    @property
    def CHUNK_OVERLAP(self) -> int:
        """Overlap tokens between chunks"""
        return int(self._get_cached_value('CHUNK_OVERLAP', '50'))

    @property
    def MAX_DOCUMENTS_PER_USER(self) -> int:
        """Maximum documents per user"""
        return int(self._get_cached_value('MAX_DOCUMENTS_PER_USER', '5'))

    @property
    def MAX_FILE_SIZE(self) -> int:
        """Maximum file size in bytes (10MB)"""
        return int(self._get_cached_value('MAX_FILE_SIZE', '10485760'))

    @property
    def MAX_STORAGE_PER_USER(self) -> int:
        """Maximum storage per user in bytes (50MB)"""
        return int(self._get_cached_value('MAX_STORAGE_PER_USER', '52428800'))

    @property
    def MAX_CHUNKS_PER_USER(self) -> int:
        """Maximum chunks per user"""
        return int(self._get_cached_value('MAX_CHUNKS_PER_USER', '1000'))

    @property
    def KNOWLEDGE_STORAGE_DIR(self) -> str:
        """Directory for storing knowledge documents"""
        return self._get_cached_value('KNOWLEDGE_STORAGE_DIR', './storage/knowledge_documents')
