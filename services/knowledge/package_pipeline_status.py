"""Derive RAG and wiki pipeline status for File Center packages."""

from typing import Dict, Iterable, Set

from config.settings import config
from models.domain.knowledge_space import KnowledgeDocument
from services.knowledge import package_wiki_store

WIKI_STATUS_DISABLED = "disabled"
WIKI_STATUS_NONE = "none"
WIKI_STATUS_NOT_YET = "not_yet"
WIKI_STATUS_PENDING = "pending"
WIKI_STATUS_READY = "ready"
WIKI_STATUS_COMPLETE = "complete"

RAG_STATUS_NOT_YET = "not_yet"
RAG_STATUS_PROCESSING = "processing"
RAG_STATUS_COMPLETE = "complete"
RAG_STATUS_FAILED = "failed"


def derive_wiki_status(completed_count: int, wiki_page_count: int) -> str:
    """Return wiki pipeline status for a package."""
    if not config.FILE_CENTER_WIKI_COMPILE:
        return WIKI_STATUS_DISABLED
    if wiki_page_count > 0:
        return WIKI_STATUS_READY
    if completed_count > 0:
        return WIKI_STATUS_PENDING
    return WIKI_STATUS_NONE


def derive_document_rag_status(document_status: str) -> str:
    """Map a source document status to a RAG pipeline badge state."""
    if document_status == "processing":
        return RAG_STATUS_PROCESSING
    if document_status == "completed":
        return RAG_STATUS_COMPLETE
    if document_status == "failed":
        return RAG_STATUS_FAILED
    return RAG_STATUS_NOT_YET


def _wiki_indexed_document_ids(user_id: int, package_id: int) -> Set[int]:
    indexed: Set[int] = set()
    for page in package_wiki_store.read_index(user_id, package_id):
        source_ids = page.get("source_document_ids")
        if not isinstance(source_ids, list):
            continue
        for raw_id in source_ids:
            try:
                indexed.add(int(raw_id))
            except (TypeError, ValueError):
                continue
    return indexed


def derive_document_wiki_status(
    document: KnowledgeDocument,
    indexed_document_ids: Set[int],
) -> str:
    """Return wiki compile badge state for one indexed source."""
    if not config.FILE_CENTER_WIKI_COMPILE:
        return WIKI_STATUS_DISABLED
    if document.status in ("pending", "processing", "failed"):
        return WIKI_STATUS_NOT_YET
    if document.id in indexed_document_ids:
        return WIKI_STATUS_COMPLETE
    return WIKI_STATUS_PENDING


def derive_document_wiki_statuses(
    user_id: int,
    package_id: int,
    documents: Iterable[KnowledgeDocument],
) -> Dict[int, str]:
    """Batch wiki badge states for all sources in a package."""
    docs = list(documents)
    if not docs:
        return {}
    indexed_ids = _wiki_indexed_document_ids(user_id, package_id)
    return {doc.id: derive_document_wiki_status(doc, indexed_ids) for doc in docs}


def count_wiki_pages(user_id: int, package_id: int) -> int:
    """Return the number of compiled wiki pages on disk for a package."""
    return len(package_wiki_store.list_pages(user_id, package_id))
