"""Unit tests for MindChunk hardening.

Covers MindChunkAdapter conversion (general / parent-child / QA), structure
cache invalidation, structure-agent heuristic fallback, and the
document_processing MindChunk -> semchunk fallback path.
"""

from __future__ import annotations

from typing import cast

import pytest

from llm_chunking.agents.structure_agent import StructureAgent
from llm_chunking.models import ChildChunk, DocumentStructure, ParentChunk, QAChunk
from llm_chunking.models import Chunk as LCChunk
from models.domain.knowledge_space import KnowledgeDocument
from services.knowledge import document_processing as dp
from services.knowledge.chunking_service import MindChunkAdapter


class _FakeChunker:
    """Minimal stand-in for LLMSemanticChunker."""

    def __init__(self, result, cache_manager=None):
        self._result = result
        self.cache_manager = cache_manager

    async def chunk(self, text, document_id, structure_type=None, pdf_outline=None, **kwargs):
        """Return the canned chunk list regardless of inputs."""
        del text, document_id, structure_type, pdf_outline, kwargs
        return self._result


class _FakeCache:
    def __init__(self):
        self.deleted = []

    def delete_structure(self, document_id):
        """Record the deleted structure id."""
        self.deleted.append(document_id)


@pytest.mark.asyncio
async def test_adapter_general_conversion():
    """Flat general chunks keep document_id and are tagged structure_type=general."""
    llm_chunks = [LCChunk(text="hello world", start_char=0, end_char=11, chunk_index=0, token_count=3)]
    adapter = MindChunkAdapter(_FakeChunker(llm_chunks))

    chunks = await adapter.chunk_text_async("hello world", metadata={"document_id": 5})

    assert len(chunks) == 1
    assert chunks[0].metadata["structure_type"] == "general"
    assert chunks[0].metadata["document_id"] == 5


@pytest.mark.asyncio
async def test_adapter_parent_child_sets_section_title():
    """Parent-child conversion flattens children and propagates section_title."""
    child = ChildChunk(text="child text", start_char=0, end_char=10, chunk_index=0)
    parent = ParentChunk(
        text="Chapter 5 body",
        start_char=0,
        end_char=14,
        chunk_index=0,
        children=[child],
        metadata={"title": "Chapter 5"},
    )
    adapter = MindChunkAdapter(_FakeChunker([parent]))

    chunks = await adapter.chunk_text_async("Chapter 5 body", metadata={"document_id": 7})

    assert len(chunks) == 1
    assert chunks[0].metadata["structure_type"] == "parent_child"
    assert chunks[0].metadata["section_title"] == "Chapter 5"
    assert chunks[0].metadata["parent_text"] == "Chapter 5 body"


@pytest.mark.asyncio
async def test_adapter_qa_conversion():
    """QA chunks carry question/answer and structure_type=qa."""
    qa = QAChunk(text="", start_char=0, end_char=5, chunk_index=0, question="Q1", answer="A1")
    adapter = MindChunkAdapter(_FakeChunker([qa]))

    chunks = await adapter.chunk_text_async("irrelevant", metadata={"document_id": 9})

    assert chunks[0].metadata["structure_type"] == "qa"
    assert chunks[0].metadata["question"] == "Q1"
    assert chunks[0].metadata["answer"] == "A1"


def test_adapter_invalidate_structure_delegates():
    """invalidate_structure forwards the stringified id to the cache manager."""
    cache = _FakeCache()
    adapter = MindChunkAdapter(_FakeChunker([], cache_manager=cache))

    adapter.invalidate_structure(123)

    assert cache.deleted == ["123"]


@pytest.mark.asyncio
async def test_structure_agent_heuristic_fallback_when_no_llm():
    """StructureAgent without an LLM still returns a valid DocumentStructure."""
    agent = StructureAgent(llm_service=None)
    structure = await agent.analyze_structure("Some plain text without a table of contents.", document_id="doc1")

    assert isinstance(structure, DocumentStructure)
    assert structure.structure_type in {"general", "parent_child", "qa"}


@pytest.mark.asyncio
async def test_chunk_text_with_mode_falls_back_to_semchunk(monkeypatch):
    """When MindChunk raises, chunking falls back to semchunk and still returns chunks."""
    monkeypatch.setenv("CHUNKING_ENGINE", "mindchunk")

    class _FailingAdapter:
        async def chunk_text_async(self, **kwargs):
            """Always fail to force the semchunk fallback path."""
            del kwargs
            raise RuntimeError("LLM unavailable")

    class _Doc:
        id = 42
        language = "en"

    text = "Sentence one. Sentence two. Sentence three. " * 40
    chunks = await dp.chunk_text_with_mode(
        _FailingAdapter(), text, cast(KnowledgeDocument, _Doc()), None, None, 42, user_id=1
    )

    assert chunks, "Expected semchunk fallback to produce chunks"
