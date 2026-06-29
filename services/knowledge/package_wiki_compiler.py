"""File Center package wiki compiler (v2b).

After a source is chunk-indexed, this service compiles or updates markdown wiki
pages for the package. Curriculum documents (课标 / 课程方案) use a TOC-driven
canonical spine; other sources fall back to a single LLM structure pass.

The wiki is an additive layer; chunk RAG remains the ground truth, so compile
failures are logged and swallowed rather than failing ingestion.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.domain.knowledge_space import DocumentBatch, DocumentChunk, KnowledgeDocument
from prompts.knowledge_wiki import (
    KNOWLEDGE_WIKI_COMPILE_SYSTEM_EN,
    KNOWLEDGE_WIKI_COMPILE_SYSTEM_ZH,
    WIKI_OVERVIEW_FROM_SECTIONS_SYSTEM_EN,
    WIKI_OVERVIEW_FROM_SECTIONS_SYSTEM_ZH,
    WIKI_SECTION_SUMMARY_SYSTEM_EN,
    WIKI_SECTION_SUMMARY_SYSTEM_ZH,
    build_overview_from_sections_prompt,
    build_section_summary_user_prompt,
    build_wiki_compile_user_prompt,
)
from services.knowledge import package_wiki_store as store
from services.knowledge.wiki_spine import BoundSection, plan_spine_sections
from services.llm import llm_service
from services.utils.error_types import JSON_PARSE_ERRORS

logger = logging.getLogger(__name__)

WIKI_REQUEST_TYPE = "knowledge_wiki"
MAX_SOURCE_CHARS = 8000
MAX_SECTION_INPUT_CHARS = 4000
MAX_WIKI_PAGES = 30
SECTION_SUMMARY_MAX_TOKENS = 900
OVERVIEW_MAX_TOKENS = 800


async def compile_package_wiki(
    db: AsyncSession,
    user_id: int,
    package_id: int,
    document_id: int,
) -> bool:
    """Compile/update the package wiki for a newly indexed source.

    Returns ``True`` when pages were written, ``False`` otherwise. Never raises
    on LLM or parse failures — the wiki is a best-effort secondary layer.
    """
    package = await _load_named_package(db, user_id, package_id)
    if package is None:
        return False

    document = await db.get(KnowledgeDocument, document_id)
    if document is None:
        return False

    source_text = await _load_source_text(db, document_id)
    if not source_text.strip():
        logger.info("[FileCenterWiki] No text for doc_id=%s; skipping wiki compile", document_id)
        return False

    existing_index = store.read_index(user_id, package_id)
    language = (document.language or "en").lower()
    source_title = _document_title(document)
    file_name = document.file_name or source_title

    spine_sections = plan_spine_sections(file_name, source_text)
    if spine_sections:
        pages = await _compile_spine_wiki_pages(
            spine_sections=spine_sections,
            doc_title=source_title,
            language=language,
            user_id=user_id,
        )
        if pages:
            written = _apply_page_actions(user_id, package_id, document_id, existing_index, pages)
            if written:
                logger.info(
                    "[FileCenterWiki] Spine compiled %s page(s) for package=%s from doc_id=%s",
                    written,
                    package_id,
                    document_id,
                )
            return written > 0

    return await _compile_legacy_wiki(
        db=db,
        user_id=user_id,
        package_id=package_id,
        document_id=document_id,
        package=package,
        document=document,
        existing_index=existing_index,
        language=language,
        source_title=source_title,
        source_text=source_text,
    )


async def _compile_legacy_wiki(
    db: AsyncSession,
    user_id: int,
    package_id: int,
    document_id: int,
    package: DocumentBatch,
    document: KnowledgeDocument,
    existing_index: List[Dict[str, Any]],
    language: str,
    source_title: str,
    source_text: str,
) -> bool:
    """Single-pass LLM wiki compile for non-curriculum sources."""
    del db, document
    system_message = KNOWLEDGE_WIKI_COMPILE_SYSTEM_ZH if language.startswith("zh") else KNOWLEDGE_WIKI_COMPILE_SYSTEM_EN
    user_prompt = build_wiki_compile_user_prompt(
        package_name=package.name or "Untitled package",
        existing_index=existing_index,
        new_source_title=source_title,
        new_source_text=source_text[:MAX_SOURCE_CHARS],
        language=language,
    )

    try:
        response = await llm_service.chat(
            prompt=user_prompt,
            system_message=system_message,
            temperature=0.3,
            max_tokens=2000,
            use_knowledge_base=False,
            user_id=user_id,
            request_type=WIKI_REQUEST_TYPE,
        )
    except JSON_PARSE_ERRORS as exc:
        logger.warning("[FileCenterWiki] LLM compile failed for package=%s: %s", package_id, exc)
        return False

    pages = _parse_pages(response)
    if not pages:
        logger.info("[FileCenterWiki] No page actions returned for package=%s", package_id)
        return False

    written = _apply_page_actions(user_id, package_id, document_id, existing_index, pages)
    if written:
        logger.info(
            "[FileCenterWiki] Compiled %s page(s) for package=%s from doc_id=%s",
            written,
            package_id,
            document_id,
        )
    return written > 0


async def _compile_spine_wiki_pages(
    spine_sections: List[BoundSection],
    doc_title: str,
    language: str,
    user_id: int,
) -> List[Dict[str, Any]]:
    """Summarize spine-bound sections and build wiki page payloads."""
    section_notes: List[Dict[str, str]] = []
    pages: List[Dict[str, Any]] = []

    summary_system = WIKI_SECTION_SUMMARY_SYSTEM_ZH if language.startswith("zh") else WIKI_SECTION_SUMMARY_SYSTEM_EN
    for section in spine_sections:
        try:
            summary = await llm_service.chat(
                prompt=build_section_summary_user_prompt(
                    section.title,
                    section.body[:MAX_SECTION_INPUT_CHARS],
                    language,
                ),
                system_message=summary_system,
                temperature=0.2,
                max_tokens=SECTION_SUMMARY_MAX_TOKENS,
                use_knowledge_base=False,
                user_id=user_id,
                request_type=WIKI_REQUEST_TYPE,
            )
        except JSON_PARSE_ERRORS as exc:
            logger.warning("[FileCenterWiki] Section summary failed slug=%s: %s", section.slug, exc)
            summary = _fallback_section_summary(section.body)
        body = (summary or "").strip() or _fallback_section_summary(section.body)
        section_notes.append({"title": section.title, "summary": body[:400]})
        pages.append(
            {
                "slug": section.slug,
                "title": section.title,
                "body_md": body,
                "links": [],
                "section_key": section.section_key,
            }
        )

    overview_system = (
        WIKI_OVERVIEW_FROM_SECTIONS_SYSTEM_ZH if language.startswith("zh") else WIKI_OVERVIEW_FROM_SECTIONS_SYSTEM_EN
    )
    overview_title = f"{doc_title}概览" if language.startswith("zh") else f"{doc_title} Overview"
    try:
        overview_body = await llm_service.chat(
            prompt=build_overview_from_sections_prompt(doc_title, section_notes, language),
            system_message=overview_system,
            temperature=0.2,
            max_tokens=OVERVIEW_MAX_TOKENS,
            use_knowledge_base=False,
            user_id=user_id,
            request_type=WIKI_REQUEST_TYPE,
        )
    except JSON_PARSE_ERRORS as exc:
        logger.warning("[FileCenterWiki] Overview compile failed: %s", exc)
        overview_body = _fallback_overview(doc_title, section_notes, language)

    overview_links = [{"slug": section.slug, "label": section.title} for section in spine_sections]
    return [
        {
            "slug": "overview",
            "title": overview_title,
            "body_md": (overview_body or "").strip() or _fallback_overview(doc_title, section_notes, language),
            "links": overview_links,
            "section_key": "overview",
        },
        *pages,
    ]


def _fallback_section_summary(body: str) -> str:
    """Extractive fallback when the LLM section summary fails."""
    collapsed = " ".join((body or "").split())
    if not collapsed:
        return ""
    return collapsed[:600] + ("…" if len(collapsed) > 600 else "")


def _fallback_overview(doc_title: str, section_notes: List[Dict[str, str]], language: str) -> str:
    """Build a minimal overview when the LLM overview pass fails."""
    if language.startswith("zh"):
        lines = [f"# {doc_title}概览", ""]
        for note in section_notes:
            lines.append(f"- **{note['title']}**：{note['summary'][:120]}")
        return "\n".join(lines)
    lines = [f"# {doc_title} Overview", ""]
    for note in section_notes:
        lines.append(f"- **{note['title']}**: {note['summary'][:120]}")
    return "\n".join(lines)


async def _load_named_package(db: AsyncSession, user_id: int, package_id: int) -> Optional[DocumentBatch]:
    result = await db.execute(
        select(DocumentBatch).where(
            DocumentBatch.id == package_id,
            DocumentBatch.user_id == user_id,
        )
    )
    package = result.scalars().first()
    if package is None or not package.name:
        return None
    return package


async def _load_source_text(db: AsyncSession, document_id: int) -> str:
    """Concatenate all indexed chunks for structure extraction and summarization."""
    result = await db.execute(
        select(DocumentChunk.text)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    parts: List[str] = []
    for (text,) in result.all():
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _document_title(document: KnowledgeDocument) -> str:
    metadata = document.doc_metadata or {}
    return metadata.get("page_title") or document.file_name or "Untitled source"


def _parse_pages(response: str) -> List[Dict[str, Any]]:
    """Extract the ``pages`` array from an LLM JSON response (brace-sliced)."""
    start = response.find("{")
    end = response.rfind("}") + 1
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(response[start:end])
    except json.JSONDecodeError:
        return []
    pages = data.get("pages") if isinstance(data, dict) else None
    if not isinstance(pages, list):
        return []
    return [page for page in pages if isinstance(page, dict) and page.get("slug")]


def _apply_page_actions(
    user_id: int,
    package_id: int,
    document_id: int,
    existing_index: List[Dict[str, Any]],
    pages: List[Dict[str, Any]],
) -> int:
    """Write page markdown files and refresh the manifest. Returns pages written."""
    directory = store.wiki_dir(user_id, package_id)
    directory.mkdir(parents=True, exist_ok=True)

    index_by_slug: Dict[str, Dict[str, Any]] = {}
    for page in existing_index:
        existing_slug = page.get("slug")
        if existing_slug:
            index_by_slug[str(existing_slug)] = dict(page)

    written = 0
    now = datetime.now(UTC).isoformat()
    for page in pages:
        slug = store.safe_slug(page.get("slug", ""))
        body = page.get("body_md")
        if not slug or not isinstance(body, str) or not body.strip():
            continue

        title = str(page.get("title") or slug)
        links = page.get("links") if isinstance(page.get("links"), list) else []
        source_ids = sorted(set(index_by_slug.get(slug, {}).get("source_document_ids", []) + [document_id]))
        section_key = str(page.get("section_key") or slug)
        entry = {
            "slug": slug,
            "title": title,
            "links": links,
            "source_document_ids": source_ids,
            "section_key": section_key,
            "updated_at": now,
        }

        _write_page_file(directory / f"{slug}.md", entry, body)
        index_by_slug[slug] = entry
        written += 1

    if written:
        manifest_pages = list(index_by_slug.values())[:MAX_WIKI_PAGES]
        manifest_json = json.dumps({"pages": manifest_pages}, ensure_ascii=False, indent=2)
        _atomic_write(store.index_path(user_id, package_id), manifest_json)

    return written


def _write_page_file(path: Path, entry: Dict[str, Any], body: str) -> None:
    dumped = yaml.safe_dump(entry, allow_unicode=True, sort_keys=False)
    frontmatter = (dumped or "").strip()
    content = f"---\n{frontmatter}\n---\n\n{body.strip()}\n"
    _atomic_write(path, content)


def _atomic_write(path: Path, content: str) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(content, encoding="utf-8")
    os.replace(tmp_path, path)
