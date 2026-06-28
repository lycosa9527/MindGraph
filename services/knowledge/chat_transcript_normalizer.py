"""Normalize WeChat / DingTalk chat exports into markdown for Knowledge Space ingest.

Author: lycosa9527
Made by: MindSpring Team

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List

MAX_TRANSCRIPT_CHARS = 200_000

ChatMessage = Dict[str, Any]


def normalize_chat_messages(
    messages: List[ChatMessage],
    chat_title: str,
    platform: str,
    max_chars: int = MAX_TRANSCRIPT_CHARS,
) -> str:
    """Render structured chat messages as markdown lines for indexing."""
    lines: List[str] = []
    header = f"# {chat_title.strip() or 'Chat export'} ({platform})"
    lines.append(header)
    lines.append("")

    for item in messages:
        sender = str(item.get("sender") or item.get("from") or "Unknown").strip()
        text = str(item.get("text") or item.get("content") or "").strip()
        if not text:
            continue
        timestamp = str(item.get("timestamp") or item.get("time") or "").strip()
        if timestamp:
            lines.append(f"[{timestamp}] {sender}: {text}")
        else:
            lines.append(f"{sender}: {text}")

    body = "\n".join(lines).strip()
    if len(body) > max_chars:
        body = body[:max_chars]
    if not body or body == header:
        raise ValueError("No text content in chat export")
    return body


def normalize_raw_content(content: str, chat_title: str, platform: str, max_chars: int = MAX_TRANSCRIPT_CHARS) -> str:
    """Accept preformatted transcript text from file-reader."""
    text = (content or "").strip()
    if not text:
        raise ValueError("Empty chat content")
    header = f"# {chat_title.strip() or 'Chat export'} ({platform})\n\n"
    combined = header + text if not text.startswith("#") else text
    if len(combined) > max_chars:
        combined = combined[:max_chars]
    return combined
