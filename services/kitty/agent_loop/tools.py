"""Tool schemas and dispatch for the typed Kitty agent loop.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.diagram.mindmap_identity import (
    identity_aliases,
    migrate_mindmap_diagram_payload,
    read_mindmap_uid,
)
from services.diagram.mindmap_location import is_leftover_mindmap_branch_id
from services.diagram_edit.types import ToolResult
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_ack, render_ack_for_command, render_clarify_options_ack
from services.kitty.adapters.diagram_command import apply_kitty_legacy_diagram_command
from services.kitty.agent_loop.messages import read_diagram_tool_schema
from services.kitty.agent_loop.results import tool_result_content, ui_result_content
from services.kitty.context.messaging import resolve_voice_interaction_language, send_kitty_ws_action
from services.kitty.diagram.hub_bridge import try_sync_voice_diagram_to_hub
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import publish_kitty_selection_update
from services.kitty.infra.desktop.kitty_voice_command_fanout import fanout_voice_command_from_session
from services.kitty.omni.tools import build_omni_diagram_tools, omni_function_call_to_command
from services.kitty.routing.diagram_agent_context import enrich_node_action_command
from services.kitty.routing.node_action_library import (
    build_node_action_tools,
    command_from_tool_call,
    render_diagram_snapshot_block,
)
from services.kitty.routing.one_sentence_edit_helpers import is_mindmap_diagram_type
from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import (
    normalize_voice_desktop_canvas_diagram_type,
)
from services.kitty.routing.open_desktop_canvas import execute_open_desktop_canvas_library_draft
from services.kitty.routing.pending_branch_autocomplete import emit_auto_complete_branch
from services.kitty.routing.pending_clarify_options import arm_pending_clarify_options
from services.kitty.session.runtime_state import voice_sessions

STRUCTURAL_ACTIONS = frozenset(
    {
        "update_center",
        "update_node",
        "add_node",
        "delete_node",
    }
)
IDENTITY_REQUIRED_ACTIONS = frozenset(
    {
        "update_node",
        "delete_node",
        "auto_complete_branch",
        "select_node",
    }
)
_OMNI_UI_NAMES = frozenset(
    {
        "select_node",
        "start_inline_recommendations",
        "add_node_with_recommendations",
        "explain_node",
        "ask_mindmate",
        "open_panel",
        "close_panel",
        "open_desktop_canvas",
    }
)


@dataclass(slots=True)
class ToolDispatchResult:
    """Outcome of one tool execution."""

    payload: Dict[str, Any]
    action: str
    stop_clarify: bool = False
    stop_nonretryable: bool = False
    mutated: bool = False


def loop_tool_schemas() -> List[Dict[str, Any]]:
    """Node-action library + read_diagram + Omni UI-only tools."""
    schemas = list(build_node_action_tools())
    schemas.append(read_diagram_tool_schema())
    for item in build_omni_diagram_tools():
        fn = item.get("function")
        if not isinstance(fn, dict):
            continue
        name = fn.get("name")
        if name in _OMNI_UI_NAMES:
            schemas.append(item)
    return schemas


def map_tool_call_to_command(name: str, arguments_json: str) -> Dict[str, Any]:
    """Map a loop tool name to a legacy command dict."""
    if name == "read_diagram":
        return {"action": "read_diagram", "confidence": 1.0}
    if name.startswith("diagram.") or name.startswith("node_action."):
        return command_from_tool_call(name, arguments_json)
    return omni_function_call_to_command(name, arguments_json)


def ensure_live_mindmap_identity(session_context: Dict[str, Any]) -> None:
    """Rewrite leftover ``branch-*`` live ids to UUID before targeting."""
    diagram_data = session_context.get("diagram_data")
    if isinstance(diagram_data, dict):
        migrate_mindmap_diagram_payload(diagram_data)


def _aliases_from_context(session_context: Dict[str, Any]) -> Dict[str, str]:
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        return {}
    nodes_raw = diagram_data.get("nodes")
    typed = [node for node in nodes_raw if isinstance(node, dict)] if isinstance(nodes_raw, list) else []
    if not typed:
        return {}
    aliases = identity_aliases(typed)
    for node in typed:
        node_id = node.get("id")
        uid = read_mindmap_uid(node)
        if (
            isinstance(node_id, str)
            and is_leftover_mindmap_branch_id(node_id)
            and uid
            and not is_leftover_mindmap_branch_id(uid)
        ):
            aliases[node_id] = uid
            aliases[uid] = uid
            data = node.get("data")
            if isinstance(data, dict):
                legacy = data.get("mindMapLegacyId")
                if isinstance(legacy, str) and legacy.strip():
                    aliases[legacy.strip()] = uid
    return aliases


def leftover_live_key(
    command: Dict[str, Any],
    session_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Return leftover ``branch-*`` when used as a live key (aliases are allowed)."""
    action = str(command.get("action") or "")
    if action not in IDENTITY_REQUIRED_ACTIONS:
        return None
    aliases = _aliases_from_context(session_context or {})

    def _unaliased_leftover(raw: Any) -> Optional[str]:
        if not isinstance(raw, str) or not raw.strip():
            return None
        text = raw.strip()
        if not is_leftover_mindmap_branch_id(text):
            return None
        mapped = aliases.get(text)
        if isinstance(mapped, str) and mapped.strip() and not is_leftover_mindmap_branch_id(mapped):
            return None
        return text

    leftover_id = _unaliased_leftover(command.get("node_id"))
    if leftover_id:
        return leftover_id
    node_id = command.get("node_id")
    if isinstance(node_id, str) and node_id.strip() and not is_leftover_mindmap_branch_id(node_id.strip()):
        return None
    for key in ("node_identifier", "target"):
        leftover = _unaliased_leftover(command.get(key))
        if leftover:
            return leftover
    return None


