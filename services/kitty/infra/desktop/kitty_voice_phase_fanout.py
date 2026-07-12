"""Fan out mobile Kitty voice phase to desktop SSE listeners.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Optional

from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_voice_phase_update,
)
from services.kitty.session.runtime_state import voice_sessions

_VALID_PHASES = frozenset({"listening", "speaking", "active"})
_SESSION_PHASE_KEY = "_desktop_voice_phase"


async def fanout_voice_phase_from_session(
    voice_session_id: str,
    phase: str,
) -> None:
    """Publish ``voice_phase_update`` when phase changes for this session."""
    normalized = str(phase or "").strip().lower()
    if normalized not in _VALID_PHASES:
        return
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return
    last = sess.get(_SESSION_PHASE_KEY)
    if last == normalized:
        return
    user_id_raw = sess.get("user_id")
    scope = sess.get("diagram_session_id")
    if user_id_raw is None or not isinstance(scope, str) or not scope.strip():
        return
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return
    sess[_SESSION_PHASE_KEY] = normalized
    await publish_kitty_voice_phase_update(user_id, scope.strip(), normalized)


async def fanout_voice_phase_from_outbound_type(
    voice_session_id: str,
    msg_type: Optional[str],
) -> None:
    """Map outbound WS frame types to desktop FAB phases."""
    kind = str(msg_type or "").strip().lower()
    if kind in {"text_chunk", "audio_chunk"}:
        await fanout_voice_phase_from_session(voice_session_id, "speaking")
        return
    if kind in {"response_done", "asr_stopped", "tts_done", "tts_interrupted"}:
        await fanout_voice_phase_from_session(voice_session_id, "active")
        return
    if kind == "asr_started":
        await fanout_voice_phase_from_session(voice_session_id, "listening")
