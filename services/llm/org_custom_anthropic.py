"""Official Anthropic Messages request shaping (system lift, role rules)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple


def message_text(content: Any) -> str:
    """Flatten Anthropic/OpenAI-style content into a single string."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: List[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
        return "\n".join(parts)
    if content is None:
        return ""
    return json.dumps(content, ensure_ascii=False)


def split_anthropic_messages(messages: List[Dict[str, Any]]) -> Tuple[Optional[str], List[Dict[str, str]]]:
    """Lift system role into top-level ``system``; keep user/assistant only."""
    system_parts: List[str] = []
    turns: List[Dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "user")
        text = message_text(message.get("content"))
        if not text:
            continue
        if role == "system":
            system_parts.append(text)
            continue
        mapped = "assistant" if role == "assistant" else "user"
        if turns and turns[-1]["role"] == mapped:
            turns[-1]["content"] = f"{turns[-1]['content']}\n{text}"
        else:
            turns.append({"role": mapped, "content": text})
    if not turns:
        turns.append({"role": "user", "content": "ping"})
    if turns[0]["role"] != "user":
        turns.insert(0, {"role": "user", "content": "ping"})
    system_text = "\n\n".join(system_parts).strip()
    return (system_text or None, turns)
