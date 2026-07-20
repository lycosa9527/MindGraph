"""Tests for document vs web content mind-map prompt selection."""

from __future__ import annotations

from prompts import get_prompt
from utils.prompt_locale import build_extracted_content_user_block


def test_document_and_web_prompts_are_registered() -> None:
    """Both source-kind prompts resolve for en/zh."""
    assert "Ignore site chrome" in get_prompt("mind_map", "en", "web_content_generation")
    assert "Cover the **whole** document" in get_prompt("mind_map", "en", "document_content_generation")
    assert "忽略网站导航" in get_prompt("mind_map", "zh", "web_content_generation")
    assert "覆盖**全文**" in get_prompt("mind_map", "zh", "document_content_generation")


def test_document_user_block_omits_url() -> None:
    """Document wrapper uses document title, not page URL."""
    block = build_extracted_content_user_block(
        page_content="Chapter 1\nHello",
        language="en",
        content_format="text/markdown",
        page_title="My Book",
        page_url="https://example.com",
        source_kind="document",
    )
    assert "Document title: My Book" in block
    assert "Page URL" not in block
    assert "Chapter 1" in block


def test_web_user_block_keeps_url() -> None:
    """Web wrapper still includes page URL."""
    block = build_extracted_content_user_block(
        page_content="Article body",
        language="en",
        content_format="text/plain",
        page_title="News",
        page_url="https://example.com/a",
        source_kind="web",
    )
    assert "Page URL: https://example.com/a" in block
    assert "Page title: News" in block
