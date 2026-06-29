"""Package-scoped RAG context retrieval for diagram completion.

Centralizes the "resolve a diagram's File Center package → retrieve its chunks →
format a prompt context block" flow so multiple LLM touchpoints (inline
recommendations, and future paths) stay consistent and never leak the whole
library. Retrieval is scoped via ``metadata_filter={"document_id": [...]}``.

At query time, relevant compiled wiki pages (overview + topic notes) are
prepended before chunk RAG hits — a lightweight map-then-retrieve pattern.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from config.settings import config
from services.knowledge import package_wiki_store as wiki_store
from services.knowledge.knowledge_settings import resolve_retrieval_params
from services.knowledge.package_rag_scope import (
    PackageRagScope,
    resolve_diagram_rag_scope,
    resolve_package_rag_scope_by_id,
)
from services.knowledge.section_query import is_section_summary_query, parse_section_hint
from services.llm.rag_service import get_rag_service
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.db.session_open import user_rls_session
from utils.prompt_locale import is_chinese_prompt_shell_language

logger = logging.getLogger(__name__)

# Keep injected context bounded so streaming prompts stay small/cheap.
DEFAULT_TOP_K = 5
MAX_CONTEXT_CHARS = 2000
SECTION_SUMMARY_MAX_CONTEXT_CHARS = 6000
MAX_WIKI_CONTEXT_CHARS = 650
WIKI_TOP_K = 2


@dataclass(frozen=True)
class PackageContextResult:
    """Outcome of a package-scoped context retrieval."""

    package_active: bool
    context_block: str
    retrieval_failed: bool = False


@dataclass(frozen=True)
class WikiSnippet:
    """A compiled wiki page title + body excerpt."""

    title: str
    body: str


async def resolve_package_context_block(
    user_id: Optional[int],
    diagram_id: Optional[str],
    query: str,
    language: str = "en",
    top_k: Optional[int] = None,
) -> PackageContextResult:
    """Resolve a diagram's package scope and build a RAG context block.

    Returns ``package_active=False`` (and an empty block) when the diagram has no
    linked package with completed sources — the caller then keeps its existing
    behavior. When active, the block holds package-scoped chunks ready to prepend
    to an LLM prompt; callers should also suppress implicit whole-library RAG.
    """
    if not user_id or not diagram_id or not query:
        return PackageContextResult(False, "")

    # File Center is gated; skip package resolution entirely when disabled.
    if not config.FEATURE_KNOWLEDGE_SPACE:
        return PackageContextResult(False, "")

    try:
        async with user_rls_session(int(user_id)) as db:
            scope = await resolve_diagram_rag_scope(db, int(user_id), str(diagram_id))
        return await resolve_package_context_for_scope(
            user_id,
            scope,
            query,
            language,
            top_k,
            stage="inline_recommendations",
        )
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning("[FileCenterRAG] Failed to retrieve package context for diagram %s: %s", diagram_id, exc)
        return PackageContextResult(False, "")


def _retrieve_wiki_snippets(user_id: int, package_id: int, query: str) -> List[WikiSnippet]:
    """Load title-matched wiki pages for the query (filesystem, no embeddings)."""
    pages = wiki_store.find_relevant_pages(user_id, package_id, query, top_k=WIKI_TOP_K)
    snippets: List[WikiSnippet] = []
    for page in pages:
        slug = page.get("slug")
        if not slug:
            continue
        body = wiki_store.read_page_body(user_id, package_id, str(slug))
        if not body:
            continue
        title = str(page.get("title") or slug)
        snippets.append(WikiSnippet(title=title, body=body))
    return snippets


def _format_wiki_section(snippets: List[WikiSnippet], language: str) -> str:
    if not snippets:
        return ""
    lines: List[str] = []
    budget = MAX_WIKI_CONTEXT_CHARS
    for snippet in snippets:
        line = f"[{snippet.title}]: {snippet.body}"
        if len(line) > budget:
            line = line[:budget].rstrip()
        lines.append(line)
        budget -= len(line)
        if budget <= 0:
            break
    body = "\n\n".join(lines)
    if is_chinese_prompt_shell_language(language):
        return f"资料包维基摘要（主题概览）：\n{body}"
    return f"Package wiki notes (topic overview):\n{body}"


def _format_chunk_section(chunks: List[str], language: str, max_chars: int) -> str:
    if not chunks:
        return ""
    if is_chinese_prompt_shell_language(language):
        body = "\n\n".join(f"[知识库参考 {i + 1}]: {chunk}" for i, chunk in enumerate(chunks))[:max_chars]
        return f"相关背景知识（来自该图表的文档总结资料包）：\n{body}\n\n请仅基于以上资料生成更准确的结果。"
    body = "\n\n".join(f"[Knowledge Base Reference {i + 1}]: {chunk}" for i, chunk in enumerate(chunks))[:max_chars]
    return (
        f"Relevant context (from this diagram's Document Summary package):\n{body}\n\n"
        "Base your response only on the context above."
    )


def _format_context_block(
    chunks: List[str],
    language: str,
    wiki_snippets: Optional[List[WikiSnippet]] = None,
    max_context_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    wiki_section = _format_wiki_section(wiki_snippets or [], language)
    wiki_len = len(wiki_section)
    chunk_budget = max(0, max_context_chars - wiki_len - (2 if wiki_section else 0))
    chunk_section = _format_chunk_section(chunks, language, chunk_budget)
    if wiki_section and chunk_section:
        return f"{wiki_section}\n\n{chunk_section}"
    if wiki_section:
        return wiki_section
    return chunk_section


async def _retrieve_chunks_for_scope(
    user_id: int,
    scope: PackageRagScope,
    query: str,
    top_k: Optional[int],
    stage: str,
) -> List[str]:
    rag_service = get_rag_service()
    section_hint = parse_section_hint(query)
    is_summary = is_section_summary_query(query)
    context_budget = SECTION_SUMMARY_MAX_CONTEXT_CHARS if is_summary else MAX_CONTEXT_CHARS

    async with user_rls_session(int(user_id)) as db:
        method, resolved_top_k, score_threshold = await resolve_retrieval_params(
            db,
            user_id,
            method="hybrid",
            top_k=top_k,
            score_threshold=None,
        )
        if section_hint is not None:
            section_texts = await rag_service.retrieve_section_context(
                db=db,
                user_id=user_id,
                section_key=section_hint.section_key,
                document_ids=scope.document_ids,
                max_chars=context_budget,
                section_number=section_hint.section_number,
                section_label=section_hint.label,
            )
            if section_texts:
                logger.info(
                    "[FileCenterRAG] Section-scoped retrieval key=%s chunks=%s stage=%s package=%s",
                    section_hint.section_key,
                    len(section_texts),
                    stage,
                    scope.package_id,
                )
                return section_texts

        return await rag_service.retrieve_context(
            db=db,
            user_id=user_id,
            query=query,
            method=method,
            top_k=resolved_top_k,
            score_threshold=score_threshold,
            source="diagram_completion",
            source_context={"stage": stage},
            metadata_filter={"document_id": scope.document_ids},
        )


async def resolve_package_context_for_scope(
    user_id: Optional[int],
    scope: Optional[PackageRagScope],
    query: str,
    language: str = "en",
    top_k: Optional[int] = None,
    stage: str = "doc_summary",
) -> PackageContextResult:
    """Build a RAG context block from a pre-resolved package scope."""
    if not user_id or not scope or not scope.has_corpus or not query:
        return PackageContextResult(False, "")
    if not config.FEATURE_KNOWLEDGE_SPACE:
        return PackageContextResult(False, "")

    wiki_snippets = _retrieve_wiki_snippets(int(user_id), scope.package_id, query)

    try:
        chunks = await _retrieve_chunks_for_scope(int(user_id), scope, query, top_k, stage)
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning("[FileCenterRAG] Failed to retrieve package context: %s", exc)
        if stage == "doc_summary_generate":
            return PackageContextResult(True, "", retrieval_failed=True)
        return PackageContextResult(False, "")

    if not chunks and not wiki_snippets:
        return PackageContextResult(True, "")

    context_budget = SECTION_SUMMARY_MAX_CONTEXT_CHARS if is_section_summary_query(query) else MAX_CONTEXT_CHARS
    block = _format_context_block(chunks, language, wiki_snippets, max_context_chars=context_budget)
    logger.info(
        "[FileCenterRAG] Injecting %d wiki page(s) + %d chunk(s) stage=%s package=%s",
        len(wiki_snippets),
        len(chunks),
        stage,
        scope.package_id,
    )
    return PackageContextResult(True, block)


async def resolve_package_context_by_package_id(
    user_id: Optional[int],
    package_id: Optional[int],
    query: str,
    language: str = "en",
    top_k: Optional[int] = None,
) -> PackageContextResult:
    """Resolve RAG context for a package id (unsaved diagram sessions)."""
    if not user_id or not package_id or not query:
        return PackageContextResult(False, "")
    if not config.FEATURE_KNOWLEDGE_SPACE:
        return PackageContextResult(False, "")

    try:
        async with user_rls_session(int(user_id)) as db:
            scope = await resolve_package_rag_scope_by_id(db, int(user_id), int(package_id))
        return await resolve_package_context_for_scope(
            user_id, scope, query, language, top_k, stage="doc_summary_generate"
        )
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning("[FileCenterRAG] package_id=%s retrieve failed: %s", package_id, exc)
        return PackageContextResult(False, "")
