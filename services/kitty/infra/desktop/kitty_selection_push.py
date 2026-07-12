"""Push desktop canvas selection to mobile Kitty WebSocket clients.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.redis.kitty_session_redis import (
    load_kitty_live_context,
    upsert_kitty_redis_session,
)
from services.kitty.session.runtime_state import active_websockets, voice_sessions

logger = logging.getLogger(__name__)


def normalize_kitty_selected_nodes(raw: Any) -> List[str]:
    """Return unique non-empty node id strings (order preserved)."""
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return []
    out: List[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        node_id = item.strip()
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        out.append(node_id)
    return out


async def push_kitty_selection_to_mobile_scope(
    scope: str,
    user_id: int,
    selected_nodes: Optional[Sequence[str]],
) -> int:
    """
    Update in-memory Kitty session context + live_spec, then notify mobile WS clients.

    Desktop SSE fan-out is done by the HTTP handler so both directions can share this path.
    Returns number of WebSocket frames sent.
    """
    scope_key = str(scope or "").strip()
    if not scope_key:
        return 0
    normalized = normalize_kitty_selected_nodes(selected_nodes)

    for _sid, sess in list(voice_sessions.items()):
        if not isinstance(sess, dict):
            continue
        if str(sess.get("diagram_session_id") or "").strip() != scope_key:
            continue
        raw_uid = sess.get("user_id")
        if raw_uid is None:
            continue
        try:
            sess_uid = int(raw_uid)
        except (TypeError, ValueError):
            continue
        if sess_uid != int(user_id):
            continue
        ctx = sess.get("context")
        if isinstance(ctx, dict):
            ctx["selected_nodes"] = list(normalized)

    live = await load_kitty_live_context(scope_key)
    if isinstance(live, dict):
        live_payload: Dict[str, Any] = dict(live)
        live_payload["selected_nodes"] = list(normalized)
        lib = live_payload.get("diagram_library_id")
        lib_str = lib if isinstance(lib, str) and lib.strip() else None
        await upsert_kitty_redis_session(
            scope_key,
            int(user_id),
            active_diagram_library_id=lib_str,
            preserve_mobile_lane=True,
            live_payload=live_payload,
        )

    body: Dict[str, Any] = {
        "type": "selection_update",
        "scope": scope_key,
        "selected_nodes": list(normalized),
    }
    sent = 0
    for websocket in list(active_websockets.get(scope_key, [])):
        ok = await safe_websocket_send(websocket, body)
        if ok:
            sent += 1
    if sent:
        logger.debug(
            "[KittySelectionPush] scope=%s nodes=%s sent=%s",
            scope_key[:12],
            len(normalized),
            sent,
        )
    return sent
