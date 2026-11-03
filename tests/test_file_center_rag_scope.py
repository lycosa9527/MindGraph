"""Package-scoped RAG isolation tests for File Center.

Covers the pieces that keep diagram completion scoped to a package's documents
instead of the whole library:

* ``resolve_diagram_rag_scope`` — returns only completed package doc IDs.
* ``rag_context_state`` — suppresses implicit whole-library RAG.
* Keyword filter builders — translate a ``document_id`` *list* into a
  "match any of these docs" clause.
"""

from __future__ import annotations

from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.knowledge.package_rag_scope import (
    PackageRagScope,
    personal_package_id_for_scope,
    resolve_diagram_rag_scope,
)
from services.knowledge.keyword_search_service import _append_document_id_clause
from services.llm.rag_context_state import is_implicit_rag_suppressed, suppress_implicit_rag


class _FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        """Return the canned scalar list."""
        return self._items


class _FakeResult:
    def __init__(self, scalar=None, scalars_list=None):
        self._scalar = scalar
        self._scalars_list = scalars_list or []

    def scalar_one_or_none(self):
        """Return the canned scalar value."""
        return self._scalar

    def scalars(self):
        """Return a scalars proxy over the canned list."""
        return _FakeScalars(self._scalars_list)


class _FakeSession:
    """Async session stub that returns canned results in call order."""

    def __init__(self, results):
        self._results = list(results)
        self.calls = 0

    async def execute(self, _stmt):
        """Return the next canned result for each execute call."""
        result = self._results[self.calls]
        self.calls += 1
        return result

    async def get(self, _model, _ident):
        """Package source is empty unless a test supplies a batch."""
        return None


@pytest.mark.asyncio
async def test_resolve_scope_none_without_package():
    """A diagram with no linked package resolves to None (whole-library decision deferred)."""
    session = _FakeSession([_FakeResult(scalar=None), _FakeResult(scalar=None)])
    scope = await resolve_diagram_rag_scope(cast(AsyncSession, session), user_id=1, diagram_id="d1")
    assert scope is None


@pytest.mark.asyncio
async def test_resolve_scope_returns_completed_docs():
    """A linked package resolves to its completed document IDs."""
    session = _FakeSession(
        [
            _FakeResult(scalar=7),
            _FakeResult(scalars_list=[11, 12, 13]),
            _FakeResult(scalar=0),
        ]
    )
    scope = await resolve_diagram_rag_scope(cast(AsyncSession, session), user_id=1, diagram_id="d1")
    assert scope is not None
    assert scope == PackageRagScope(package_id=7, document_ids=[11, 12, 13])
    assert scope.has_corpus is True


def test_scope_empty_corpus_flag():
    """A package with no completed sources reports an empty corpus."""
    assert PackageRagScope(package_id=7, document_ids=[]).has_corpus is False


def test_suppress_implicit_rag_context():
    """The suppression flag is off by default and only set within the context."""
    assert is_implicit_rag_suppressed() is False
    with suppress_implicit_rag():
        assert is_implicit_rag_suppressed() is True
    assert is_implicit_rag_suppressed() is False


def test_keyword_clause_with_list():
    """A document_id list expands to an IN (...) clause with bound params."""
    params: dict = {}
    sql = _append_document_id_clause("SELECT 1 WHERE 1=1", params, [11, 12])
    assert "dc.document_id IN (:doc_id_0, :doc_id_1)" in sql
    assert params == {"doc_id_0": 11, "doc_id_1": 12}


def test_keyword_clause_with_single_id():
    """A single document_id expands to an equality clause."""
    params: dict = {}
    sql = _append_document_id_clause("SELECT 1 WHERE 1=1", params, 11)
    assert "dc.document_id = :document_id" in sql
    assert params == {"document_id": 11}


def test_personal_context_follows_a_finished_personal_folder():
    """A finished personal folder is used. An empty, busy, or document-summary folder is not."""
    empty = PackageRagScope(package_id=8, source="knowledge_space", document_ids=[])
    ready = PackageRagScope(package_id=8, source="knowledge_space", document_ids=[114])
    busy = PackageRagScope(package_id=8, source="knowledge_space", document_ids=[114], open_count=1)
    canvas = PackageRagScope(package_id=8, source="canvas", document_ids=[114])
    extension = PackageRagScope(package_id=8, source="chrome_extension", document_ids=[114])
    summary = PackageRagScope(package_id=8, source="doc_summary", document_ids=[114])
    assert personal_package_id_for_scope(None) is None
    assert personal_package_id_for_scope(empty) is None
    assert personal_package_id_for_scope(busy) is None
    assert personal_package_id_for_scope(summary) is None
    assert personal_package_id_for_scope(canvas) == 8
    assert personal_package_id_for_scope(extension) == 8
    assert personal_package_id_for_scope(ready) == 8


def test_keyword_clause_with_empty_list_is_noop():
    """An empty document_id list adds no clause (no accidental whole-library widening)."""
    params: dict = {}
    sql = _append_document_id_clause("SELECT 1 WHERE 1=1", params, [])
    assert sql == "SELECT 1 WHERE 1=1"
    assert not params
