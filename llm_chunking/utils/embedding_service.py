"""
Embedding service wrapper for LLM chunking module.

Provides a simple interface to DashScopeEmbeddingClient for semantic chunking.
Since DashScope embeddings are already L2-normalized, cosine similarity
can be computed efficiently using dot product.

Author: MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
All Rights Reserved
Proprietary License
"""

import logging
from typing import List, Optional
import numpy as np

try:
    from clients.dashscope_embedding import get_embedding_client
except ImportError:
    get_embedding_client = None

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Embedding service wrapper for semantic chunking.

    Uses DashScopeEmbeddingClient (Qwen text-embedding-v4) which already
    provides L2-normalized embeddings, making cosine similarity calculation
    efficient via dot product.
    """

    def __init__(self, embedding_client=None):
        """
        Initialize embedding service.

        Args:
            embedding_client: Optional DashScopeEmbeddingClient instance
        """
        self.embedding_client = embedding_client
        if embedding_client is None:
            try:
                if get_embedding_client is None:
                    raise ImportError("get_embedding_client not available")
                self.embedding_client = get_embedding_client()
                logger.info("[EmbeddingService] Initialized with DashScope embedding client")
            except Exception as e:
                logger.warning("[EmbeddingService] Embedding client not available: %s", e)
                self.embedding_client = None

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Embed multiple texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of normalized embedding vectors (L2-normalized)
        """
        if not self.embedding_client:
            raise ValueError("Embedding client not available")

        if not texts:
            return []

        try:
            # DashScopeEmbeddingClient already normalizes embeddings
            embeddings = self.embedding_client.embed_texts(
                texts=texts,
                text_type="document"
            )
            return embeddings
        except Exception as e:
            logger.error("[EmbeddingService] Failed to embed texts: %s", e)
            raise

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two normalized embeddings.

        Since embeddings are already L2-normalized, cosine similarity
        equals dot product (faster than sklearn's cosine_similarity).

        Args:
            embedding1: First normalized embedding vector
            embedding2: Second normalized embedding vector

        Returns:
            Cosine similarity value (0.0 to 1.0)
        """
        if not embedding1 or not embedding2:
            return 0.0

        # Convert to numpy arrays for efficient computation
        vec1 = np.array(embedding1, dtype=np.float32)
        vec2 = np.array(embedding2, dtype=np.float32)

        # Since embeddings are normalized, cosine similarity = dot product
        similarity = np.dot(vec1, vec2)

        # Clamp to [0, 1] range (should already be in range, but safety check)
        return float(np.clip(similarity, 0.0, 1.0))

    def cosine_distance(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine distance between two normalized embeddings.

        Cosine distance = 1 - cosine similarity

        Args:
            embedding1: First normalized embedding vector
            embedding2: Second normalized embedding vector

        Returns:
            Cosine distance value (0.0 to 1.0)
        """
        similarity = self.cosine_similarity(embedding1, embedding2)
        return 1.0 - similarity

    def batch_cosine_distances(self, embeddings: List[List[float]]) -> List[float]:
        """
        Calculate cosine distances between adjacent embeddings.

        Args:
            embeddings: List of normalized embedding vectors

        Returns:
            List of cosine distances (one less than input length)
        """
        if len(embeddings) < 2:
            return []

        distances = []
        for i in range(len(embeddings) - 1):
            distance = self.cosine_distance(embeddings[i], embeddings[i + 1])
            distances.append(distance)

        return distances

    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self.embedding_client is not None


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get global embedding service instance."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
