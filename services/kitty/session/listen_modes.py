"""Kitty listen modes: manual PTT vs auto half-duplex.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Literal, Optional

from services.kitty.session.runtime_state import voice_sessions

ListenMode = Literal["manual", "auto"]

LISTEN_MANUAL: ListenMode = "manual"
LISTEN_AUTO: ListenMode = "auto"
SESSION_LISTEN_MODE_KEY = "_kitty_listen_mode"


def normalize_listen_mode(raw: object) -> ListenMode:
    """Unknown values become manual (PTT). Auto is opt-in only."""
    text = str(raw or "").strip().lower()
    if text in {"auto", "automatic"}:
        return LISTEN_AUTO
    return LISTEN_MANUAL


def session_listen_mode(voice_session_id: str) -> ListenMode:
    """Per-session listen mode, default manual."""
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return LISTEN_MANUAL
    return normalize_listen_mode(sess.get(SESSION_LISTEN_MODE_KEY))


def set_session_listen_mode(voice_session_id: str, raw: object) -> ListenMode:
    """Store a normalized listen mode on the live session."""
    mode = normalize_listen_mode(raw)
    sess = voice_sessions.get(voice_session_id)
    if isinstance(sess, dict):
        sess[SESSION_LISTEN_MODE_KEY] = mode
    return mode


def is_auto_listen(voice_session_id: str) -> bool:
    """True when Fun-ASR final should commit without a PTT release."""
    return session_listen_mode(voice_session_id) == LISTEN_AUTO


def asr_commit_mode(voice_session_id: str) -> str:
    """Wire hint: auto uses Fun-ASR final; manual waits for ``asr_stop``."""
    if is_auto_listen(voice_session_id):
        return "final_or_stopped"
    return "release_only"


def parse_hello_listen_mode(message: dict) -> Optional[ListenMode]:
    """Read ``listen_mode`` from a hello payload, or ``None`` when omitted."""
    if "listen_mode" not in message:
        return None
    return normalize_listen_mode(message.get("listen_mode"))
