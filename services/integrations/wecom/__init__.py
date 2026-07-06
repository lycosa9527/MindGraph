"""WeCom (企业微信) outbound notification module."""

from services.integrations.wecom.orchestrator import notify
from services.integrations.wecom.profiles import PROFILE_SCHOOL_CONSULT, PROFILE_TECH_SUPPORT
from services.integrations.wecom.types import WeComMessage, WeComNotifyResult
from services.integrations.wecom.webhook_client import send_webhook_payload
from services.integrations.wecom.webhook_payloads import (
    WeComWebhookHorizontalField,
    WeComWebhookImageMessage,
    WeComWebhookMarkdownMessage,
    WeComWebhookMarkdownV2Message,
    WeComWebhookMediaMessage,
    WeComWebhookNewsArticle,
    WeComWebhookTextMessage,
    WeComWebhookTextNoticeCard,
    build_file_payload,
    build_image_payload,
    build_markdown_payload,
    build_markdown_v2_payload,
    build_news_payload,
    build_text_notice_card_payload,
    build_text_payload,
    build_voice_payload,
)

__all__ = [
    "PROFILE_SCHOOL_CONSULT",
    "PROFILE_TECH_SUPPORT",
    "WeComMessage",
    "WeComNotifyResult",
    "WeComWebhookHorizontalField",
    "WeComWebhookImageMessage",
    "WeComWebhookMarkdownMessage",
    "WeComWebhookMarkdownV2Message",
    "WeComWebhookMediaMessage",
    "WeComWebhookNewsArticle",
    "WeComWebhookTextMessage",
    "WeComWebhookTextNoticeCard",
    "build_file_payload",
    "build_image_payload",
    "build_markdown_payload",
    "build_markdown_v2_payload",
    "build_news_payload",
    "build_text_notice_card_payload",
    "build_text_payload",
    "build_voice_payload",
    "notify",
    "send_webhook_payload",
]
