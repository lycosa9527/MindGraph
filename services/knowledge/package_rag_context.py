"""Package-scoped RAG context retrieval for diagram completion.

Centralizes the "resolve a diagram's File Center package → retrieve its chunks →
format a prompt context block" flow so multiple LLM touchpoints (inline
recommendations, and future paths) stay consistent and never leak the whole
library. Retrieval is scoped via ``metadata_filter={"document_id": [...]}``.

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
from services.knowledge.package_rag_scope import (
    PackageRagScope,
    resolve_diagram_rag_scope,
    resolve_package_rag_scope_by_id,
)
from services.llm.rag_service import get_rag_service
from services.utils.error_types import LLM_PIPELINE_ERRORS
from utils.db.session_open import user_rls_session
from utils.prompt_locale import is_chinese_prompt_shell_language

logger = logging.getLogger(__name__)

# Keep injected context bounded so streaming prompts stay small/cheap.
DEFAULT_TOP_K = 5
MAX_CONTEXT_CHARS = 2000


@dataclass(frozen=True)
class PackageContextResult:
    """Outcome of a package-scoped context retrieval."""

    package_active: bool
    context_block: str
    retrieval_failed: bool = False


async def resolve_package_context_block(
    user_id: Optional[int],
    diagram_id: Optional[str],
    query: str,
    language: str = "en",
    top_k: int = DEFAULT_TOP_K,
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


def _format_context_block(chunks: List[str], language: str) -> str:
    if is_chinese_prompt_shell_language(language):
        body = "\n\n".join(f"[知识库参考 {i + 1}]: {chunk}" for i, chunk in enumerate(chunks))[:MAX_CONTEXT_CHARS]
        return f"相关背景知识（来自该图表的文档总结资料包）：\n{body}\n\n请仅基于以上资料生成更准确的结果。"
    body = "\n\n".join(f"[Knowledge Base Reference {i + 1}]: {chunk}" for i, chunk in enumerate(chunks))[
        :MAX_CONTEXT_CHARS
    ]
    return (
        f"Relevant context (from this diagram's Document Summary package):\n{body}\n\n"
        "Base your response only on the context above."
    )


async def _retrieve_chunks_for_scope(
    user_id: int,
    scope: PackageRagScope,
    query: str,
    top_k: int,
    stage: str,
) -> List[str]:
    rag_service = get_rag_service()
    async with user_rls_session(int(user_id)) as db:
        return await rag_service.retrieve_context(
            db=db,
            user_id=user_id,
            query=query,
            method="hybrid",
            top_k=top_k,
            score_threshold=0.3,
            source="diagram_completion",
            source_context={"stage": stage},
            metadata_filter={"document_id": scope.document_ids},
        )


async def resolve_package_context_for_scope(
    user_id: Optional[int],
    scope: Optional[PackageRagScope],
    query: str,
    language: str = "en",
    top_k: int = DEFAULT_TOP_K,
    stage: str = "doc_summary",
) -> PackageContextResult:
    """Build a RAG context block from a pre-resolved package scope."""
    if not user_id or not scope or not scope.has_corpus or not query:
        return PackageContextResult(False, "")
    if not config.FEATURE_KNOWLEDGE_SPACE:
        return PackageContextResult(False, "")

    try:
        chunks = await _retrieve_chunks_for_scope(int(user_id), scope, query, top_k, stage)
    except LLM_PIPELINE_ERRORS as exc:
        logger.warning("[FileCenterRAG] Failed to retrieve package context: %s", exc)
        if stage == "doc_summary_generate":
            return PackageContextResult(True, "", retrieval_failed=True)
        return PackageContextResult(False, "")

    if not chunks:
        return PackageContextResult(True, "")

    block = _format_context_block(chunks, language)
    logger.info(
        "[FileCenterRAG] Injecting %d package chunk(s) stage=%s package=%s",
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
    top_k: int = DEFAULT_TOP_K,
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
