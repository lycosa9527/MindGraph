"""Read-only filesystem store for File Center package wikis (v2a).

Wiki pages are markdown files on disk under ``KNOWLEDGE_STORAGE_DIR``; a small
``_index.json`` manifest lists slugs, titles, links and the source document IDs
each page draws from. No wiki content lives in PostgreSQL.

Layout::

    {KNOWLEDGE_STORAGE_DIR}/user_{user_id}/packages/{package_id}/wiki/
        _index.json
        overview.md
        chapter-5.md

This module owns the path helpers and read/delete operations. Writes are done
by :mod:`services.knowledge.package_wiki_compiler`.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

INDEX_FILE_NAME = "_index.json"


def _storage_root() -> Path:
    return Path(os.getenv("KNOWLEDGE_STORAGE_DIR", "./storage/knowledge_documents"))


def wiki_dir(user_id: int, package_id: int) -> Path:
    """Return the wiki directory for a package (not created)."""
    return _storage_root() / f"user_{user_id}" / "packages" / str(package_id) / "wiki"


def index_path(user_id: int, package_id: int) -> Path:
    """Return the path to the package wiki manifest."""
    return wiki_dir(user_id, package_id) / INDEX_FILE_NAME


def read_index(user_id: int, package_id: int) -> List[Dict[str, Any]]:
    """Read the wiki manifest (list of page entries). Empty when no wiki exists."""
    path = index_path(user_id, package_id)
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("[FileCenterWiki] Failed to read index %s: %s", path, exc)
        return []
    pages = data.get("pages", []) if isinstance(data, dict) else []
    return pages if isinstance(pages, list) else []


def list_pages(user_id: int, package_id: int) -> List[Dict[str, Any]]:
    """List wiki page metadata for a package."""
    return read_index(user_id, package_id)


def read_page(user_id: int, package_id: int, slug: str) -> Optional[str]:
    """Read the markdown body of a single wiki page, or ``None`` if missing."""
    cleaned_slug = safe_slug(slug)
    if not cleaned_slug:
        return None
    path = wiki_dir(user_id, package_id) / f"{cleaned_slug}.md"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("[FileCenterWiki] Failed to read page %s: %s", path, exc)
        return None


def find_relevant_pages(user_id: int, package_id: int, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Find wiki pages whose title or slug best matches a query (substring score).

    A lightweight match by title/slug keywords — no embeddings. The overview
    page is always considered a candidate so global context is available.
    """
    pages = read_index(user_id, package_id)
    if not pages:
        return []

    terms = [term for term in query.lower().split() if term]
    scored: List[tuple[int, Dict[str, Any]]] = []
    for page in pages:
        haystack = f"{page.get('slug', '')} {page.get('title', '')}".lower()
        score = sum(1 for term in terms if term in haystack)
        if page.get("slug") == "overview":
            score += 1  # always keep big-picture context available
        if score > 0:
            scored.append((score, page))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [page for _, page in scored[:top_k]]


def delete_wiki(user_id: int, package_id: int) -> None:
    """Remove the entire wiki folder for a package (best-effort)."""
    path = wiki_dir(user_id, package_id)
    if path.exists():
        try:
            shutil.rmtree(path)
            logger.info("[FileCenterWiki] Removed wiki folder %s", path)
        except OSError as exc:
            logger.warning("[FileCenterWiki] Failed to remove wiki folder %s: %s", path, exc)


def safe_slug(slug: str) -> str:
    """Return a filesystem-safe slug (defends against path traversal)."""
    cleaned = "".join(ch for ch in (slug or "").lower() if ch.isalnum() or ch in "-_")
    return cleaned[:80]
