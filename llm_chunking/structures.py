"""
Chunk structure interfaces for different chunking strategies.

Defines three main structure types:
- GeneralStructure: Flat chunks (default)
- ParentChildStructure: Hierarchical chunks (parent-child)
- QAStructure: Question-answer pairs
"""
from abc import ABC, abstractmethod
from typing import List, Any, Optional

from llm_chunking.models import (
    Chunk,
    ParentChunk,
    QAChunk,
    DocumentStructure,
)


class ChunkStructure(ABC):
    """Base interface for chunk structures."""

    @property
    @abstractmethod
    def structure_type(self) -> str:
        """Return structure type identifier."""

    @abstractmethod
    def chunk(
        self,
        text: str,
        structure: Optional[DocumentStructure] = None,
        **kwargs
    ) -> List[Any]:
        """
        Chunk text according to structure.

        Args:
            text: Text to chunk
            structure: Optional document structure from sampling
            **kwargs: Additional parameters

        Returns:
            List of chunks (type depends on structure)
        """


class GeneralStructure(ChunkStructure):
    """
    General (flat) chunk structure.

    Best for: Blog posts, articles, simple documentation
    All chunks indexed equally in vector DB.
    """

    @property
    def structure_type(self) -> str:
        """Return structure type."""
        return "general"

    def chunk(
        self,
        text: str,
        structure: Optional[DocumentStructure] = None,
        chunk_size: int = 500,
        overlap: int = 50,
        **kwargs
    ) -> List[Chunk]:
        """
        Create flat chunks.

        Args:
            text: Text to chunk
            structure: Optional document structure
            chunk_size: Target chunk size in tokens
            overlap: Overlap tokens between chunks
            **kwargs: Additional parameters

        Returns:
            List of Chunk objects
        """
        # Implementation will be in chunker.py
        # This is just the interface
        raise NotImplementedError("Use LLMSemanticChunker for implementation")


class ParentChildStructure(ChunkStructure):
    """
    Parent-child hierarchical chunk structure.

    Best for: Books, manuals, structured documents
    Only child chunks indexed; parent context included on retrieval.

    Parent modes:
    - paragraph: Each paragraph is a parent
    - full_document: Entire document is one parent
    """

    def __init__(self, parent_mode: str = "paragraph"):
        """
        Initialize parent-child structure.

        Args:
            parent_mode: "paragraph" or "full_document"
        """
        self.parent_mode = parent_mode

    @property
    def structure_type(self) -> str:
        """Return structure type."""
        return "parent_child"

    def chunk(
        self,
        text: str,
        structure: Optional[DocumentStructure] = None,
        parent_max_tokens: int = 2000,
        child_max_tokens: int = 500,
        **kwargs
    ) -> List[ParentChunk]:
        """
        Create hierarchical chunks.

        Args:
            text: Text to chunk
            structure: Optional document structure
            parent_max_tokens: Maximum tokens per parent chunk
            child_max_tokens: Maximum tokens per child chunk
            **kwargs: Additional parameters

        Returns:
            List of ParentChunk objects
        """
        # Implementation will be in chunker.py
        raise NotImplementedError("Use LLMSemanticChunker for implementation")


class QAStructure(ChunkStructure):
    """
    Question-answer pair structure.

    Best for: FAQ documents, help docs, customer support
    LLM-generated questions or manual Q&A pairs.
    Question-based semantic search.
    """

    @property
    def structure_type(self) -> str:
        """Return structure type."""
        return "qa"

    def chunk(
        self,
        text: str,
        structure: Optional[DocumentStructure] = None,
        generate_questions: bool = True,
        **kwargs
    ) -> List[QAChunk]:
        """
        Create Q&A chunks.

        Args:
            text: Text to chunk
            structure: Optional document structure
            generate_questions: If True, LLM generates questions from text
            **kwargs: Additional parameters

        Returns:
            List of QAChunk objects
        """
        # Implementation will be in chunker.py
        raise NotImplementedError("Use LLMSemanticChunker for implementation")


def get_structure(structure_type: str, **kwargs) -> ChunkStructure:
    """
    Factory function to get chunk structure.

    Args:
        structure_type: "general", "parent_child", or "qa"
        **kwargs: Structure-specific parameters

    Returns:
        ChunkStructure instance
    """
    structures = {
        "general": GeneralStructure,
        "parent_child": ParentChildStructure,
        "qa": QAStructure,
    }

    if structure_type not in structures:
        raise ValueError(
            f"Unknown structure type: {structure_type}. "
            f"Must be one of: {list(structures.keys())}"
        )

    structure_class = structures[structure_type]
    return structure_class(**kwargs)
