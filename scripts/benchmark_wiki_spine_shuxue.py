"""Benchmark spine binding + retrieval on 数学课程标准 OCR PDF."""

from __future__ import annotations

from pathlib import Path

import fitz

from services.knowledge.wiki_spine import plan_spine_sections, resolve_query_to_wiki_slug

OCR_DIR = Path("/mnt/c/Users/roywa/Downloads/义务教育课程方案和课程标准/OCR")
SUBJECT = "数学"


def main() -> None:
    """Run spine binding and query-resolution benchmark on the math OCR PDF."""
    pdf_path = next(p for p in OCR_DIR.glob("*.pdf") if SUBJECT in p.name and "课程方案" not in p.name)
    doc = fitz.open(str(pdf_path))
    text = "\n\n".join(str(doc.load_page(i).get_text() or "") for i in range(len(doc)))
    doc_title = pdf_path.stem.replace("_可搜索", "")

    bound = plan_spine_sections(pdf_path.name, text)
    if bound is None:
        print("FAIL: spine binding returned None")
        return

    pages = [{"slug": "overview", "title": f"{doc_title}概览", "section_key": "overview"}]
    pages.extend(
        {"slug": section.slug, "title": section.title, "section_key": section.section_key} for section in bound
    )

    print("BENCHMARK:", pdf_path.name)
    print("PAGES:", len(doc), "| CHARS:", len(text), "| WIKI SECTIONS:", len(bound))
    print()
    print("| slug | title |")
    print("|------|-------|")
    for page in pages:
        print(f"| {page['slug']} | {page['title']} |")

    tests = [
        ("overview", "数学课程标准概览"),
        ("qianyan", "前言"),
        ("yi-kecheng-xingzhi", "课程性质"),
        ("san-kecheng-mubiao", "课程目标"),
        ("si-kecheng-neirong", "课程内容"),
        ("wu-xueye-zhiliang", "学业质量"),
        ("liu-kecheng-shishi", "课程实施"),
        ("fulu", "附录"),
    ]

    print()
    ok = 0
    for expected, query in tests:
        got = resolve_query_to_wiki_slug(query, pages)
        hit = got == expected
        ok += int(hit)
        print(f"  {'OK' if hit else 'MISS':4}  {query!r:28} → {got} (expected {expected})")
    print(f"\nScore: {ok}/{len(tests)}")


if __name__ == "__main__":
    main()
