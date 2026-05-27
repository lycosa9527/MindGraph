"""Fan out mobile Kitty voice command labels to desktop SSE listeners."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.kitty.infra.desktop.kitty_desktop_wake_fanout import publish_kitty_voice_command_log
from services.kitty.session.runtime_state import voice_sessions


def _clip(text: str, limit: int = 120) -> str:
    cleaned = " ".join(str(text).split()).strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


def _detail_from_params(params: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(params, dict):
        return None
    for key in ("target", "new_text", "text", "message", "node_label", "node_id"):
        raw = params.get(key)
        if isinstance(raw, str) and raw.strip():
            return _clip(raw.strip())
    return None


def _detail_from_diagram_updates(updates: Any) -> Optional[str]:
    if isinstance(updates, dict):
        for key in ("text", "label", "topic", "target"):
            raw = updates.get(key)
            if isinstance(raw, str) and raw.strip():
                return _clip(raw.strip())
        nodes = updates.get("nodes")
        if isinstance(nodes, list) and nodes:
            first = nodes[0]
            if isinstance(first, dict):
                for key in ("text", "label"):
                    raw = first.get(key)
                    if isinstance(raw, str) and raw.strip():
                        return _clip(raw.strip())
    if isinstance(updates, list) and updates:
        first = updates[0]
        if isinstance(first, dict):
            for key in ("text", "label"):
                raw = first.get(key)
                if isinstance(raw, str) and raw.strip():
                    return _clip(raw.strip())
    return None


async def fanout_voice_command_from_session(
    voice_session_id: str,
    action: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    updates: Any = None,
) -> None:
    """Publish a ``voice_command`` SSE frame for desktop command log UI."""
    sess = voice_sessions.get(voice_session_id)
    if not isinstance(sess, dict):
        return
    user_id_raw = sess.get("user_id")
    scope = sess.get("diagram_session_id")
    if user_id_raw is None or not isinstance(scope, str) or not scope.strip():
        return
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return
    act = str(action or "").strip()
    if not act:
        return
    detail = _detail_from_params(params) or _detail_from_diagram_updates(updates)
    await publish_kitty_voice_command_log(
        user_id,
        scope.strip(),
        action=act,
        detail=detail,
    )
