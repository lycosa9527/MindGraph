"""
MindMate export view model + serializers (JSON source of truth, self-contained HTML).

The JSON model is full-fidelity (conversation/message ids, role, text, UTC epoch
timestamps, feedback, source Dify server). The HTML renderer derives a
self-contained (inline CSS, no network) scrollable chat-bubble transcript from
the same model, so the in-panel viewer and the downloaded page look alike.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, List, Optional

SCHEMA_VERSION = 2


@dataclass
class ExportBubble:
    """One chat bubble (a user query or an assistant answer)."""

    role: str  # "user" | "assistant"
    text: str
    created_at: int  # UTC epoch seconds
    message_id: str
    files: List[dict] = field(default_factory=list)
    feedback: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize bubble to a JSON-ready dict."""
        return {
            "role": self.role,
            "text": self.text,
            "created_at": self.created_at,
            "message_id": self.message_id,
            "files": self.files,
            "feedback": self.feedback,
        }


@dataclass
class ExportConversation:
    """A single conversation with its ordered bubbles, tagged by source server."""

    conversation_id: str
    name: str
    server: int
    organization_id: int
    dify_user: str
    user_id: Optional[int]
    user_label: str
    channel: str
    created_at: int
    updated_at: int
    mindbot_config_id: Optional[int] = None
    endpoint_source: str = "org_server"
    dingtalk_chat_scope: Optional[str] = None
    dingtalk_conversation_id: Optional[str] = None
    bubbles: List[ExportBubble] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize conversation to a JSON-ready dict."""
        payload = {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "server": self.server,
            "organization_id": self.organization_id,
            "dify_user": self.dify_user,
            "user_id": self.user_id,
            "user_label": self.user_label,
            "channel": self.channel,
            "mindbot_config_id": self.mindbot_config_id,
            "endpoint_source": self.endpoint_source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "bubbles": [b.to_dict() for b in self.bubbles],
        }
        if self.dingtalk_chat_scope:
            payload["dingtalk_chat_scope"] = self.dingtalk_chat_scope
        if self.dingtalk_conversation_id:
            payload["dingtalk_conversation_id"] = self.dingtalk_conversation_id
        return payload


@dataclass
class ExportConversationSummary:
    """Lightweight conversation row for the list endpoint (no message bodies)."""

    conversation_id: str
    name: str
    server: int
    organization_id: int
    dify_user: str
    user_id: Optional[int]
    user_label: str
    channel: str
    created_at: int
    updated_at: int
    mindbot_config_id: Optional[int] = None
    endpoint_source: str = "org_server"
    dingtalk_chat_scope: Optional[str] = None
    dingtalk_conversation_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serialize summary to a JSON-ready dict."""
        payload = {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "server": self.server,
            "organization_id": self.organization_id,
            "dify_user": self.dify_user,
            "user_id": self.user_id,
            "user_label": self.user_label,
            "channel": self.channel,
            "mindbot_config_id": self.mindbot_config_id,
            "endpoint_source": self.endpoint_source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self.dingtalk_chat_scope:
            payload["dingtalk_chat_scope"] = self.dingtalk_chat_scope
        if self.dingtalk_conversation_id:
            payload["dingtalk_conversation_id"] = self.dingtalk_conversation_id
        return payload


@dataclass
class ExportBundle:
    """A full export: scope metadata plus every collected conversation."""

    organization_id: Optional[int]
    organization_name: str
    scope: str
    conversations: List[ExportConversation] = field(default_factory=list)
    generated_at: int = field(default_factory=lambda: int(datetime.now(UTC).timestamp()))
    warnings: List[str] = field(default_factory=list)
    partial_failures: int = 0
    verification_report: Optional[dict] = None

    def to_json_dict(self) -> dict:
        """Serialize the whole bundle to a JSON-ready dict (source of truth)."""
        payload = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "organization_id": self.organization_id,
            "organization_name": self.organization_name,
            "scope": self.scope,
            "conversation_count": len(self.conversations),
            "warnings": self.warnings,
            "partial_failures": self.partial_failures,
            "conversations": [c.to_dict() for c in self.conversations],
        }
        if self.verification_report is not None:
            payload["verification_report"] = self.verification_report
        return payload

    def to_json(self) -> str:
        """JSON string for download (UTF-8, pretty-printed)."""
        return json.dumps(self.to_json_dict(), ensure_ascii=False, indent=2)


