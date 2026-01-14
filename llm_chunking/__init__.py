"""
LLM-Based Semantic Chunking Module

A comprehensive chunking system that uses LLM for semantic boundary detection,
supporting multiple chunk structures (General, Parent-Child, Q&A) with performance
optimizations including 30-page sampling, batch processing, and caching.

Author: MindSpring Team
Copyright 2024-2025 北京思源智教科技有限公司
"""

from llm_chunking.chunker import LLMSemanticChunker
from llm_chunking.models import (
    Chunk,
    ParentChunk,
    ChildChunk,
    QAChunk,
    TeachingChunk,
)
from llm_chunking.structures import (
    GeneralStructure,
    ParentChildStructure,
    QAStructure,
)

__all__ = [
    "LLMSemanticChunker",
    "Chunk",
    "ParentChunk",
    "ChildChunk",
    "QAChunk",
    "TeachingChunk",
    "GeneralStructure",
    "ParentChildStructure",
    "QAStructure",
]

__version__ = "1.0.0"
