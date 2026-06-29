"""DingTalk local chat export reader (phase 2).

Supports JSON exports with ``messages`` arrays and plain-text fallbacks.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from file_reader.chat.messages import (
    ChatMessage,
    ExportPreview,
    MAX_EXPORT_MESSAGES,
    parse_text_export_file,
)

# Backward-compatible alias — same shape as WeChat previews.
DingTalkPreview = ExportPreview


def list_export_files(root: Path) -> List[ExportPreview]:
    """List DingTalk ``.md`` / ``.json`` / ``.txt`` exports under a directory."""
    if not root.is_dir():
        return []
    previews: List[ExportPreview] = []
    seen: set[Path] = set()
    candidates: List[Path] = []
    for pattern in ("*.md", "*.json", "*.txt"):
        candidates.extend(root.rglob(pattern))
    for path in sorted(candidates, key=lambda item: str(item).lower()):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        messages = parse_export_file(path)
        previews.append(ExportPreview(title=path.stem, path=path, message_count=len(messages)))
    return previews


def parse_export_file(path: Path, max_messages: int = MAX_EXPORT_MESSAGES) -> List[ChatMessage]:
    """Parse DingTalk JSON or text export."""
    if path.suffix.lower() == ".json":
        return _parse_json_export(path, max_messages)
    return parse_text_export_file(path, max_messages=max_messages)


def _parse_json_export(path: Path, max_messages: int) -> List[ChatMessage]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    raw_messages = data.get("messages") if isinstance(data, dict) else data
    if not isinstance(raw_messages, list):
        return []

    messages: List[ChatMessage] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        messages.append(
            ChatMessage(
                sender=str(item.get("sender") or item.get("nick") or "Unknown").strip(),
                text=text,
                timestamp=_optional_str(item.get("timestamp") or item.get("createdAt")),
            )
        )
        if len(messages) >= max_messages:
            break
    return messages


def _optional_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def messages_to_payload(messages: List[ChatMessage]) -> List[Dict[str, Any]]:
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
