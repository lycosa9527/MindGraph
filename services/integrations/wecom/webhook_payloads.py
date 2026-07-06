"""WeCom webhook/send payload builders — doc 99110 message types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.integrations.wecom.text_limits import truncate_utf8
from services.integrations.wecom.webhook_constants import (
    WEBHOOK_MARKDOWN_MAX_BYTES,
    WEBHOOK_MARKDOWN_V2_MAX_BYTES,
    WEBHOOK_NEWS_ARTICLES_MAX,
    WEBHOOK_NEWS_ARTICLES_MIN,
    WEBHOOK_NEWS_DESCRIPTION_MAX_BYTES,
    WEBHOOK_NEWS_TITLE_MAX_BYTES,
    WEBHOOK_TEXT_MAX_BYTES,
)


@dataclass(frozen=True)
class WeComWebhookTextMessage:
    """text msgtype — supports mentioned_list / mentioned_mobile_list (99110)."""

    content: str
    mentioned_list: tuple[str, ...] = ()
    mentioned_mobile_list: tuple[str, ...] = ()


@dataclass(frozen=True)
class WeComWebhookMarkdownMessage:
    """markdown msgtype — use <@userid> in content for @ mentions (99110)."""

    content: str


@dataclass(frozen=True)
class WeComWebhookMarkdownV2Message:
    """markdown_v2 msgtype — no @ syntax or font colors (99110)."""

    content: str


@dataclass(frozen=True)
class WeComWebhookNewsArticle:
    """One news article entry (99110)."""

    title: str
    url: str
    description: str = ""
    picurl: str = ""


@dataclass(frozen=True)
class WeComWebhookImageMessage:
    """image msgtype — base64 + md5 of raw image bytes (99110)."""

    base64_data: str
    md5_hex: str


@dataclass(frozen=True)
class WeComWebhookMediaMessage:
    """file or voice msgtype — media_id from upload_media (99110)."""

    media_id: str


@dataclass(frozen=True)
class WeComWebhookHorizontalField:
    """horizontal_content_list row for text_notice template cards."""

    keyname: str
    value: str


@dataclass(frozen=True)
class WeComWebhookTextNoticeCard:
    """text_notice template_card — simplified subset of 99110."""

    main_title: str
    main_desc: str = ""
    sub_title_text: str = ""
    fields: tuple[WeComWebhookHorizontalField, ...] = ()
    card_action_url: str = ""
    source_desc: str = "MindGraph"


def build_text_payload(message: WeComWebhookTextMessage) -> dict[str, Any]:
    """Build webhook text payload (99110 §文本类型)."""
    text_body: dict[str, Any] = {
        "content": truncate_utf8(message.content, WEBHOOK_TEXT_MAX_BYTES),
    }
    if message.mentioned_list:
        text_body["mentioned_list"] = list(message.mentioned_list)
    if message.mentioned_mobile_list:
        text_body["mentioned_mobile_list"] = list(message.mentioned_mobile_list)
    return {"msgtype": "text", "text": text_body}


def build_markdown_payload(message: WeComWebhookMarkdownMessage) -> dict[str, Any]:
    """Build webhook markdown payload (99110 §markdown类型)."""
    return {
        "msgtype": "markdown",
        "markdown": {
            "content": truncate_utf8(message.content, WEBHOOK_MARKDOWN_MAX_BYTES),
        },
    }


def build_markdown_v2_payload(message: WeComWebhookMarkdownV2Message) -> dict[str, Any]:
    """Build webhook markdown_v2 payload (99110 §markdown_v2类型)."""
    return {
        "msgtype": "markdown_v2",
        "markdown_v2": {
            "content": truncate_utf8(message.content, WEBHOOK_MARKDOWN_V2_MAX_BYTES),
        },
    }


def build_news_payload(articles: tuple[WeComWebhookNewsArticle, ...]) -> dict[str, Any]:
    """Build webhook news payload (99110 §图文类型)."""
    if len(articles) < WEBHOOK_NEWS_ARTICLES_MIN or len(articles) > WEBHOOK_NEWS_ARTICLES_MAX:
        raise ValueError(f"news articles count must be {WEBHOOK_NEWS_ARTICLES_MIN}-{WEBHOOK_NEWS_ARTICLES_MAX}")
    article_rows: list[dict[str, str]] = []
    for article in articles:
        row: dict[str, str] = {
            "title": truncate_utf8(article.title, WEBHOOK_NEWS_TITLE_MAX_BYTES),
            "url": article.url.strip(),
        }
        if article.description.strip():
            row["description"] = truncate_utf8(
                article.description,
                WEBHOOK_NEWS_DESCRIPTION_MAX_BYTES,
            )
        if article.picurl.strip():
            row["picurl"] = article.picurl.strip()
        article_rows.append(row)
    return {"msgtype": "news", "news": {"articles": article_rows}}


def build_image_payload(message: WeComWebhookImageMessage) -> dict[str, Any]:
    """Build webhook image payload (99110 §图片类型)."""
    return {
        "msgtype": "image",
        "image": {
            "base64": message.base64_data,
            "md5": message.md5_hex,
        },
    }


def build_file_payload(message: WeComWebhookMediaMessage) -> dict[str, Any]:
    """Build webhook file payload (99110 §文件类型)."""
    return {"msgtype": "file", "file": {"media_id": message.media_id}}


def build_voice_payload(message: WeComWebhookMediaMessage) -> dict[str, Any]:
    """Build webhook voice payload (99110 §语音类型)."""
    return {"msgtype": "voice", "voice": {"media_id": message.media_id}}


def build_text_notice_card_payload(card: WeComWebhookTextNoticeCard) -> dict[str, Any]:
    """Build text_notice template_card payload (99110 §文本通知模版卡片)."""
    horizontal_list: list[dict[str, str]] = []
    for field in card.fields[:6]:
        horizontal_list.append(
            {
                "keyname": truncate_utf8(field.keyname, 20),
                "value": field.value,
            }
        )
    template_card: dict[str, Any] = {
        "card_type": "text_notice",
        "source": {"desc": card.source_desc, "desc_color": 0},
        "main_title": {
            "title": card.main_title,
        },
        "card_action": {
            "type": 1,
            "url": card.card_action_url,
        },
    }
    if card.main_desc.strip():
        template_card["main_title"]["desc"] = card.main_desc
    if card.sub_title_text.strip():
        template_card["sub_title_text"] = card.sub_title_text
    if horizontal_list:
        template_card["horizontal_content_list"] = horizontal_list
    return {"msgtype": "template_card", "template_card": template_card}


def append_markdown_mentions(
    content: str,
    mention_userids: tuple[str, ...],
) -> str:
    """Append <@userid> tokens for markdown @ mentions (99110)."""
    mentions = " ".join(f"<@{userid.strip()}>" for userid in mention_userids if userid.strip())
    if not mentions:
        return content
    return f"{content}\n\n{mentions}"
