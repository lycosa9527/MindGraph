"""Embedding adapters for different chunk structures.

Adapts embedding generation to different chunk types:
- General: Embed each chunk independently
- Parent-Child: Embed only child chunks, store parent in payload
- Q&A: Embed questions (or Q&A pairs)
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union
import logging

from llm_chunking.models import Chunk, ParentChunk, QAChunk

try:
    from clients.dashscope_embedding import get_embedding_client
except ImportError:
    get_embedding_client = None

logger = logging.getLogger(__name__)


class EmbeddingAdapter(ABC):
    """Base interface for embedding adapters."""

    def __init__(self, embedding_client=None):
        """
        Initialize adapter.

        Args:
            embedding_client: Embedding client instance
        """
        self.embedding_client = embedding_client
        if embedding_client is None:
            if get_embedding_client is None:
                logger.warning("Embedding client not available: import failed")
            else:
                try:
                    self.embedding_client = get_embedding_client()
                except Exception as e:
                    logger.warning("Embedding client not available: %s", e)

    @abstractmethod
    def embed_chunks(
        self,
        chunks: Union[List[Chunk], List[ParentChunk], List[QAChunk]],
        structure_type: str
    ) -> List[Dict[str, Any]]:
        """
        Embed chunks based on structure type.

        Args:
            chunks: List of chunks
            structure_type: Structure type identifier

        Returns:
            List of dicts with 'id', 'vector', 'payload'
        """


class GeneralEmbeddingAdapter(EmbeddingAdapter):
    """Adapter for General (flat) chunks."""

    def embed_chunks(
        self,
        chunks: List[Chunk],
        structure_type: str = "general"
    ) -> List[Dict[str, Any]]:
        """
        Embed each chunk independently.

        Args:
            chunks: List of Chunk objects
            structure_type: Structure type (ignored)

        Returns:
            List of embedding data dicts
        """
        if not self.embedding_client:
            raise ValueError("Embedding client not available")

        # Extract texts
        texts = [chunk.text for chunk in chunks]

        # Generate embeddings
        embeddings = self.embedding_client.embed_texts(
            texts=texts,
            text_type="document"
        )

        # Build result list
        results = []
        for chunk, embedding in zip(chunks, embeddings):
            results.append({
                "id": f"chunk_{chunk.chunk_index}",
                "vector": embedding,
                "payload": {
                    "text": chunk.text,
                    "metadata": chunk.metadata,
                    "chunk_index": chunk.chunk_index,
                    "chunk_type": "general",
                    "start_char": chunk.start_char,
                    "end_char": chunk.end_char,
                    "token_count": chunk.token_count,
                }
            })

        return results


class ParentChildEmbeddingAdapter(EmbeddingAdapter):
    """Adapter for Parent-Child chunks."""

    def embed_chunks(
        self,
        chunks: List[ParentChunk],
        structure_type: str = "parent_child"
    ) -> List[Dict[str, Any]]:
        """
        Embed only child chunks, store parent in payload.

        Args:
            chunks: List of ParentChunk objects
            structure_type: Structure type (ignored)

        Returns:
            List of embedding data dicts (one per child chunk)
        """
        if not self.embedding_client:
            raise ValueError("Embedding client not available")

        # Extract all child chunks
        all_child_chunks = []
        for parent in chunks:
            for child in parent.children:
                all_child_chunks.append({
                    "id": f"parent_{parent.chunk_index}_child_{child.chunk_index}",
                    "text": child.text,
                    "parent_text": parent.text,
                    "parent_id": f"parent_{parent.chunk_index}",
                    "parent_index": parent.chunk_index,
                    "child_index": child.chunk_index,
                    "metadata": child.metadata or {},
                    "parent_metadata": parent.metadata or {},
                })

        if not all_child_chunks:
            return []

        # Embed child chunks only
        child_texts = [child["text"] for child in all_child_chunks]
        embeddings = self.embedding_client.embed_texts(
            texts=child_texts,
            text_type="document"
        )

        # Build result list
        results = []
        for child_data, embedding in zip(all_child_chunks, embeddings):
            results.append({
                "id": child_data["id"],
                "vector": embedding,
                "payload": {
                    "text": child_data["text"],
                    "parent_text": child_data["parent_text"],  # Include parent for context
                    "parent_id": child_data["parent_id"],
                    "parent_index": child_data["parent_index"],
                    "child_index": child_data["child_index"],
                    "metadata": child_data["metadata"],
                    "parent_metadata": child_data["parent_metadata"],
                    "chunk_type": "child",
                }
            })

        return results


class QAEmbeddingAdapter(EmbeddingAdapter):
    """Adapter for Q&A chunks."""

    def embed_chunks(
        self,
        chunks: List[QAChunk],
        structure_type: str = "qa",
        embed_mode: str = "questions_only"
    ) -> List[Dict[str, Any]]:
        """
        Embed Q&A chunks.

        Args:
            chunks: List of QAChunk objects
            structure_type: Structure type (ignored)
            embed_mode: "questions_only" or "qa_pairs"

        Returns:
            List of embedding data dicts
        """
        if not self.embedding_client:
            raise ValueError("Embedding client not available")

        if embed_mode == "questions_only":
            # Embed questions only (recommended for FAQ-style retrieval)
            texts = [qa.question for qa in chunks]
            text_type = "query"  # Questions are queries
        else:
            # Embed Q&A pairs together
            texts = [
                f"Q: {qa.question}\nA: {qa.answer}"
                for qa in chunks
            ]
            text_type = "document"

        # Generate embeddings
        embeddings = self.embedding_client.embed_texts(
            texts=texts,
            text_type=text_type
        )

        # Build result list
        results = []
        for qa, embedding in zip(chunks, embeddings):
            results.append({
                "id": f"qa_{qa.chunk_index}",
                "vector": embedding,
                "payload": {
                    "question": qa.question,
                    "answer": qa.answer,
                    "qa_text": f"Q: {qa.question}\nA: {qa.answer}",
                    "metadata": qa.metadata,
                    "chunk_index": qa.chunk_index,
                    "qa_index": qa.qa_index,
                    "chunk_type": "qa",
                }
            })

        return results


def get_embedding_adapter(structure_type: str, **kwargs) -> EmbeddingAdapter:
    """
    Factory function to get appropriate embedding adapter.

    Args:
        structure_type: "general", "parent_child", or "qa"
        **kwargs: Additional adapter parameters

    Returns:
        EmbeddingAdapter instance
    """
    adapters = {
        "general": GeneralEmbeddingAdapter,
        "parent_child": ParentChildEmbeddingAdapter,
        "qa": QAEmbeddingAdapter,
    }

    if structure_type not in adapters:
        raise ValueError(
            f"Unknown structure type: {structure_type}. "
            f"Must be one of: {list(adapters.keys())}"
        )

    adapter_class = adapters[structure_type]
    return adapter_class(**kwargs)
