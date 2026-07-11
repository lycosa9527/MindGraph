"""Hydrate KittySessionMemory from durable one-sentence turns on WS start.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from services.kitty.session.memory import get_session_memory
from services.kitty.session.one_sentence_turns import list_one_sentence_turns
from services.kitty.session.runtime_state import voice_sessions

logger = logging.getLogger(__name__)

_DEFAULT_HYDRATE_LIMIT = 20


async def hydrate_one_sentence_session_memory(
    *,
    voice_session_id: str,
    user_id: int,
    diagram_scope: str,
    limit: int = _DEFAULT_HYDRATE_LIMIT,
) -> int:
    """
    Load recent durable turns into KittySessionMemory and conversation_history.

    Returns the number of turns applied. No-op when the panel is not one_sentence
    or when no turns exist.
    """
    session = voice_sessions.get(voice_session_id)
    if session is None:
        return 0
    if str(session.get("active_panel") or "").strip() != "one_sentence":
        return 0

    scope = str(diagram_scope or session.get("diagram_session_id") or "").strip()
    if not scope or user_id <= 0:
        return 0

    result = await list_one_sentence_turns(scope, int(user_id), limit=max(1, min(limit, 50)))
    turns: List[Dict[str, Any]] = list(result.get("turns") or [])
    if not turns:
        return 0

    mem = get_session_memory(voice_session_id)
    history = session.get("conversation_history")
    if not isinstance(history, list):
        history = []
        session["conversation_history"] = history

    applied = 0
    for turn in turns:
        role = str(turn.get("role") or "").strip()
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        if role == "user":
            mem.append_user_turn(content, source="text")
            history.append({"role": "user", "content": content})
            applied += 1
        elif role == "kitty":
            mem.append_assistant_chunk(content)
            mem.flush_assistant_turn()
            history.append({"role": "assistant", "content": content})
            applied += 1

    logger.info(
        "[OneSentenceHydrate] voice=%s scope=%s turns=%d",
        voice_session_id[:12],
        scope[:16],
        applied,
    )
    return applied
