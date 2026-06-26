"""Tests for DingTalk diagram preview image outbound helpers."""

from __future__ import annotations

from services.mindbot.diagram.preview_image_outbound import (
    dingtalk_reply_text_without_inline_preview,
    extract_dingtalk_diagram_preview_url,
    prepare_dingtalk_diagram_card_markdown,
    rewrite_dingtalk_diagram_markdown_alt,
    strip_dingtalk_diagram_preview_markdown,
)

_URL = "https://mg.mindspringedu.com/api/temp_images/dingtalk_deadbeef_1710000000.png?sig=abc&exp=999"


def test_extract_dingtalk_diagram_preview_url_from_mg_alt() -> None:
    """Parse preview URL from mg alt markdown."""
    text = f"![mg:550e8400-e29b-41d4-a716-446655440000]({_URL})"
    assert extract_dingtalk_diagram_preview_url(text) == _URL


def test_prepare_dingtalk_diagram_card_markdown_strips_image() -> None:
    """Card body drops inline image; URL returned separately."""
    text = f"说明文字\n\n![mg:uuid]({_URL})\n<!-- mg-diagram-id:uuid -->"
    card_md, url = prepare_dingtalk_diagram_card_markdown(text)
    assert url == _URL
    assert "temp_images" not in card_md
    assert "说明文字" in card_md


def test_rewrite_dingtalk_diagram_markdown_alt() -> None:
    """Empty alt avoids DingTalk markdown colon issues."""
    text = f"![mg:uuid]({_URL})"
    assert rewrite_dingtalk_diagram_markdown_alt(text) == f"![]({_URL})"


def test_dingtalk_reply_text_without_inline_preview_strips_image() -> None:
    """Text delivery omits inline preview; URL stays available for sampleImageMsg."""
    text = f"说明文字\n\n![mg:uuid]({_URL})\n<!-- mg-diagram-id:uuid -->"
    assert dingtalk_reply_text_without_inline_preview(text) == "说明文字"
    assert "temp_images" not in dingtalk_reply_text_without_inline_preview(text)


def test_strip_dingtalk_diagram_preview_markdown() -> None:
    """Strip removes image line and HTML comment."""
    text = f"notice\n\n![x]({_URL})\n<!-- mg-diagram-id:abc -->"
    assert strip_dingtalk_diagram_preview_markdown(text) == "notice"
