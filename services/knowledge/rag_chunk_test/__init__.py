"""
RAG Chunk Test Module
=====================

Module for testing and comparing different chunking methods (semchunk vs mindchunk)
using benchmark datasets and user documents.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""
from services.knowledge.rag_chunk_test.rag_chunk_test_service import (
    RAGChunkTestService,
    get_rag_chunk_test_service
)

__all__ = [
    'RAGChunkTestService',
    'get_rag_chunk_test_service'
]
