"""Tests for the File Center per-source chunking policy.

PDF/DOCX get hierarchical semchunk (so ``section_title`` survives for branch
retrieval); web/paste text gets flat semchunk; an explicit space mode always
wins; the engine follows ``CHUNKING_ENGINE``.
"""

from __future__ import annotations

from services.knowledge.chunking_policy import resolve_chunking_policy


def test_pdf_defaults_to_hierarchical():
    """PDF sources default to hierarchical mode."""
    policy = resolve_chunking_policy("application/pdf", None)
    assert policy.mode == "hierarchical"
    assert policy.engine == "semchunk"


def test_docx_defaults_to_hierarchical():
    """DOCX sources default to hierarchical mode."""
    docx = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert resolve_chunking_policy(docx, None).mode == "hierarchical"


def test_markdown_web_paste_is_flat():
    """Markdown (web/paste snapshots) defaults to flat automatic mode."""
    assert resolve_chunking_policy("text/markdown", None).mode == "automatic"


def test_explicit_mode_wins():
    """An explicit space mode overrides the file-type default."""
    policy = resolve_chunking_policy("application/pdf", {"mode": "automatic"})
    assert policy.mode == "automatic"


def test_engine_follows_env(monkeypatch):
    """The engine honors CHUNKING_ENGINE; default stays semchunk."""
    monkeypatch.setenv("CHUNKING_ENGINE", "mindchunk")
    assert resolve_chunking_policy("text/markdown", None).engine == "mindchunk"
    monkeypatch.setenv("CHUNKING_ENGINE", "semchunk")
    assert resolve_chunking_policy("text/markdown", None).engine == "semchunk"
