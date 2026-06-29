"""Tests for document section parsing."""

from services.knowledge.section_parser import detect_section_headings, split_into_sections


def test_split_english_chapters() -> None:
    """English Chapter headings split the document into sections."""
    text = "Preface intro.\n\nChapter 1: Introduction\nIntro body line one.\n\nChapter 2: Methods\nMethods body here."
    sections = split_into_sections(text)
    assert len(sections) == 2
    assert sections[0].section_key == "chapter-1"
    assert "Intro body" in sections[0].body
    assert sections[1].section_key == "chapter-2"
    assert "Methods body" in sections[1].body


def test_split_chinese_chapter() -> None:
    """Chinese 第N章 headings produce chapter keys."""
    text = "第1章 概述\n内容一。\n\n第5章 神经网络\n内容五。"
    sections = split_into_sections(text)
    assert len(sections) == 2
    assert sections[1].section_key == "chapter-5"
    assert "内容五" in sections[1].body


def test_single_heading_creates_one_section() -> None:
    """A lone heading still yields one section for scoped retrieval."""
    text = "Chapter 1 only\nSome text without another heading."
    sections = split_into_sections(text)
    assert len(sections) == 1
    assert sections[0].section_key == "chapter-1"
    assert "Some text" in sections[0].body


def test_detect_markdown_heading() -> None:
    """Markdown headings are detected."""
    text = "# Overview\n\n## Details\n\nBody"
    headings = detect_section_headings(text)
    assert len(headings) >= 2
