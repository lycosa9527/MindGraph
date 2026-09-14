"""Promote stacked-job thinking when fill never starts.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from fastapi import WebSocket

from services.diagram_edit.transport.kitty_ws import MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.agent_loop.results import (
    PENDING_AUTOCOMPLETE_KEY,
    take_stacked_progress_pending,
)
from services.kitty.session.runtime_state import voice_sessions


async def finalize_stacked_progress_if_idle(
    websocket: WebSocket,
    voice_session_id: str,
) -> None:
    """Speak the stacked thinking line only when generate was never armed."""
    live = voice_sessions.get(voice_session_id)
    if not isinstance(live, dict):
        return
    if isinstance(live.get(PENDING_AUTOCOMPLETE_KEY), dict):
        return
    pending = take_stacked_progress_pending(live)
    live.pop(MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY, None)
    if pending is None:
        return
    await emit_user_ack(
        websocket,
        voice_session_id,
        pending["text"],
        one_sentence_action=pending["action"],
        one_sentence_outcome="executed",
    )