def _fmt_ts(epoch: int) -> str:
    """Format a UTC epoch as a readable UTC timestamp string."""
    if not epoch:
        return ""
    try:
        return datetime.fromtimestamp(int(epoch), UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OverflowError, OSError):
        return ""


_HTML_CSS = """
:root { color-scheme: light dark; }
* { box-sizing: border-box; }
body {
  margin: 0; padding: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    "PingFang SC", "Microsoft YaHei", sans-serif;
  background: #f4f5f7; color: #1f2329;
}
.export-header {
  position: sticky; top: 0; z-index: 5;
  padding: 16px 20px; background: #ffffff; border-bottom: 1px solid #e5e6eb;
}
.export-header h1 { margin: 0 0 4px; font-size: 18px; }
.export-meta { font-size: 12px; color: #6b7280; }
.conv { max-width: 860px; margin: 20px auto; padding: 0 16px; }
.conv-card { background: #ffffff; border: 1px solid #e5e6eb; border-radius: 10px; overflow: hidden; }
.conv-title {
  padding: 12px 16px; border-bottom: 1px solid #f0f0f0;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.conv-title strong { font-size: 14px; }
.conv-sub { font-size: 12px; color: #8a8f99; }
.badge {
  display: inline-block; font-size: 11px; padding: 1px 8px; border-radius: 999px;
  background: #eef2ff; color: #3b5bdb; border: 1px solid #dbe1ff;
}
.badge.s2 { background: #fff4e6; color: #d9480f; border-color: #ffe0c2; }
.badge.scope-group { background: #e6fcf5; color: #087f5b; border-color: #c3fae8; }
.badge.scope-cross-org { background: #fff0f6; color: #c2255c; border-color: #ffdeeb; }
.badge.scope-oto { background: #f3f0ff; color: #5f3dc4; border-color: #e5dbff; }
.bubbles { padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; }
.row { display: flex; }
.row.user { justify-content: flex-end; }
.row.assistant { justify-content: flex-start; }
.bubble {
  max-width: 78%; padding: 9px 12px; border-radius: 12px; font-size: 14px;
  line-height: 1.5; white-space: pre-wrap; word-break: break-word;
}
.row.user .bubble { background: #3b5bdb; color: #ffffff; border-bottom-right-radius: 3px; }
.row.assistant .bubble { background: #f2f3f5; color: #1f2329; border-bottom-left-radius: 3px; }
.bubble .ts { display: block; margin-top: 4px; font-size: 11px; opacity: 0.7; }
.bubble .files { margin-top: 6px; font-size: 12px; opacity: 0.85; }
.bubble .fb { margin-top: 4px; font-size: 11px; }
.empty { padding: 30px; text-align: center; color: #8a8f99; }
@media (prefers-color-scheme: dark) {
  body { background: #17181c; color: #e5e6eb; }
  .export-header, .conv-card { background: #1f2024; border-color: #2c2e33; }
  .row.assistant .bubble { background: #2c2e33; color: #e5e6eb; }
}
"""