def _session_scope(voice_session_id: str) -> str:
    session = voice_sessions.get(voice_session_id) or {}
    raw = session.get("diagram_session_id")
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return ""


def _session_user_id(voice_session_id: str) -> Optional[int]:
    session = voice_sessions.get(voice_session_id) or {}
    raw = session.get("user_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


async def dispatch_loop_tool(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    name: str,
    arguments_json: str,
    session_context: Dict[str, Any],
    diagram_type: str,
    command_text: str,
    verify_required: bool,
) -> ToolDispatchResult:
    """Resolve identity, then Bus / UI / clarify. Never fake structural applied."""
    command = map_tool_call_to_command(name, arguments_json)
    return await dispatch_prepared_command(
        websocket,
        voice_session_id,
        command=command,
        session_context=session_context,
        diagram_type=diagram_type,
        command_text=command_text,
        verify_required=verify_required,
    )


async def dispatch_prepared_command(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    diagram_type: str,
    command_text: str,
    verify_required: bool,
) -> ToolDispatchResult:
    """Dispatch an already-mapped legacy command (identity resolve first)."""
    ensure_live_mindmap_identity(session_context)
    leftover = leftover_live_key(command, session_context)
    command = enrich_node_action_command(command, session_context)
    action = str(command.get("action") or "")
    lang = resolve_voice_interaction_language(session_context)

    if action == "read_diagram":
        snapshot = render_diagram_snapshot_block(
            session_context,
            diagram_type=diagram_type,
            lang="en" if lang == "en" else "zh",
        )
        return ToolDispatchResult(
            payload=ui_result_content(status="ok", action="read_diagram", extra={"snapshot": snapshot}),
            action="read_diagram",
        )

    if leftover:
        rejected = action or "unknown"
        return ToolDispatchResult(
            payload=ui_result_content(
                status="failed",
                action=rejected,
                message="leftover branch-* is not a live node id",
                extra={"error_code": "not_parsed", "node_id": leftover},
            ),
            action=rejected,
        )

    if action == "clarify_options":
        live = voice_sessions.get(voice_session_id)
        armed = arm_pending_clarify_options(live if isinstance(live, dict) else None, command)
        ack_text = render_clarify_options_ack(command, lang=lang)
        await emit_user_ack(
            websocket,
            voice_session_id,
            ack_text,
            one_sentence_action="clarify_options",
            one_sentence_outcome="executed",
            one_sentence_user_text=command_text,
            clarify_question=str(command.get("question") or "") or None,
            clarify_options=list(command.get("options") or []) if isinstance(command.get("options"), list) else None,
        )
        return ToolDispatchResult(
            payload=ui_result_content(
                status="ok",
                action="clarify_options",
                extra={"armed": armed},
            ),
            action="clarify_options",
            stop_clarify=True,
        )

    if action in STRUCTURAL_ACTIONS:
        return await _dispatch_structural(
            websocket,
            voice_session_id,
            command=command,
            session_context=session_context,
            diagram_type=diagram_type,
            verify_required=verify_required,
            lang=lang,
            command_text=command_text,
        )

    return await _dispatch_ui(
        websocket,
        voice_session_id,
        command=command,
        session_context=session_context,
        command_text=command_text,
        lang=lang,
    )


async def _dispatch_structural(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    diagram_type: str,
    verify_required: bool,
    lang: str,
    command_text: str,
) -> ToolDispatchResult:
    """Apply one structural command through the DiagramCommandBus."""
    action = str(command.get("action") or "")
    scope = _session_scope(voice_session_id)
    if not scope:
        payload = ui_result_content(
            status="rejected",
            action=action,
            extra={"error_code": "no_owner"},
        )
        return ToolDispatchResult(payload=payload, action=action, stop_nonretryable=True)

    use_verify = verify_required and is_mindmap_diagram_type(diagram_type)
    bus_result = await apply_kitty_legacy_diagram_command(
        websocket,
        voice_session_id,
        command,
        session_context,
        scope=scope,
        diagram_type=diagram_type,
        user_id=_session_user_id(voice_session_id),
        verify_required=use_verify,
    )
    tool_result: ToolResult = bus_result.tool_result
    payload = tool_result_content(tool_result)
    error_code = tool_result.error_code
    mutated = tool_result.status == "applied"
    if mutated:
        ack_text = render_ack_for_command(action, command, session_context, lang=lang, phase="done")
        await emit_user_ack(
            websocket,
            voice_session_id,
            ack_text,
            one_sentence_action=action,
            one_sentence_outcome="executed",
            one_sentence_user_text=command_text,
        )
    return ToolDispatchResult(
        payload=payload,
        action=action,
        mutated=mutated,
        stop_nonretryable=error_code in {"access_denied", "no_owner", "collab_active", "busy_llm_generating"},
    )


async def _dispatch_ui(
    websocket: WebSocket,
    voice_session_id: str,
    *,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    command_text: str,
    lang: str,
) -> ToolDispatchResult:
    """Canvas / panel actions that are not structural ExpectedEffect verifies."""
    del session_context
    action = str(command.get("action") or "")
    if action == "auto_complete":
        sent = await send_kitty_ws_action(
            websocket,
            voice_session_id,
            {"type": "action", "action": "auto_complete", "params": {}},
        )
        await fanout_voice_command_from_session(voice_session_id, "auto_complete")
        status = "ok" if sent else "failed"
        if sent:
            await emit_user_ack(websocket, voice_session_id, render_ack("ui.auto_complete", lang=lang))
        else:
            await emit_user_ack(websocket, voice_session_id, render_ack("ui.auto_complete.failed", lang=lang))
        return ToolDispatchResult(
            payload=ui_result_content(status=status, action=action),
            action=action,
            stop_nonretryable=not sent,
        )

    if action == "auto_complete_branch":
        target_raw = command.get("target") or command.get("node_label") or command.get("text")
        target = str(target_raw).strip() if isinstance(target_raw, str) else ""
        node_id_raw = command.get("node_id")
        node_id = str(node_id_raw).strip() if isinstance(node_id_raw, str) else ""
        sent = await emit_auto_complete_branch(
            websocket,
            voice_session_id,
            target,
            command_text=command_text,
            lang=lang,
            node_id=node_id or None,
        )
        return ToolDispatchResult(
            payload=ui_result_content(
                status="ok" if sent else "failed",
                action=action,
                extra={"node_id": node_id or None, "target": target},
            ),
            action=action,
            stop_nonretryable=not sent,
        )

    if action == "open_desktop_canvas":
        user_id = _session_user_id(voice_session_id)
        raw_slug = command.get("diagram_type")
        slug = normalize_voice_desktop_canvas_diagram_type(raw_slug if isinstance(raw_slug, str) else None)
        if user_id is None or slug is None:
            return ToolDispatchResult(
                payload=ui_result_content(status="failed", action=action, extra={"error_code": "not_parsed"}),
                action=action,
            )
        executed, fail_reason = await execute_open_desktop_canvas_library_draft(
            websocket=websocket,
            voice_session_id=voice_session_id,
            user_id=user_id,
            slug=slug,
            command=command,
            lang=lang,
            organization_id=None,
        )
        extra: Dict[str, Any] = {}
        if fail_reason:
            extra["message"] = fail_reason
        return ToolDispatchResult(
            payload=ui_result_content(status="ok" if executed else "failed", action=action, extra=extra or None),
            action=action,
        )

    if action == "select_node":
        node_id = command.get("node_id")
        if not isinstance(node_id, str) or not node_id.strip():
            return ToolDispatchResult(
                payload=ui_result_content(status="failed", action=action, extra={"error_code": "not_parsed"}),
                action=action,
            )
        resolved = node_id.strip()
        session_row = voice_sessions.get(voice_session_id)
        if isinstance(session_row, dict):
            ctx = dict(session_row.get("context") or {})
            ctx["selected_nodes"] = [resolved]
            diagram_data = ctx.get("diagram_data")
            if not isinstance(diagram_data, dict):
                diagram_data = {}
                ctx["diagram_data"] = diagram_data
            diagram_data["selected_nodes"] = [resolved]
            session_row["context"] = ctx
            await try_sync_voice_diagram_to_hub(voice_session_id)
            user_id = _session_user_id(voice_session_id)
            scope = _session_scope(voice_session_id)
            if user_id is not None and scope:
                await publish_kitty_selection_update(user_id, scope, [resolved])
        await send_kitty_ws_action(
            websocket,
            voice_session_id,
            {"type": "action", "action": "select_node", "params": {"node_id": resolved}},
        )
        return ToolDispatchResult(
            payload=ui_result_content(status="ok", action=action, extra={"node_id": resolved}),
            action=action,
        )

    ws_action = _ui_ws_action(action, command)
    if ws_action is None:
        return ToolDispatchResult(
            payload=ui_result_content(status="failed", action=action or "unknown", extra={"error_code": "not_parsed"}),
            action=action or "unknown",
        )
    await send_kitty_ws_action(websocket, voice_session_id, ws_action)
    await fanout_voice_command_from_session(voice_session_id, str(ws_action.get("action") or action))
    return ToolDispatchResult(
        payload=ui_result_content(status="ok", action=action),
        action=action,
    )


def _ui_ws_action(action: str, command: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Map leftover UI actions to a canvas WS payload."""
    if action in {"open_mindmate", "open_thinkguide"}:
        return {"type": "action", "action": "open_mindmate", "params": {}}
    if action in {"close_mindmate", "close_thinkguide"}:
        return {"type": "action", "action": "close_mindmate", "params": {}}
    if action == "open_panel":
        panel = str(command.get("target") or "").strip().lower()
        if panel in {"mindmate", "thinkguide"}:
            return {"type": "action", "action": "open_mindmate", "params": {}}
        if panel == "node_palette":
            return {"type": "action", "action": "open_node_palette", "params": {}}
        return None
    if action == "close_panel":
        panel = str(command.get("target") or "").strip().lower()
        if panel in {"mindmate", "thinkguide"}:
            return {"type": "action", "action": "close_mindmate", "params": {}}
        if panel == "node_palette":
            return {"type": "action", "action": "close_node_palette", "params": {}}
        return {"type": "action", "action": "close_all_panels", "params": {}}
    if action == "open_node_palette":
        return {"type": "action", "action": "open_node_palette", "params": {}}
    if action == "close_node_palette":
        return {"type": "action", "action": "close_node_palette", "params": {}}
    if action == "close_all_panels":
        return {"type": "action", "action": "close_all_panels", "params": {}}
    if action in {"ask_mindmate", "ask_thinkguide"}:
        message = command.get("target") or command.get("message")
        if isinstance(message, str) and message.strip():
            return {"type": "action", "action": "ask_mindmate", "params": {"message": message.strip()}}
        return None
    if action == "start_inline_recommendations":
        params: Dict[str, Any] = {}
        node_id = command.get("node_id")
        if isinstance(node_id, str) and node_id.strip():
            params["node_id"] = node_id.strip()
        return {"type": "action", "action": "start_inline_recommendations", "params": params}
    if action == "add_node_with_recommendations":
        params = {}
        seed = command.get("target")
        if isinstance(seed, str) and seed.strip():
            params["text"] = seed.strip()
        return {"type": "action", "action": "add_node_with_recommendations", "params": params}
    if action == "explain_node":
        params = {}
        node_id = command.get("node_id")
        if isinstance(node_id, str) and node_id.strip():
            params["node_id"] = node_id.strip()
        return {"type": "action", "action": "explain_node", "params": params}
    return None
