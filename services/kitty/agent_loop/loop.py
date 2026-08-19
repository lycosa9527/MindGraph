"""Typed-text observe-act loop (OpenAI-compatible messages + tool results).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import WebSocket

from services.diagram_edit.effects import refresh_session_diagram_data_from_evidence
from services.infrastructure.http.error_handler import (
    LLMServiceError,
    LLMTimeoutError,
    ThinkingCoinInsufficientError,
)
from services.kitty.ack.ack_emit import emit_user_ack
from services.kitty.ack.ack_library import render_not_understood_ack
from services.kitty.agent_loop.messages import (
    LoopMode,
    append_assistant_tool_calls,
    append_tool_message,
    build_initial_messages,
    extract_assistant_text,
    extract_tool_calls,
)
from services.kitty.agent_loop.results import (
    created_node_ids_from_payload,
    error_code_from_payload,
    summarize_payload_for_memory,
)
from services.kitty.agent_loop.tools import (
    dispatch_loop_tool,
    dispatch_prepared_command,
    ensure_live_mindmap_identity,
    loop_tool_schemas,
)
from services.kitty.context.library_refresh import (
    live_spec_newer_than_library,
    should_skip_library_refresh,
    throttled_refresh_voice_context_from_library,
)
from services.kitty.context.messaging import resolve_voice_interaction_language
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.redis.kitty_session_redis import (
    apply_redis_live_to_voice_session,
    load_kitty_live_context,
)
from services.kitty.routing.command_router import RouteOutcome, RouteResult
from services.kitty.routing.node_action_library import render_diagram_snapshot_block
from services.kitty.routing.one_sentence_edit_heuristics import heuristic_one_sentence_edit_command
from services.kitty.routing.one_sentence_edit_helpers import (
    is_mindmap_diagram_type,
    is_one_sentence_edit_mode,
)
from services.kitty.routing.pending_branch_autocomplete import try_consume_pending_branch_autocomplete
from services.kitty.routing.pending_clarify_options import (
    classify_clarify_option_pick,
    clear_pending_clarify_options,
    get_pending_clarify_options,
    try_consume_pending_clarify_options,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.ops import get_voice_session
from services.kitty.session.runtime_state import voice_sessions
from services.llm import llm_service
from services.utils.error_types import LLM_PIPELINE_ERRORS

AGENT_LOOP_MODEL = "qwen3.6-flash"
MAX_TOOL_ROUNDS = 5


def _finish(voice_session_id: str, outcome: RouteOutcome, *, reason: str = "", action: str = "") -> RouteResult:
    kitty_wf_log(
        "agent_loop",
        reason or outcome.value,
        voice_session_id=voice_session_id,
        action=action or None,
    )
    return RouteResult(outcome=outcome, reason=reason or None, action=action or None)


def _resolve_mode(session_context: Dict[str, Any], live_session: Optional[Dict[str, Any]]) -> LoopMode:
    if is_one_sentence_edit_mode(session_context, live_session):
        return "edit"
    return "general"


def _diagram_type(voice_session_id: str, session_context: Dict[str, Any]) -> str:
    session = voice_sessions.get(voice_session_id) or {}
    for raw in (session.get("diagram_type"), session_context.get("diagram_type")):
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return "circle_map"


def _session_user_ids(voice_session_id: str) -> tuple[Optional[int], Optional[int]]:
    session = voice_sessions.get(voice_session_id) or {}
    raw = session.get("user_id")
    user_id: Optional[int]
    try:
        user_id = int(raw) if raw is not None else None
    except (TypeError, ValueError):
        user_id = None
    return user_id, None


async def _refresh_live_context(voice_session_id: str, session_context: Dict[str, Any]) -> Dict[str, Any]:
    """Merge Redis live_spec / library into the voice session, then return context."""
    live_session = get_voice_session(voice_session_id)
    if not live_session:
        return session_context
    ws_diagram_id = live_session.get("diagram_session_id")
    if isinstance(ws_diagram_id, str) and ws_diagram_id.strip():
        live_payload = await load_kitty_live_context(ws_diagram_id.strip())
        if live_payload:
            apply_redis_live_to_voice_session(live_session, live_payload)
    context = dict(live_session.get("context") or session_context)
    user_id, _org = _session_user_ids(voice_session_id)
    lib_id = context.get("diagram_library_id")
    skip_refresh = should_skip_library_refresh(voice_session_id, force=True)
    if (
        not skip_refresh
        and user_id is not None
        and isinstance(ws_diagram_id, str)
        and ws_diagram_id.strip()
        and isinstance(lib_id, str)
        and lib_id.strip()
    ):
        live_newer = await live_spec_newer_than_library(user_id, lib_id.strip(), ws_diagram_id.strip())
        if not live_newer:
            await throttled_refresh_voice_context_from_library(
                user_id=user_id,
                voice_session_id=voice_session_id,
                diagram_session_id=ws_diagram_id.strip(),
                force=True,
            )
            context = dict(live_session.get("context") or context)
    return context


def _pending_clarify_note(session: Optional[Dict[str, Any]]) -> str:
    pending = get_pending_clarify_options(session)
    if pending is None:
        return ""
    question = pending.get("question")
    options = pending.get("options")
    parts: List[str] = []
    if isinstance(question, str) and question.strip():
        parts.append(question.strip())
    if isinstance(options, list):
        labels = [str(item) for item in options if isinstance(item, str) and item.strip()]
        if labels:
            parts.append(" / ".join(labels[:3]))
    return " | ".join(parts)


def _text_for_created_node(payload: Dict[str, Any], node_id: str) -> str:
    applied_ops = payload.get("applied_ops")
    if not isinstance(applied_ops, list):
        return ""
    for item in applied_ops:
        if not isinstance(item, dict) or item.get("node_id") != node_id:
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
    return ""


def _apply_evidence_to_context(session_context: Dict[str, Any], payload: Dict[str, Any]) -> None:
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        refresh_session_diagram_data_from_evidence(session_context, evidence)
        return
    created = created_node_ids_from_payload(payload)
    if not created:
        return
    diagram_data = session_context.get("diagram_data")
    if not isinstance(diagram_data, dict):
        return
    children = diagram_data.get("children")
    if not isinstance(children, list):
        children = []
        diagram_data["children"] = children
    nodes = diagram_data.get("nodes")
    if not isinstance(nodes, list):
        nodes = []
        diagram_data["nodes"] = nodes
    for node_id in created:
        text = _text_for_created_node(payload, node_id)
        if not any(isinstance(child, dict) and child.get("id") == node_id for child in children):
            child: Dict[str, Any] = {"id": node_id}
            if text:
                child["text"] = text
            children.append(child)
        if not any(isinstance(node, dict) and node.get("id") == node_id for node in nodes):
            node_row: Dict[str, Any] = {"id": node_id, "type": "branch"}
            if text:
                node_row["text"] = text
            nodes.append(node_row)


async def _last_resort_heuristic(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
    diagram_type: str,
    verify_required: bool,
) -> Optional[RouteResult]:
    heuristic = heuristic_one_sentence_edit_command(command_text)
    if heuristic is None:
        return None
    dispatched = await dispatch_prepared_command(
        websocket,
        voice_session_id,
        command=heuristic,
        session_context=session_context,
        diagram_type=diagram_type,
        command_text=command_text,
        verify_required=verify_required,
    )
    if dispatched.mutated or dispatched.action in {"auto_complete", "auto_complete_branch"}:
        return _finish(voice_session_id, RouteOutcome.EXECUTED, action=dispatched.action, reason="heuristic")
    return None


async def run_typed_agent_loop(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
) -> RouteResult:
    """Industry-standard tool loop for keyboard + Fun-ASR typed text."""
    text = command_text.strip()
    if not text:
        return _finish(voice_session_id, RouteOutcome.FAILED, reason="empty")

    pending_branch = await try_consume_pending_branch_autocomplete(
        websocket,
        voice_session_id,
        text,
        session_context,
    )
    if pending_branch:
        return _finish(voice_session_id, RouteOutcome.EXECUTED, action=pending_branch)

    picked = await try_consume_pending_clarify_options(
        websocket,
        voice_session_id,
        text,
        session_context,
    )
    live = voice_sessions.get(voice_session_id)
    live_dict = live if isinstance(live, dict) else None
    pending_note = ""
    if picked is None and live_dict is not None:
        pending = get_pending_clarify_options(live_dict)
        if pending is not None:
            option_commands = pending.get("option_commands")
            count = len(option_commands) if isinstance(option_commands, list) else 0
            if classify_clarify_option_pick(text, count) is None:
                pending_note = _pending_clarify_note(live_dict)
                clear_pending_clarify_options(live_dict)

    context = await _refresh_live_context(voice_session_id, session_context)
    ensure_live_mindmap_identity(context)
    if picked is not None:
        context = dict(live_dict.get("context") or context) if live_dict else context
        diagram_type = _diagram_type(voice_session_id, context)
        verify_required = is_mindmap_diagram_type(diagram_type)
        dispatched = await dispatch_prepared_command(
            websocket,
            voice_session_id,
            command=picked,
            session_context=context,
            diagram_type=diagram_type,
            command_text=text,
            verify_required=verify_required,
        )
        outcome = RouteOutcome.EXECUTED if dispatched.mutated or dispatched.action else RouteOutcome.FAILED
        if dispatched.payload.get("status") in {"failed", "rejected"}:
            outcome = RouteOutcome.FAILED
        return _finish(voice_session_id, outcome, action=dispatched.action, reason="clarify_pick")

    mode = _resolve_mode(context, live_dict)
    diagram_type = _diagram_type(voice_session_id, context)
    verify_required = is_mindmap_diagram_type(diagram_type)
    lang = resolve_voice_interaction_language(context)
    snapshot = render_diagram_snapshot_block(
        context,
        diagram_type=diagram_type,
        lang="en" if lang == "en" else "zh",
    )
    memory = get_session_memory(voice_session_id)
    messages = build_initial_messages(
        mode=mode,
        user_text=text,
        snapshot=snapshot,
        recent=memory.summarize_for_parser(5),
        lang=lang,
        pending_clarify_note=pending_note,
    )
    user_id, organization_id = _session_user_ids(voice_session_id)
    acted = False
    last_action = ""

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            result = await llm_service.chat_raw(
                messages=messages,
                model=AGENT_LOOP_MODEL,
                temperature=0.0,
                max_tokens=600,
                timeout=20.0,
                tools=loop_tool_schemas(),
                tool_choice="auto",
                user_id=user_id,
                organization_id=organization_id,
                request_type="kitty_agent_loop",
                diagram_type=diagram_type,
                session_id=voice_session_id,
                endpoint_path="/ws/kitty",
                use_knowledge_base=False,
            )
        except ThinkingCoinInsufficientError:
            ack = render_not_understood_ack(lang=lang)
            await emit_user_ack(
                websocket,
                voice_session_id,
                ack,
                one_sentence_action="none",
                one_sentence_outcome="failed",
                one_sentence_user_text=text,
            )
            return _finish(voice_session_id, RouteOutcome.FAILED, reason="thinking_coins")
        except (LLMTimeoutError, LLMServiceError, *LLM_PIPELINE_ERRORS):
            if mode == "edit":
                heuristic = await _last_resort_heuristic(
                    websocket,
                    voice_session_id,
                    text,
                    context,
                    diagram_type,
                    verify_required,
                )
                if heuristic is not None:
                    return heuristic
                ack = render_not_understood_ack(lang=lang)
                await emit_user_ack(
                    websocket,
                    voice_session_id,
                    ack,
                    one_sentence_action="none",
                    one_sentence_outcome="failed",
                    one_sentence_user_text=text,
                )
                return _finish(voice_session_id, RouteOutcome.FAILED, reason="llm_failed")
            return _finish(voice_session_id, RouteOutcome.CONVERSATIONAL_FALLBACK, reason="llm_failed")

        tool_calls = extract_tool_calls(result)
        if not tool_calls:
            reply = extract_assistant_text(result)
            if mode == "edit" and not acted:
                if pending_note:
                    ack = render_not_understood_ack(lang=lang)
                else:
                    heuristic = await _last_resort_heuristic(
                        websocket,
                        voice_session_id,
                        text,
                        context,
                        diagram_type,
                        verify_required,
                    )
                    if heuristic is not None:
                        return heuristic
                    ack = render_not_understood_ack(lang=lang)
                await emit_user_ack(
                    websocket,
                    voice_session_id,
                    ack,
                    one_sentence_action="none",
                    one_sentence_outcome="failed",
                    one_sentence_user_text=text,
                )
                return _finish(voice_session_id, RouteOutcome.FAILED, reason="edit_not_parsed")
            if acted:
                return _finish(voice_session_id, RouteOutcome.EXECUTED, action=last_action, reason="text_stop")
            if reply:
                await emit_user_ack(
                    websocket,
                    voice_session_id,
                    reply,
                    one_sentence_action=last_action or None,
                    one_sentence_user_text=text,
                )
                return _finish(voice_session_id, RouteOutcome.EXECUTED, action=last_action, reason="text_stop")
            return _finish(voice_session_id, RouteOutcome.CONVERSATIONAL_FALLBACK, reason="empty_text")

        append_assistant_tool_calls(messages, tool_calls)
        for call in tool_calls:
            dispatched = await dispatch_loop_tool(
                websocket,
                voice_session_id,
                name=str(call["name"]),
                arguments_json=str(call.get("arguments") or "{}"),
                session_context=context,
                diagram_type=diagram_type,
                command_text=text,
                verify_required=verify_required,
            )
            last_action = dispatched.action
            status = str(dispatched.payload.get("status") or "")
            if status in {"ok", "applied"}:
                acted = True
            if dispatched.mutated:
                _apply_evidence_to_context(context, dispatched.payload)
                live_row = voice_sessions.get(voice_session_id)
                if isinstance(live_row, dict):
                    live_row["context"] = context
            raw_revision = dispatched.payload.get("revision")
            revision = raw_revision if isinstance(raw_revision, int) else None
            memory.append_observation(
                summarize_payload_for_memory(dispatched.payload, action=dispatched.action),
                action=dispatched.action,
                revision=revision,
            )
            append_tool_message(messages, tool_call_id=str(call["id"]), payload=dispatched.payload)
            if dispatched.stop_clarify:
                return _finish(voice_session_id, RouteOutcome.EXECUTED, action="clarify_options")
            if dispatched.stop_after:
                return _finish(
                    voice_session_id,
                    RouteOutcome.EXECUTED,
                    action=dispatched.action,
                    reason="await_canvas",
                )
            if dispatched.stop_nonretryable:
                err = error_code_from_payload(dispatched.payload) or "failed"
                return _finish(voice_session_id, RouteOutcome.FAILED, reason=err, action=dispatched.action)

    if acted:
        return _finish(voice_session_id, RouteOutcome.EXECUTED, action=last_action, reason="step_cap")
    if mode == "edit":
        heuristic = await _last_resort_heuristic(
            websocket,
            voice_session_id,
            text,
            context,
            diagram_type,
            verify_required,
        )
        if heuristic is not None:
            return heuristic
        ack = render_not_understood_ack(lang=lang)
        await emit_user_ack(
            websocket,
            voice_session_id,
            ack,
            one_sentence_action="none",
            one_sentence_outcome="failed",
            one_sentence_user_text=text,
        )
        return _finish(voice_session_id, RouteOutcome.FAILED, reason="step_cap")
    return _finish(voice_session_id, RouteOutcome.FAILED, reason="step_cap")