def _render_files(files: List[dict]) -> str:
    """Render a compact file listing for a bubble."""
    if not files:
        return ""
    names: List[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        label = item.get("filename") or item.get("name") or item.get("type") or "file"
        names.append(html.escape(str(label)))
    if not names:
        return ""
    return f'<div class="files">📎 {", ".join(names)}</div>'


def _render_bubble(bubble: ExportBubble) -> str:
    """Render one bubble row."""
    role_class = "user" if bubble.role == "user" else "assistant"
    text = html.escape(bubble.text or "")
    ts = _fmt_ts(bubble.created_at)
    parts = [f'<div class="row {role_class}"><div class="bubble">{text}']
    parts.append(_render_files(bubble.files))
    if bubble.feedback:
        mark = "👍" if bubble.feedback == "like" else "👎" if bubble.feedback == "dislike" else ""
        if mark:
            parts.append(f'<div class="fb">{mark}</div>')
    if ts:
        parts.append(f'<span class="ts">{html.escape(ts)}</span>')
    parts.append("</div></div>")
    return "".join(parts)


def _chat_scope_badge(scope: Optional[str]) -> str:
    """Render a DingTalk chat-scope pill when scope metadata is present."""
    if not scope:
        return ""
    normalized = scope.strip().lower()
    labels = {
        "group": "DingTalk group",
        "cross_org_group": "Cross-org group",
        "oto": "DingTalk 1:1",
        "1:1": "DingTalk 1:1",
    }
    css = {
        "group": "scope-group",
        "cross_org_group": "scope-cross-org",
        "oto": "scope-oto",
        "1:1": "scope-oto",
    }
    label = labels.get(normalized, scope)
    css_class = css.get(normalized, "scope-group")
    return (
        f'<span class="badge {css_class}">{html.escape(label)}</span>'
    )


def _render_conversation(conv: ExportConversation) -> str:
    """Render one conversation card."""
    server_badge = f'<span class="badge s{conv.server}">Server {conv.server}</span>'
    scope_badge = _chat_scope_badge(conv.dingtalk_chat_scope)
    title = html.escape(conv.name or conv.conversation_id)
    sub = html.escape(
        f"{conv.user_label} · {_fmt_ts(conv.created_at)}"
    )
    bubbles_html = "".join(_render_bubble(b) for b in conv.bubbles)
    if not bubbles_html:
        bubbles_html = '<div class="empty">No messages</div>'
    return (
        '<section class="conv"><div class="conv-card">'
        f'<div class="conv-title"><strong>{title}</strong>{scope_badge}{server_badge}'
        f'<span class="conv-sub">{sub}</span></div>'
        f'<div class="bubbles">{bubbles_html}</div>'
        "</div></section>"
    )


def render_html(bundle: ExportBundle) -> str:
    """Render a self-contained HTML transcript page from the export bundle."""
    org_name = html.escape(bundle.organization_name or "")
    meta = html.escape(
        f"Scope: {bundle.scope} · Conversations: {len(bundle.conversations)} · "
        f"Generated: {_fmt_ts(bundle.generated_at)}"
    )
    body_parts: List[str] = []
    if not bundle.conversations:
        body_parts.append('<div class="empty">No conversations found for this selection.</div>')
    else:
        body_parts.extend(_render_conversation(c) for c in bundle.conversations)
    body = "".join(body_parts)
    return (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>MindMate Export · {org_name}</title>"
        f"<style>{_HTML_CSS}</style></head><body>"
        f'<div class="export-header"><h1>MindMate 记录导出 · {org_name}</h1>'
        f'<div class="export-meta">{meta}</div></div>'
        f"{body}</body></html>"
    )


def split_message_to_bubbles(message: dict, server: int) -> List[ExportBubble]:
    """
    Split one Dify message object into a user bubble (query) and an assistant
    bubble (answer), preserving message files and feedback on the answer.
    """
    _ = server
    message_id = str(message.get("id") or "")
    created_at = int(message.get("created_at") or 0)
    bubbles: List[ExportBubble] = []

    query = (message.get("query") or "").strip()
    inputs_files = message.get("message_files") or []
    if query or inputs_files:
        bubbles.append(
            ExportBubble(
                role="user",
                text=query,
                created_at=created_at,
                message_id=message_id,
                files=[f for f in inputs_files if isinstance(f, dict)],
            )
        )

    answer = (message.get("answer") or "").strip()
    feedback = message.get("feedback") or {}
    rating = feedback.get("rating") if isinstance(feedback, dict) else None
    if answer:
        bubbles.append(
            ExportBubble(
                role="assistant",
                text=answer,
                created_at=created_at,
                message_id=message_id,
                feedback=rating,
            )
        )
    return bubbles


def conversation_created_at(conversation: dict) -> int:
    """Best-effort UTC epoch for a Dify conversation object."""
    raw: Any = conversation.get("created_at") or conversation.get("updated_at") or 0
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0
