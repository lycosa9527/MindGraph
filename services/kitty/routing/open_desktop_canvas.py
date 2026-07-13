"""Durable library-draft create for voice ``open_desktop_canvas``.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Tuple

from fastapi import WebSocket

from services.diagram.generation_library_save import (
    SAVE_LIMIT_REACHED,
    try_save_diagram_to_library,
)
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack
from services.kitty.diagram.library_draft import (
    build_kitty_library_draft_spec,
    draft_title_for_diagram,
    normalize_library_diagram_type,
)
from services.kitty.infra.desktop.kitty_desktop_action_queue import (
    enqueue_kitty_desktop_action,
    mark_kitty_desktop_action_explicit_drain,
)
from services.kitty.infra.desktop.kitty_desktop_focus_push import (
    notify_kitty_desktop_focus_changed,
)
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_desktop_action_pending,
)
from services.kitty.session.manager import get_kitty_session_manager
from services.kitty.session.runtime_state import voice_sessions


async def execute_open_desktop_canvas_library_draft(
    *,
    websocket: WebSocket,
    voice_session_id: str,
    user_id: int,
    slug: str,
    command: Dict[str, Any],
    lang: str,
    organization_id: Optional[int],
) -> Tuple[bool, Optional[str]]:
    """
    Create a durable library draft, enqueue open_library_diagram, set desktop focus.

    Returns ``(ok, fail_reason)``. ``fail_reason`` is set when the draft/enqueue path
    fails before a successful route outcome; ack is always emitted by this helper.
    """
    targ = command.get("target")
    topic = targ.strip() if isinstance(targ, str) else ""
    left_raw = command.get("left")
    right_raw = command.get("right")
    left_text = left_raw.strip() if isinstance(left_raw, str) else ""
    right_text = right_raw.strip() if isinstance(right_raw, str) else ""
    library_type = normalize_library_diagram_type(slug)
    draft_spec = build_kitty_library_draft_spec(
        library_type,
        topic=topic,
        left=left_text,
        right=right_text,
    )
    title = draft_title_for_diagram(
        library_type,
        topic=topic or left_text,
        language=lang,
    )
    draft_id = await try_save_diagram_to_library(
        user_id,
        title=title,
        diagram_type=library_type,
        spec=draft_spec,
        language=lang,
        organization_id=organization_id,
        log_prefix="kitty_open_desktop_canvas",
        source_channel="kitty_voice",
    )
    if draft_id == SAVE_LIMIT_REACHED:
        await emit_user_ack(
            websocket,
            voice_session_id,
            render_ack("ui.open_desktop_canvas.library_full", lang=lang),
        )
        return False, "library_full"
    if not draft_id:
        await emit_user_ack(
            websocket,
            voice_session_id,
            render_ack("ui.open_desktop_canvas.fail", lang=lang),
        )
        return False, "library_draft_failed"

    payload: Dict[str, Any] = {
        "kind": "open_library_diagram",
        "diagram_library_id": draft_id,
        "title": title,
    }
    ok = await enqueue_kitty_desktop_action(user_id, payload)
    if ok:
        await mark_kitty_desktop_action_explicit_drain(user_id)
        await publish_kitty_desktop_action_pending(user_id)

    mgr = get_kitty_session_manager()
    focus_id, focus_at = await mgr.set_desktop_focus(user_id, draft_id)
    await notify_kitty_desktop_focus_changed(user_id, focus_id, focus_at)
    voice_sess = voice_sessions.get(voice_session_id)
    lane_raw = voice_sess.get("_kitty_client_lane") if isinstance(voice_sess, dict) else None
    ingress_lane = lane_raw if isinstance(lane_raw, str) and lane_raw.strip() else None
    await mgr.begin_ingress(
        user_id=user_id,
        scope=draft_id,
        request_id=str(uuid.uuid4()),
        source="ui_create",
        text=title,
        lane=ingress_lane,
        voice_session_id=voice_session_id,
    )

    if isinstance(voice_sess, dict):
        voice_sess["diagram_session_id"] = draft_id
        voice_sess["diagram_type"] = library_type
        ctx = voice_sess.get("context")
        if isinstance(ctx, dict):
            ctx["diagram_type"] = library_type
            ctx["diagram_library_id"] = draft_id
            ctx["diagram_data"] = draft_spec

    ack_key = "ui.open_desktop_canvas.ok" if ok else "ui.open_desktop_canvas.fail"
    await emit_user_ack(websocket, voice_session_id, render_ack(ack_key, lang=lang))
    return True, None if ok else "enqueue_failed"
