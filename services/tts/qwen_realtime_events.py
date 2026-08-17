"""Qwen-TTS Realtime WebSocket client events (session + text buffer).

Aliyun requires ``event_id`` on every client event:
https://help.aliyun.com/zh/model-studio/qwen-tts-realtime-client-events

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid
from typing import Any, Optional


def new_qwen_event_id() -> str:
    """Unique ``event_id`` for one Qwen-TTS Realtime client event."""
    return f"event_{uuid.uuid4().hex}"


def build_qwen_session_update(
    *,
    voice: str,
    response_format: str = "pcm",
    mode: str = "server_commit",
    sample_rate: Optional[int] = 24000,
    language_type: Optional[str] = None,
    event_id: Optional[str] = None,
) -> dict[str, Any]:
    """``session.update`` after ``session.created``."""
    session: dict[str, Any] = {
        "voice": voice,
        "response_format": response_format,
        "mode": mode,
    }
    if sample_rate is not None:
        session["sample_rate"] = sample_rate
    if language_type:
        session["language_type"] = language_type
    return {
        "event_id": event_id or new_qwen_event_id(),
        "type": "session.update",
        "session": session,
    }


def build_qwen_text_append(text: str, *, event_id: Optional[str] = None) -> dict[str, Any]:
    """``input_text_buffer.append``."""
    return {
        "event_id": event_id or new_qwen_event_id(),
        "type": "input_text_buffer.append",
        "text": text,
    }


def build_qwen_text_commit(*, event_id: Optional[str] = None) -> dict[str, Any]:
    """``input_text_buffer.commit`` (Commit mode, or force in ServerCommit)."""
    return {
        "event_id": event_id or new_qwen_event_id(),
        "type": "input_text_buffer.commit",
    }


def build_qwen_session_finish(*, event_id: Optional[str] = None) -> dict[str, Any]:
    """``session.finish`` — required before the server closes."""
    return {
        "event_id": event_id or new_qwen_event_id(),
        "type": "session.finish",
    }
