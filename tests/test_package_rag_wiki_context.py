"""Tests for wiki-augmented package RAG context formatting."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from services.knowledge import package_rag_context as rag_context
from services.knowledge.package_rag_context import (
    WikiSnippet,
    _format_context_block,
    _retrieve_wiki_snippets,
    resolve_package_context_for_scope,
)
from services.knowledge.package_rag_scope import PackageRagScope


def test_format_context_block_includes_wiki_and_chunks():
    """Wiki section precedes chunk RAG in the combined prompt block."""
    block = _format_context_block(
        chunks=["chunk one", "chunk two"],
        language="en",
        wiki_snippets=[WikiSnippet(title="Overview", body="Package summary.")],
    )
    assert "Package wiki notes" in block
    assert "[Overview]: Package summary." in block
    assert "[Knowledge Base Reference 1]: chunk one" in block
    assert block.index("Package wiki notes") < block.index("[Knowledge Base Reference 1]")


def test_format_context_block_wiki_only():
    """Wiki-only context is returned when chunk retrieval finds nothing."""
    block = _format_context_block(
        chunks=[],
        language="zh",
        wiki_snippets=[WikiSnippet(title="概述", body="资料包摘要。")],
    )
    assert "资料包维基摘要" in block
    assert "概述" in block
    assert "Knowledge Base Reference" not in block


def test_retrieve_wiki_snippets_reads_matching_pages(tmp_path, monkeypatch):
    """Title/slug matching loads stripped markdown bodies from disk."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    wiki_root = tmp_path / "user_1" / "packages" / "9" / "wiki"
    wiki_root.mkdir(parents=True)
    (wiki_root / "_index.json").write_text(
        '{"pages": [{"slug": "overview", "title": "Overview"}]}',
        encoding="utf-8",
    )
    (wiki_root / "overview.md").write_text(
        "---\nslug: overview\ntitle: Overview\n---\n\nSummary body.\n",
        encoding="utf-8",
    )

    snippets = _retrieve_wiki_snippets(1, 9, "overview summary")
    assert len(snippets) == 1
    assert snippets[0].title == "Overview"
    assert snippets[0].body == "Summary body."


@pytest.mark.asyncio
async def test_resolve_package_context_for_scope_merges_wiki_and_chunks(monkeypatch, tmp_path):
    """Active package context includes wiki notes plus retrieved chunks."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))

    monkeypatch.setattr(
        type(rag_context.config),
        "FEATURE_KNOWLEDGE_SPACE",
        property(lambda _self: True),
    )
    wiki_root = tmp_path / "user_1" / "packages" / "3" / "wiki"
    wiki_root.mkdir(parents=True)
    (wiki_root / "_index.json").write_text(
        '{"pages": [{"slug": "overview", "title": "Overview"}]}',
        encoding="utf-8",
    )
    (wiki_root / "overview.md").write_text("Overview text.\n", encoding="utf-8")

    scope = PackageRagScope(package_id=3, document_ids=[10, 11])
    with patch(
        "services.knowledge.package_rag_context._retrieve_chunks_for_scope",
        new=AsyncMock(return_value=["detail chunk"]),
    ):
        result = await resolve_package_context_for_scope(
            user_id=1,
            scope=scope,
            query="overview topic",
            language="en",
            top_k=3,
        )

    assert result.package_active is True
    assert "Overview text." in result.context_block
    assert "detail chunk" in result.context_block
