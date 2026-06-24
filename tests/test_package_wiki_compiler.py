"""Tests for the File Center package wiki compiler (v2a).

Covers JSON parsing, disk writes (markdown + manifest), the read-only store
helpers, and an end-to-end compile pass with a stubbed LLM and DB session.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from services.knowledge import package_wiki_compiler as compiler
from services.knowledge import package_wiki_store as store
from services.knowledge.package_wiki_compiler import _apply_page_actions, _parse_pages


@pytest.fixture(autouse=True)
def _isolated_storage(tmp_path, monkeypatch):
    """Point KNOWLEDGE_STORAGE_DIR at a temp dir for every test."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    return tmp_path


def test_parse_pages_extracts_valid_pages():
    """A well-formed JSON response yields page dicts with slugs."""
    response = '```json\n{"pages": [{"action": "create", "slug": "overview", "title": "T", "body_md": "B"}]}\n```'
    pages = _parse_pages(response)
    assert len(pages) == 1
    assert pages[0]["slug"] == "overview"


def test_parse_pages_ignores_garbage():
    """Non-JSON or page-less responses return an empty list."""
    assert _parse_pages("no json here") == []
    assert _parse_pages('{"foo": 1}') == []


def test_apply_page_actions_writes_files_and_manifest():
    """Page actions write markdown files and a manifest readable via the store."""
    pages = [
        {"slug": "overview", "title": "Overview", "body_md": "Big picture", "links": []},
        {"slug": "chapter-5", "title": "Chapter 5", "body_md": "CNNs", "links": []},
    ]
    written = _apply_page_actions(
        user_id=1, package_id=9, document_id=42, existing_index=[], pages=pages
    )
    assert written == 2

    index = store.list_pages(1, 9)
    slugs = {page["slug"] for page in index}
    assert slugs == {"overview", "chapter-5"}

    body = store.read_page(1, 9, "chapter-5")
    assert body is not None
    assert "CNNs" in body
    assert "source_document_ids" in body  # frontmatter present

    # source_document_ids carries the originating document.
    overview = next(page for page in index if page["slug"] == "overview")
    assert overview["source_document_ids"] == [42]


def test_apply_page_actions_merges_source_ids_on_update():
    """Updating an existing slug accumulates source document IDs."""
    _apply_page_actions(
        user_id=1, package_id=9, document_id=42, existing_index=[], pages=[
            {"slug": "overview", "title": "Overview", "body_md": "v1", "links": []},
        ]
    )
    existing = store.list_pages(1, 9)
    _apply_page_actions(
        user_id=1, package_id=9, document_id=43, existing_index=existing, pages=[
            {"slug": "overview", "title": "Overview", "body_md": "v2", "links": []},
        ]
    )
    overview = next(page for page in store.list_pages(1, 9) if page["slug"] == "overview")
    assert overview["source_document_ids"] == [42, 43]


def test_find_relevant_pages_matches_title_and_keeps_overview():
    """Relevant-page lookup matches titles and always retains the overview."""
    _apply_page_actions(
        user_id=1, package_id=9, document_id=42, existing_index=[], pages=[
            {"slug": "overview", "title": "Overview", "body_md": "x", "links": []},
            {"slug": "chapter-5", "title": "Convolutional Networks", "body_md": "x", "links": []},
        ]
    )
    relevant = store.find_relevant_pages(1, 9, "convolutional networks chapter")
    slugs = {page["slug"] for page in relevant}
    assert "chapter-5" in slugs
    assert "overview" in slugs


def test_delete_wiki_removes_folder():
    """Deleting the wiki removes all pages for the package."""
    _apply_page_actions(
        user_id=1, package_id=9, document_id=42, existing_index=[], pages=[
            {"slug": "overview", "title": "Overview", "body_md": "x", "links": []},
        ]
    )
    assert store.list_pages(1, 9)
    store.delete_wiki(1, 9)
    assert store.list_pages(1, 9) == []


def test_safe_slug_blocks_traversal():
    """Slugs are sanitized to defend against path traversal."""
    assert store.safe_slug("../../etc/passwd") == "etcpasswd"


class _FakeScalarResult:
    def __init__(self, first):
        self._first = first

    def scalars(self):
        """Return a scalars proxy exposing the canned first() value."""
        return SimpleNamespace(first=lambda: self._first)


class _FakeRowsResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        """Return the canned chunk rows."""
        return self._rows


class _FakeSession:
    """Async session stub for compile_package_wiki (package + chunks + document)."""

    def __init__(self, package, document, chunk_texts):
        self._execute_results = [
            _FakeScalarResult(package),
            _FakeRowsResult([(text,) for text in chunk_texts]),
        ]
        self._document = document
        self._i = 0

    async def execute(self, _stmt):
        """Return the next canned result for each execute call."""
        result = self._execute_results[self._i]
        self._i += 1
        return result

    async def get(self, _model, _pk):
        """Return the canned document."""
        return self._document


@pytest.mark.asyncio
async def test_compile_package_wiki_end_to_end(monkeypatch):
    """A full compile pass writes pages from a stubbed LLM response."""
    package = SimpleNamespace(id=9, name="Deep Learning", user_id=1)
    document = SimpleNamespace(
        id=42, language="en", file_name="book.pdf", doc_metadata={"page_title": "Book"}
    )
    session = _FakeSession(package, document, chunk_texts=["Intro to CNNs.", "More CNNs."])

    async def _fake_chat(*_args, **_kwargs):
        return '{"pages": [{"action": "create", "slug": "overview", "title": "Overview", "body_md": "Notes."}]}'

    monkeypatch.setattr(compiler.llm_service, "chat", _fake_chat)

    ok = await compiler.compile_package_wiki(cast(AsyncSession, session), user_id=1, package_id=9, document_id=42)
    assert ok is True

    index = store.list_pages(1, 9)
    assert any(page["slug"] == "overview" for page in index)


@pytest.mark.asyncio
async def test_compile_skips_unnamed_package(monkeypatch):
    """A package without a name (not a File Center package) is skipped."""
    session = _FakeSession(SimpleNamespace(id=9, name=None, user_id=1), None, [])

    async def _fail_chat(*_args, **_kwargs):
        raise AssertionError("LLM should not be called for unnamed packages")

    monkeypatch.setattr(compiler.llm_service, "chat", _fail_chat)
    ok = await compiler.compile_package_wiki(cast(AsyncSession, session), user_id=1, package_id=9, document_id=42)
    assert ok is False
