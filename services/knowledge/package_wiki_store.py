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
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from services.knowledge.section_query import parse_section_hint
from services.knowledge.wiki_spine import rank_pages_for_query, resolve_query_to_wiki_slug

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


def read_page_body(user_id: int, package_id: int, slug: str) -> Optional[str]:
    """Return wiki page markdown without YAML frontmatter."""
    raw = read_page(user_id, package_id, slug)
    if raw is None:
        return None
    body = strip_frontmatter(raw).strip()
    return body or None


def strip_frontmatter(text: str) -> str:
    """Remove optional YAML frontmatter from a markdown page file."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end < 0:
        return text
    return text[end + 4 :].lstrip("\n")


def find_relevant_pages(user_id: int, package_id: int, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """Find wiki pages whose slug/title/section_key best match a query.

    Uses canonical curriculum spine keyword routing when available, then falls
    back to substring scoring. The overview page stays a low-priority candidate.
    """
    pages = read_index(user_id, package_id)
    if not pages:
        return []

    ranked = rank_pages_for_query(query, pages)
    if ranked:
        return ranked[:top_k]

    section_hint = parse_section_hint(query)
    primary_slug = resolve_query_to_wiki_slug(query, pages)
    terms = _query_terms(query)
    scored: List[tuple[int, Dict[str, Any]]] = []
    for page in pages:
        slug = str(page.get("slug", ""))
        section_key = str(page.get("section_key") or slug)
        haystack = f"{slug} {page.get('title', '')} {section_key}".lower()
        score = sum(1 for term in terms if term in haystack)
        if primary_slug and slug == primary_slug:
            score += 100
        if section_hint is not None and section_key == section_hint.section_key:
            score += 10
        if page.get("slug") == "overview":
            score += 1
        if score > 0:
            scored.append((score, page))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [page for _, page in scored[:top_k]]


def _query_terms(query: str) -> List[str]:
    """Return lowercase Latin and CJK terms for lightweight wiki matching."""
    text = (query or "").strip().lower()
    latin = [term for term in text.split() if len(term) >= 2]
    cjk = re.findall(r"[\u4e00-\u9fff]{2,}", query or "")
    return latin + cjk


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
