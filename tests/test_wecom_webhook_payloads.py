"""Unit tests for WeCom webhook payload builders (doc 99110)."""

from __future__ import annotations

import pytest

from services.integrations.wecom.webhook_payloads import (
    WeComWebhookMarkdownMessage,
    WeComWebhookNewsArticle,
    WeComWebhookTextMessage,
    WeComWebhookTextNoticeCard,
    append_markdown_mentions,
    build_markdown_payload,
    build_news_payload,
    build_text_notice_card_payload,
    build_text_payload,
)


def test_build_text_payload_with_mentions() -> None:
    """text msgtype uses mentioned_list fields per 99110."""
    payload = build_text_payload(
        WeComWebhookTextMessage(
            content="hello",
            mentioned_list=("alice",),
            mentioned_mobile_list=("13800000000",),
        )
    )
    assert payload["msgtype"] == "text"
    assert payload["text"]["content"] == "hello"
    assert payload["text"]["mentioned_list"] == ["alice"]
    assert payload["text"]["mentioned_mobile_list"] == ["13800000000"]


def test_build_markdown_payload_content_only() -> None:
    """markdown uses content key only — not DingTalk title/text."""
    payload = build_markdown_payload(WeComWebhookMarkdownMessage(content="# Title\n> line"))
    assert payload == {
        "msgtype": "markdown",
        "markdown": {"content": "# Title\n> line"},
    }


def test_append_markdown_mentions() -> None:
    """@ in markdown uses <@userid> syntax."""
    content = append_markdown_mentions("body", ("michelleq",))
    assert content == "body\n\n<@michelleq>"


def test_build_news_payload_article_count() -> None:
    """news supports 1-8 articles."""
    with pytest.raises(ValueError):
        build_news_payload(())

    payload = build_news_payload(
        (
            WeComWebhookNewsArticle(
                title="Title",
                url="https://example.com",
                description="desc",
            ),
        )
    )
    assert payload["msgtype"] == "news"
    assert len(payload["news"]["articles"]) == 1


def test_build_text_notice_card_payload() -> None:
    """text_notice template_card includes card_action url."""
    payload = build_text_notice_card_payload(
        WeComWebhookTextNoticeCard(
            main_title="Lead",
            main_desc="New inquiry",
            card_action_url="https://mindgraph.example/leads",
        )
    )
    assert payload["msgtype"] == "template_card"
    card = payload["template_card"]
    assert card["card_type"] == "text_notice"
    assert card["card_action"]["url"] == "https://mindgraph.example/leads"
