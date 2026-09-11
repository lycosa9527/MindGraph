"""Dispatch content-level and branch-numbering Kitty actions.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack
from services.kitty.agent_loop.results import ui_result_content
from services.kitty.context.messaging import send_kitty_ws_action
from services.kitty.infra.desktop.kitty_voice_command_fanout import fanout_voice_command_from_session
from services.kitty.routing.preference_action_heuristics import (
    content_level_label,
    normalize_content_level,
    normalize_numbering_style,
    numbering_style_label,
)
from services.kitty.session.runtime_state import voice_sessions


async def dispatch_preference_action(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    command_text: str,
    lang: str,
) -> Optional[Dict[str, Any]]:
    """Handle set_content_level / set_branch_numbering. None if not a preference."""
    action = str(command.get("action") or "")
    if action == "set_content_level":
        return await _dispatch_content_level(
            websocket,
            voice_session_id,
            command=command,
            session_context=session_context,
            command_text=command_text,
            lang=lang,
        )
    if action == "set_branch_numbering":
        return await _dispatch_branch_numbering(
            websocket,
            voice_session_id,
            command=command,
            session_context=session_context,
            command_text=command_text,
            lang=lang,
        )
    return None


async def _dispatch_content_level(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    command_text: str,
    lang: str,
) -> Dict[str, Any]:
    level = normalize_content_level(command.get("level"))
    if level is None:
        return {
            "payload": ui_result_content(
                status="failed",
                action="set_content_level",
                extra={"error_code": "not_parsed"},
            ),
            "action": "set_content_level",
        }
    session_context["ai_content_level"] = level
    _write_session_context(voice_session_id, session_context)
    sent = await send_kitty_ws_action(
        websocket,
        voice_session_id,
        {"type": "action", "action": "set_content_level", "params": {"level": level}},
    )
    await fanout_voice_command_from_session(voice_session_id, "set_content_level")
    label = content_level_label(level, lang)
    ack_key = "ui.set_content_level" if sent else "ui.set_content_level.failed"
    await emit_user_ack(
        websocket,
        voice_session_id,
        render_ack(ack_key, {"level": label}, lang=lang),
        one_sentence_action="set_content_level",
        one_sentence_outcome="executed" if sent else "failed",
        one_sentence_user_text=command_text,
    )
    return {
        "payload": ui_result_content(
            status="ok" if sent else "failed",
            action="set_content_level",
            extra={"level": level},
        ),
        "action": "set_content_level",
        "stop_nonretryable": not sent,
    }


async def _dispatch_branch_numbering(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    command_text: str,
    lang: str,
) -> Dict[str, Any]:
    prefix = normalize_numbering_style(command.get("prefix"))
    if command.get("enabled") is False:
        enabled = False
        prefix = None
    else:
        enabled = command.get("enabled") is True or prefix is not None
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        diagram_data = {}
        session_context["diagram_data"] = diagram_data
    diagram_data["_mindmap_branch_numbering"] = enabled
    if prefix:
        diagram_data["_mindmap_branch_numbering_prefix"] = prefix
    _write_session_context(voice_session_id, session_context)
    params: Dict[str, Any] = {"enabled": enabled}
    if prefix:
        params["prefix"] = prefix
    sent = await send_kitty_ws_action(
        websocket,
        voice_session_id,
        {
            "type": "action",
            "action": "set_branch_numbering",
            "params": params,
        },
    )
    await fanout_voice_command_from_session(voice_session_id, "set_branch_numbering")
    ack_slots: Dict[str, str] = {}
    if not sent:
        ack_key = "ui.set_branch_numbering.failed"
    elif prefix:
        ack_key = "ui.set_branch_numbering.style"
        ack_slots["style"] = numbering_style_label(prefix, lang)
    elif enabled:
        ack_key = "ui.set_branch_numbering.on"
    else:
        ack_key = "ui.set_branch_numbering.off"
    await emit_user_ack(
        websocket,
        voice_session_id,
        render_ack(ack_key, ack_slots, lang=lang),
        one_sentence_action="set_branch_numbering",
        one_sentence_outcome="executed" if sent else "failed",
        one_sentence_user_text=command_text,
    )
    extra: Dict[str, Any] = {"enabled": enabled}
    if prefix:
        extra["prefix"] = prefix
    return {
        "payload": ui_result_content(
            status="ok" if sent else "failed",
            action="set_branch_numbering",
            extra=extra,
        ),
        "action": "set_branch_numbering",
        "stop_nonretryable": not sent,
    }


def _write_session_context(voice_session_id: str, session_context: Dict[str, Any]) -> None:
    live = voice_sessions.get(voice_session_id)
    if isinstance(live, dict):
        live["context"] = session_context
