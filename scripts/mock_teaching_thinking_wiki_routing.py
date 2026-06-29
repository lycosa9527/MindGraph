"""Simulate wiki routing for 3 OCR 课标 docs + teaching/thinking questions."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

import fitz

from services.knowledge.wiki_spine import (
    BoundSection,
    plan_spine_sections,
    rank_pages_for_query,
    resolve_query_to_wiki_slug,
)

OCR_DIR = Path("/mnt/c/Users/roywa/Downloads/义务教育课程方案和课程标准/OCR")

# Three different subjects (not 课程方案).
SUBJECTS = ("语文", "数学", "英语")

MOCK_QUESTIONS = [
    "如何在教学中发展学生的思维能力？",
    "课程标准对思维发展有什么要求？",
    "核心素养里的思维品质怎么教？",
    "课程理念部分讲了什么？",
    "学业质量标准是什么？",
    "课程实施里的教学建议",
    "前言里为什么要修订课标？",
    "overview 概览",
]


def _load_pdf(name_part: str) -> Tuple[Path, str]:
    """Load OCR PDF text for a subject name fragment."""
    path = next(p for p in OCR_DIR.glob("*.pdf") if name_part in p.name and "课程方案" not in p.name)
    doc = fitz.open(str(path))
    text = "\n\n".join(str(doc[i].get_text() or "") for i in range(len(doc)))
    return path, text


def _section_snippet(body: str, query: str, width: int = 120) -> str:
    terms = re.findall(r"[\u4e00-\u9fff]{2,}", query)
    for term in terms:
        idx = body.find(term)
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(body), idx + width)
            snippet = body[start:end].replace("\n", " ")
            return snippet.strip()
    collapsed = " ".join(body.split())
    return collapsed[:width] + ("…" if len(collapsed) > width else "")


def _pages_from_bound(doc_title: str, bound: List[BoundSection]) -> List[dict]:
    pages = [{"slug": "overview", "title": f"{doc_title}概览", "section_key": "overview"}]
    for section in bound:
        pages.append(
            {
                "slug": section.slug,
                "title": section.title,
                "section_key": section.section_key,
            }
        )
    return pages


def _body_by_slug(bound: List[BoundSection]) -> dict[str, str]:
    return {section.slug: section.body for section in bound}


def main() -> None:
    """Print wiki spine routing results for mock teaching/thinking questions."""
    print("=" * 72)
    print("CURRENT HANDLING: wiki spine bind + query routing (no LLM summaries)")
    print("=" * 72)

    for subject in SUBJECTS:
        path, text = _load_pdf(subject)
        doc_title = path.stem.replace("_可搜索", "")
        bound = plan_spine_sections(path.name, text)
        print()
        print("#" * 72)
        print(f"DOCUMENT: {path.name}")
        print(f"  pages={fitz.open(str(path)).page_count}  chars={len(text)}")
        if bound is None:
            print("  SPINE: FAILED (would fall back to old LLM wiki guess)")
            continue

        print(f"  SPINE: OK — {len(bound)} sections →", ", ".join(s.slug for s in bound))
        pages = _pages_from_bound(doc_title, bound)
        bodies = _body_by_slug(bound)

        print()
        print("  Mock questions → wiki page → excerpt from that section")
        print("  " + "-" * 68)
        for question in MOCK_QUESTIONS:
            slug = resolve_query_to_wiki_slug(question, pages)
            ranked = rank_pages_for_query(question, pages)
            top3 = [p["slug"] for p in ranked[:3]]
            if slug is None:
                print(f"  Q: {question}")
                print(f"     → NO MATCH  (top candidates: {top3 or 'none'})")
                print()
                continue
            title = next(p["title"] for p in pages if p["slug"] == slug)
            body = bodies.get(slug, "")
            snippet = _section_snippet(body, question) if body else "(overview — no bound body yet)"
            thinking_hits = []
            for kw in ("思维", "思考", "核心素养", "教学", "理念", "质量", "实施"):
                if kw in body:
                    thinking_hits.append(kw)
            print(f"  Q: {question}")
            print(f"     → slug={slug}  ({title})")
            print(f"     top-3: {top3}")
            if thinking_hits:
                print(f"     keywords in section: {', '.join(thinking_hits)}")
            print(f"     excerpt: {snippet}")
            print()


if __name__ == "__main__":
    main()
