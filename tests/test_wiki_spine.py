"""Tests for curriculum wiki spine binding and query routing."""

from __future__ import annotations

from services.knowledge import package_wiki_store as store
from services.knowledge.package_wiki_compiler import _apply_page_actions
from services.knowledge.wiki_spine import (
    bind_sections_to_spine,
    extract_document_sections,
    plan_spine_sections,
    resolve_query_to_wiki_slug,
    SUBJECT_STANDARD_SPINE,
)


def _sample_subject_text() -> str:
    block = "为落实立德树人根本任务，制定本课程标准。" * 8
    return (
        "前言\n"
        f"{block}\n"
        "一、课程性质\n"
        f"{block}\n"
        "二、课程理念\n"
        f"{block}\n"
        "三、课程目标\n"
        f"{block}\n"
        "四、课程内容\n"
        f"{block}\n"
        "五、学业质量\n"
        f"{block}\n"
        "六、课程实施\n"
        f"{block}\n"
        "附录\n"
        f"{block}\n"
    )


def test_detect_spine_uses_basename_only():
    """Folder paths containing 课程方案 must not override a 课程标准 filename."""
    path = "/data/义务教育课程方案和课程标准/OCR/义务教育数学课程标准（2022年版）.pdf"
    detected = plan_spine_sections(path, _sample_subject_text())
    assert detected is not None
    assert detected[0].slug == "qianyan"


def test_plan_spine_sections_subject_standard():
    """Subject 课标 filenames bind to the canonical spine."""
    bound = plan_spine_sections("义务教育语文课程标准（2022年版）.pdf", _sample_subject_text())
    assert bound is not None
    slugs = [section.slug for section in bound]
    assert slugs == [
        "qianyan",
        "yi-kecheng-xingzhi",
        "er-kecheng-linian",
        "san-kecheng-mubiao",
        "si-kecheng-neirong",
        "wu-xueye-zhiliang",
        "liu-kecheng-shishi",
        "fulu",
    ]


def test_bind_sections_tolerates_ocr_heading_variants():
    """OCR-corrupted headings still map to canonical slugs."""
    raw = extract_document_sections(
        "六、课程实陆\n"
        + ("实施建议正文，包含教学与评价要求。" * 12)
        + "六、课程实陷\n"
        + ("更多实施建议，包含教学与评价要求。" * 16)
    )
    bound = bind_sections_to_spine(raw, SUBJECT_STANDARD_SPINE)
    assert len(bound) == 1
    assert bound[0].slug == "liu-kecheng-shishi"


def test_resolve_query_to_wiki_slug_subject_keywords():
    """Chinese chapter keywords resolve to canonical slugs."""
    pages = [
        {"slug": "overview", "title": "概览", "section_key": "overview"},
        {"slug": "san-kecheng-mubiao", "title": "三、课程目标", "section_key": "san-kecheng-mubiao"},
        {"slug": "si-kecheng-neirong", "title": "四、课程内容", "section_key": "si-kecheng-neirong"},
    ]
    assert resolve_query_to_wiki_slug("课程目标", pages) == "san-kecheng-mubiao"
    assert resolve_query_to_wiki_slug("第四部分 课程内容", pages) == "si-kecheng-neirong"
    assert resolve_query_to_wiki_slug("概述", pages) == "overview"


def test_find_relevant_pages_uses_section_key(tmp_path, monkeypatch):
    """Store lookup prefers canonical section slugs for Chinese queries."""
    monkeypatch.setenv("KNOWLEDGE_STORAGE_DIR", str(tmp_path))
    _apply_page_actions(
        user_id=1,
        package_id=9,
        document_id=42,
        existing_index=[],
        pages=[
            {
                "slug": "overview",
                "title": "概览",
                "body_md": "x",
                "links": [],
                "section_key": "overview",
            },
            {
                "slug": "wu-xueye-zhiliang",
                "title": "五、学业质量",
                "body_md": "x",
                "links": [],
                "section_key": "wu-xueye-zhiliang",
            },
        ],
    )
    relevant = store.find_relevant_pages(1, 9, "学业质量")
    assert relevant[0]["slug"] == "wu-xueye-zhiliang"
