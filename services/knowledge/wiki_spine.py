"""Canonical wiki spine templates and TOC binding for curriculum documents.

Maps OCR/extracted section spans onto stable wiki slugs (e.g. ``san-kecheng-mubiao``)
so chapter queries, wiki pages, and section-scoped RAG share one key space.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from services.knowledge.section_query import parse_section_hint

MIN_SECTION_BODY = 120
MATCH_THRESHOLD = 0.72
QUERY_MATCH_THRESHOLD = 0.55

ZH_ENUM = re.compile(r"^([一二三四五六七八九十百]+)[、．.]([^\n]{2,50})$", re.MULTILINE)
QIANYAN = re.compile(r"^前\s*言\s*$", re.MULTILINE)
FULU = re.compile(r"^附\s*录\s*$", re.MULTILINE)
PAGE_NOISE = re.compile(r"(页面_|可搜索|Z\d|序\(|年版\）$)")


@dataclass(frozen=True)
class SpineEntry:
    """One canonical wiki page in a document template."""

    slug: str
    title: str
    keyword: str


SUBJECT_STANDARD_SPINE: Tuple[SpineEntry, ...] = (
    SpineEntry("qianyan", "前言", "前言"),
    SpineEntry("yi-kecheng-xingzhi", "一、课程性质", "课程性质"),
    SpineEntry("er-kecheng-linian", "二、课程理念", "课程理念"),
    SpineEntry("san-kecheng-mubiao", "三、课程目标", "课程目标"),
    SpineEntry("si-kecheng-neirong", "四、课程内容", "课程内容"),
    SpineEntry("wu-xueye-zhiliang", "五、学业质量", "学业质量"),
    SpineEntry("liu-kecheng-shishi", "六、课程实施", "课程实施"),
    SpineEntry("fulu", "附录", "附录"),
)

CURRICULUM_PLAN_SPINE: Tuple[SpineEntry, ...] = (
    SpineEntry("qianyan", "前言", "前言"),
    SpineEntry("yi-zhidaosixiang", "一、指导思想", "指导思想"),
    SpineEntry("er-xiuding-yuanze", "二、修订原则", "修订原则"),
    SpineEntry("san-peiyang-mubiao", "三、培养目标", "培养目标"),
    SpineEntry("kecheng-shezhi", "三、课程设置", "课程设置"),
    SpineEntry("si-kebiao-yanjiu", "四、课程标准研制与教材编写", "课程标准研制"),
    SpineEntry("wu-kecheng-shishi", "五、课程实施", "课程实施"),
)


@dataclass(frozen=True)
class RawSection:
    """A heading-bound text span extracted from document body."""

    title: str
    body: str
    position: int


@dataclass(frozen=True)
class BoundSection:
    """A spine-aligned section ready for wiki summarization."""

    slug: str
    title: str
    body: str
    section_key: str


def normalize_text(text: str) -> str:
    """Collapse whitespace and normalize Unicode for fuzzy compare."""
    collapsed = re.sub(r"\s+", "", (text or "").strip())
    return unicodedata.normalize("NFKC", collapsed)


def similarity(left: str, right: str) -> float:
    """Return a 0–1 similarity ratio between two labels."""
    return SequenceMatcher(None, normalize_text(left), normalize_text(right)).ratio()


def detect_spine_from_filename(file_name: str) -> Optional[Tuple[str, Tuple[SpineEntry, ...]]]:
    """Return ``(kind, spine)`` when the basename matches a known curriculum template."""
    name = Path(file_name or "").name
    if "课程方案" in name:
        return ("curriculum_plan", CURRICULUM_PLAN_SPINE)
    if "课程标准" in name:
        return ("subject_standard", SUBJECT_STANDARD_SPINE)
    return None


def extract_document_sections(text: str) -> List[RawSection]:
    """Split *text* on 前言 / 附录 / 一、 style headings."""
    markers: List[Tuple[int, int, str]] = []

    for match in QIANYAN.finditer(text):
        markers.append((match.start(), match.end(), "前言"))

    for match in FULU.finditer(text):
        markers.append((match.start(), match.end(), "附录"))

    for match in ZH_ENUM.finditer(text):
        numeral = match.group(1)
        title = match.group(2).strip()
        markers.append((match.start(), match.end(), f"{numeral}、{title}"))

    markers.sort(key=lambda item: item[0])

    sections: List[RawSection] = []
    for index, (start, line_end, title) in enumerate(markers):
        body_end = markers[index + 1][0] if index + 1 < len(markers) else len(text)
        body = text[line_end:body_end].strip()
        if PAGE_NOISE.search(title):
            continue
        if len(body) < MIN_SECTION_BODY and title not in {"前言", "附录"}:
            continue
        sections.append(RawSection(title=title, body=body, position=start))

    return sections


def _heading_core(title: str) -> str:
    """Strip leading Chinese enumeration from a section title."""
    norm = normalize_text(title)
    stripped = re.sub(r"^[一二三四五六七八九十百]+[、．.]", "", norm)
    return stripped or norm


def match_canonical_slug(section_title: str, spine: Sequence[SpineEntry]) -> Optional[str]:
    """Map an extracted section title onto a canonical slug from *spine*."""
    norm = normalize_text(section_title)
    core = _heading_core(section_title)
    if norm == "前言":
        return "qianyan"
    if "附录" in norm:
        return "fulu"

    best_slug: Optional[str] = None
    best_score = 0.0
    for entry in spine:
        if entry.slug in {"qianyan", "fulu"}:
            continue
        score = max(similarity(entry.keyword, norm), similarity(entry.keyword, core))
        if entry.keyword in norm or entry.keyword in core:
            score = max(score, 0.92)
        if score > best_score:
            best_score = score
            best_slug = entry.slug
    if best_score >= MATCH_THRESHOLD:
        return best_slug
    return None


def bind_sections_to_spine(
    raw_sections: Sequence[RawSection],
    spine: Sequence[SpineEntry],
) -> List[BoundSection]:
    """Align raw spans to canonical slugs; keep the longest body per slug."""
    title_by_slug = {entry.slug: entry.title for entry in spine}
    best: Dict[str, BoundSection] = {}

    for raw in raw_sections:
        slug = match_canonical_slug(raw.title, spine)
        if slug is None:
            continue
        bound = BoundSection(
            slug=slug,
            title=title_by_slug.get(slug, raw.title),
            body=raw.body,
            section_key=slug,
        )
        existing = best.get(slug)
        if existing is None or len(bound.body) > len(existing.body):
            best[slug] = bound

    ordered: List[BoundSection] = []
    for entry in spine:
        section = best.get(entry.slug)
        if section is not None:
            ordered.append(section)
    return ordered


def plan_spine_sections(file_name: str, text: str) -> Optional[List[BoundSection]]:
    """Return spine-bound sections when *file_name* matches a curriculum template."""
    detected = detect_spine_from_filename(file_name)
    if detected is None:
        return None
    _kind, spine = detected
    raw_sections = extract_document_sections(text)
    bound = bind_sections_to_spine(raw_sections, spine)
    if len(bound) < 3:
        return None
    return bound


def resolve_query_to_wiki_slug(query: str, pages: Sequence[dict]) -> Optional[str]:
    """Resolve a natural-language query to the best wiki slug."""
    hint = parse_section_hint(query)
    if hint is not None:
        for page in pages:
            slug = str(page.get("slug", ""))
            section_key = str(page.get("section_key") or slug)
            if hint.section_key in {section_key, slug}:
                return slug

    norm_query = normalize_text(query)
    if any(word in norm_query for word in ("概览", "概述", "overview")):
        return "overview"
    if "前言" in norm_query:
        return "qianyan"

    best_slug: Optional[str] = None
    best_score = 0.0
    for page in pages:
        slug = str(page.get("slug", ""))
        title = str(page.get("title", ""))
        section_key = str(page.get("section_key") or slug)
        haystack = normalize_text(f"{slug} {title} {section_key}")
        if norm_query and norm_query in haystack:
            return slug

        for spine in (SUBJECT_STANDARD_SPINE, CURRICULUM_PLAN_SPINE):
            for entry in spine:
                if entry.slug != slug:
                    continue
                score = 0.0
                if entry.keyword in norm_query or normalize_text(entry.title) in norm_query:
                    score = 1.0
                else:
                    score = similarity(entry.keyword, norm_query)
                if score > best_score:
                    best_score = score
                    best_slug = slug

        for term in _query_terms(query):
            if term in normalize_text(title) or term in normalize_text(section_key):
                term_score = 0.8
                if term_score > best_score:
                    best_score = term_score
                    best_slug = slug

    if best_score >= QUERY_MATCH_THRESHOLD:
        return best_slug
    return None


def rank_pages_for_query(query: str, pages: Sequence[dict]) -> List[dict]:
    """Score and sort wiki pages by relevance to *query*."""
    if not pages:
        return []

    primary_slug = resolve_query_to_wiki_slug(query, pages)
    scored: List[Tuple[int, dict]] = []
    for page in pages:
        slug = str(page.get("slug", ""))
        title = str(page.get("title", ""))
        section_key = str(page.get("section_key") or slug)
        score = 0
        if slug == primary_slug:
            score += 100
        if slug == "overview":
            score += 1
        norm_query = normalize_text(query)
        haystack = normalize_text(f"{slug} {title} {section_key}")
        for term in _query_terms(query):
            if term in haystack:
                score += 2
        if norm_query and norm_query in haystack:
            score += 5
        if score > 0 or slug == "overview":
            scored.append((score, page))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [page for _, page in scored]


def _query_terms(query: str) -> List[str]:
    """Extract meaningful CJK or Latin terms from a query string."""
    text = (query or "").strip().lower()
    if not text:
        return []
    latin = [term for term in re.split(r"\s+", text) if len(term) >= 2]
    cjk_chunks = re.findall(r"[\u4e00-\u9fff]{2,}", query or "")
    return latin + cjk_chunks
