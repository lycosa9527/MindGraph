"""Structured Kitty voice-to-diagram workflow trace logging (no audio chunk noise).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from services.kitty.session.runtime_state import voice_sessions

_LOGGER = logging.getLogger("kitty.workflow")
_DETAIL_MAX = 240


def _env_falsy(name: str) -> bool:
    """Env falsy."""
    raw = os.environ.get(name, "")
    return raw.strip().lower() in ("0", "false", "no", "off")


def kitty_workflow_trace_enabled() -> bool:
    """On by default; set ``KITTY_WORKFLOW_TRACE=0`` to disable."""
    return not _env_falsy("KITTY_WORKFLOW_TRACE")


def _clip(text: str, limit: int = _DETAIL_MAX) -> str:
    """Clip."""
    cleaned = " ".join(str(text).split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


def _short_scope(scope: Optional[str]) -> str:
    """Short scope."""
    if not scope or not isinstance(scope, str):
        return "—"
    s = scope.strip()
    if len(s) <= 12:
        return s
    return f"{s[:12]}…"


def _short_sid(voice_session_id: Optional[str]) -> str:
    """Short sid."""
    if not voice_session_id or not isinstance(voice_session_id, str):
        return "—"
    s = voice_session_id.strip()
    if len(s) <= 10:
        return s
    return f"{s[:10]}…"


def _resolve_session(
    voice_session_id: Optional[str],
    scope: Optional[str],
    user_id: Optional[int],
) -> tuple[Optional[str], Optional[str], Optional[int]]:
    """Resolve session."""
    sid = voice_session_id.strip() if isinstance(voice_session_id, str) and voice_session_id.strip() else None
    sc = scope.strip() if isinstance(scope, str) and scope.strip() else None
    uid = user_id
    if sid:
        sess = voice_sessions.get(sid)
        if isinstance(sess, dict):
            if sc is None:
                raw_scope = sess.get("diagram_session_id")
                if isinstance(raw_scope, str) and raw_scope.strip():
                    sc = raw_scope.strip()
            if uid is None:
                raw_uid = sess.get("user_id")
                if raw_uid is not None:
                    try:
                        uid = int(raw_uid)
                    except (TypeError, ValueError):
                        uid = None
    return sid, sc, uid


def summarize_diagram_update(action: Optional[str], updates: Any) -> str:
    """Short human-readable summary for diagram_update payloads."""
    act = str(action or "").strip()
    parts: list[str] = []
    if act:
        parts.append(act)
    if isinstance(updates, dict):
        for key in ("text", "label", "topic", "target"):
            raw = updates.get(key)
            if isinstance(raw, str) and raw.strip():
                parts.append(f"{key}={_clip(raw.strip(), 48)}")
                break
        nodes = updates.get("nodes")
        if isinstance(nodes, list) and nodes:
            parts.append(f"nodes={len(nodes)}")
    elif isinstance(updates, list) and updates:
        parts.append(f"items={len(updates)}")
    return " ".join(parts) if parts else act or "diagram_update"


def kitty_wf_log(
    stage: str,
    detail: str,
    *,
    voice_session_id: Optional[str] = None,
    scope: Optional[str] = None,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log one step in the voice → hub → canvas pipeline.

    Stages include: transcription, route, diagram_execute, ws_out, sse_fanout,
    hub_sync, hub_context, hub_persist, library_refresh, selection_fanout, voice_command.
    """
    if not kitty_workflow_trace_enabled():
        return
    sid, sc, uid = _resolve_session(voice_session_id, scope, user_id)
    parts = [
        f"stage={stage}",
        f"sid={_short_sid(sid)}",
        f"scope={_short_scope(sc)}",
    ]
    if uid is not None:
        parts.append(f"uid={uid}")
    if action:
        parts.append(f"action={action}")
    msg_detail = _clip(detail)
    if msg_detail:
        parts.append(f"detail={msg_detail}")
    message = " | ".join(parts)
    if extra:
        _LOGGER.info("KITTY_WF %s | %s", message, extra)
    else:
        _LOGGER.info("KITTY_WF %s", message)
