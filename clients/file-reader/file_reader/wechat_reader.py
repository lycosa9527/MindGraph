"""WeChat local chat export reader (phase 1).

Reads plain-text exports and line-oriented backup files. Full encrypted DB
decryption is out of scope for v1 — users can export chats or point at a
folder of ``.txt`` exports.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

_LINE_RE = re.compile(
    r"^(?:(?P<time>\d{4}[-/]\d{1,2}[-/]\d{1,2}[ T]\d{1,2}:\d{2}(?::\d{2})?)\s*)?"
    r"(?P<sender>[^:]+):\s*(?P<text>.+)$"
)


@dataclass(frozen=True)
class ExportPreview:
    """Summary of a local chat export file."""

    title: str
    path: Path
    message_count: int


# Backward-compatible alias for WeChat exports.
ChatPreview = ExportPreview


@dataclass(frozen=True)
class ChatMessage:
    """Normalized chat line."""

    sender: str
    text: str
    timestamp: Optional[str] = None


MAX_EXPORT_MESSAGES = 5000  # Matches ChatHandoffIngestRequest.messages max_length


def list_export_files(root: Path) -> List[ExportPreview]:
    """List ``.txt`` chat exports under a directory."""
    if not root.is_dir():
        return []
    previews: List[ExportPreview] = []
    for path in sorted(root.rglob("*.txt")):
        messages = parse_export_file(path)
        title = path.stem.replace("_", " ")
        previews.append(ExportPreview(title=title, path=path, message_count=len(messages)))
    return previews


def parse_export_file(path: Path, max_messages: int = MAX_EXPORT_MESSAGES) -> List[ChatMessage]:
    """Parse a WeChat-style text export into structured messages."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    messages: List[ChatMessage] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _LINE_RE.match(stripped)
        if match:
            messages.append(
                ChatMessage(
                    sender=match.group("sender").strip(),
                    text=match.group("text").strip(),
                    timestamp=(match.group("time") or "").strip() or None,
                )
            )
        else:
            messages.append(ChatMessage(sender="Unknown", text=stripped))
        if len(messages) >= max_messages:
            break
    return messages


def messages_to_payload(messages: List[ChatMessage]) -> List[dict]:
    """Convert messages to chat-handoff API shape."""
    return [
        {
            "sender": msg.sender,
            "text": msg.text,
            "timestamp": msg.timestamp,
        }
        for msg in messages
        if msg.text
    ]
