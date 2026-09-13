"""Dispatch Kitty 节点解释 (explain_node) canvas actions.

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


def _node_label(command: Dict[str, Any]) -> str:
    for key in ("target", "node_label", "node_identifier"):
        raw = command.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return ""


async def dispatch_explain_node(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    command_text: str,
    lang: str,
) -> Optional[Dict[str, Any]]:
    """Open desktop 节点解释 for a grounded node. None if not explain_node."""
    action = str(command.get("action") or "")
    if action != "explain_node":
        return None
    node_id_raw = command.get("node_id")
    node_id = node_id_raw.strip() if isinstance(node_id_raw, str) else ""
    if not node_id:
        return {
            "payload": ui_result_content(
                status="failed",
                action=action,
                extra={"error_code": "not_parsed"},
            ),
            "action": action,
            "stop_nonretryable": True,
        }
    label = _node_label(command)
    params: Dict[str, Any] = {"node_id": node_id}
    if label:
        params["node_label"] = label
    sent = await send_kitty_ws_action(
        websocket,
        voice_session_id,
        {"type": "action", "action": "explain_node", "params": params},
    )
    await fanout_voice_command_from_session(voice_session_id, "explain_node")
    ack_key = "ui.explain_node" if sent else "ui.explain_node.failed"
    slots = {"target": label} if label else {}
    await emit_user_ack(
        websocket,
        voice_session_id,
        render_ack(ack_key, slots, lang=lang),
        one_sentence_action="explain_node",
        one_sentence_outcome="executed" if sent else "failed",
        one_sentence_user_text=command_text,
    )
    return {
        "payload": ui_result_content(
            status="ok" if sent else "failed",
            action=action,
            extra={"node_id": node_id, "target": label or None},
        ),
        "action": action,
        "stop_after": sent,
        "stop_nonretryable": not sent,
    }
