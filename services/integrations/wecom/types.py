"""WeCom message types and UTF-8 byte limit helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from services.integrations.wecom.text_limits import truncate_utf8
from services.integrations.wecom.webhook_constants import WEBHOOK_MARKDOWN_MAX_BYTES
from services.integrations.wecom.webhook_payloads import (
    WeComWebhookMarkdownMessage,
    append_markdown_mentions,
    build_markdown_payload,
)

APP_MESSAGE_MAX_BYTES = 2048


@dataclass(frozen=True)
class WeComChannelResult:
    """Result from one delivery channel (webhook or app message)."""

    channel: str
    ok: bool
    errcode: int | None = None
    errmsg: str | None = None
    skipped: bool = False
    skip_reason: str | None = None


@dataclass
class WeComNotifyResult:
    """Aggregate result across enabled channels for a profile."""

    profile_id: str
    ok: bool
    not_configured: bool = False
    channels: list[WeComChannelResult] = field(default_factory=list)

    @property
    def any_channel_ok(self) -> bool:
        """True when at least one channel reported success."""
        return any(channel.ok for channel in self.channels)


@dataclass(frozen=True)
class WeComMessage:
    """Structured notification body rendered for WeCom channels."""

    title: str
    fields: dict[str, str]

    def render_webhook_markdown(self, mention_userids: tuple[str, ...] = ()) -> str:
        """Build markdown.content for webhook/send (99110 §markdown)."""
        lines = [f"# {self.title}"]
        for label, value in self.fields.items():
            cleaned = value.strip()
            if cleaned:
                lines.append(f"> {label}: {cleaned}")
        content = append_markdown_mentions("\n".join(lines), mention_userids)
        return truncate_utf8(content, WEBHOOK_MARKDOWN_MAX_BYTES)

    def build_webhook_markdown_payload(
        self,
        mention_userids: tuple[str, ...] = (),
    ) -> dict[str, object]:
        """Full webhook JSON payload for markdown msgtype (99110)."""
        content = self.render_webhook_markdown(mention_userids)
        return build_markdown_payload(WeComWebhookMarkdownMessage(content=content))

    def render_plain_text(self) -> str:
        """Build plain text for app message/send text body (90236)."""
        lines = [self.title, ""]
        for label, value in self.fields.items():
            cleaned = value.strip()
            if cleaned:
                lines.append(f"{label}: {cleaned}")
        return truncate_utf8("\n".join(lines), APP_MESSAGE_MAX_BYTES)
