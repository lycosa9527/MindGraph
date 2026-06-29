"""Shared chat message types, markdown export, and text/md parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_BRACKET_LINE_RE = re.compile(r"^\[(?P<time>[^\]]+)\]\s*(?P<sender>[^:]+):\s*(?P<text>.+)$")
_PLAIN_TIME_LINE_RE = re.compile(
    r"^(?:(?P<time>\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s*)?"
    r"(?P<sender>[^:]+):\s*(?P<text>.+)$"
)
_SIMPLE_LINE_RE = re.compile(r"^(?P<sender>[^:]+):\s*(?P<text>.+)$")


@dataclass(frozen=True)
class ExportPreview:
    """Summary of a local chat export file."""

    title: str
    path: Path
    message_count: int


ChatPreview = ExportPreview


@dataclass(frozen=True)
class ChatMessage:
    """Normalized chat line."""

    sender: str
    text: str
    timestamp: Optional[str] = None


MAX_EXPORT_MESSAGES = 5000
MAX_TRANSCRIPT_CHARS = 200_000


def parse_text_export_file(path: Path, max_messages: int = MAX_EXPORT_MESSAGES) -> List[ChatMessage]:
    """Parse a markdown or plain-text chat export into structured messages."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    messages: List[ChatMessage] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parsed = _parse_message_line(stripped)
        if parsed is None:
            messages.append(ChatMessage(sender="Unknown", text=stripped))
        else:
            messages.append(parsed)
        if len(messages) >= max_messages:
            break
    return messages


def _parse_message_line(stripped: str) -> Optional[ChatMessage]:
    bracket_match = _BRACKET_LINE_RE.match(stripped)
    if bracket_match:
        return ChatMessage(
            sender=bracket_match.group("sender").strip(),
            text=bracket_match.group("text").strip(),
            timestamp=bracket_match.group("time").strip() or None,
        )
    plain_match = _PLAIN_TIME_LINE_RE.match(stripped)
    if plain_match:
        timestamp = (plain_match.group("time") or "").strip() or None
        return ChatMessage(
            sender=plain_match.group("sender").strip(),
            text=plain_match.group("text").strip(),
            timestamp=timestamp,
        )
    simple_match = _SIMPLE_LINE_RE.match(stripped)
    if simple_match:
        return ChatMessage(
            sender=simple_match.group("sender").strip(),
            text=simple_match.group("text").strip(),
            timestamp=None,
        )
    return None


def messages_to_markdown(
    messages: List[ChatMessage],
    chat_title: str,
    platform: str,
    max_chars: int = MAX_TRANSCRIPT_CHARS,
) -> str:
    """Render chat messages as markdown for export and Knowledge Space ingest."""
    lines: List[str] = []
    header = f"# {(chat_title or 'Chat export').strip()} ({platform})"
    lines.append(header)
    lines.append("")

    for msg in messages:
        if not msg.text:
            continue
        sender = msg.sender.strip() or "Unknown"
        timestamp = (msg.timestamp or "").strip()
        if timestamp:
            lines.append(f"[{timestamp}] {sender}: {msg.text}")
        else:
            lines.append(f"{sender}: {msg.text}")

    body = "\n".join(lines).strip()
    if len(body) > max_chars:
        body = body[:max_chars]
    if not body or body == header:
        return ""
    return body + "\n"


def messages_to_payload(messages: List[ChatMessage]) -> List[dict]:
    """Convert messages to chat-handoff API shape (legacy JSON ingest path)."""
    return [
        {
            "sender": msg.sender,
            "text": msg.text,
            "timestamp": msg.timestamp,
        }
        for msg in messages
        if msg.text
    ]


def export_content_for_upload(path: Path, chat_title: str, platform: str) -> str:
    """Load markdown content for upload, preserving pre-rendered ``.md`` exports."""
    if path.suffix.lower() == ".md":
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            raise ValueError(str(exc)) from exc
        if text.startswith("#"):
            if len(text) > MAX_TRANSCRIPT_CHARS:
                return text[:MAX_TRANSCRIPT_CHARS]
            return text
    messages = parse_text_export_file(path)
    if not messages:
        raise ValueError("No messages found in export file")
    content = messages_to_markdown(messages, chat_title, platform).strip()
    if not content:
        raise ValueError("No text content in chat export")
    return content


def write_export_file(
    path: Path,
    messages: List[ChatMessage],
    *,
    title: str = "",
    platform: str = "wechat",
) -> int:
    """Write chat messages to a ``.md`` export file. Returns message count."""
    export_path = path if path.suffix.lower() == ".md" else path.with_suffix(".md")
    export_path.parent.mkdir(parents=True, exist_ok=True)
    body = messages_to_markdown(messages, title, platform)
    if not body:
        raise ValueError("No text content in chat export")
    export_path.write_text(body, encoding="utf-8")
    return sum(1 for msg in messages if msg.text)
