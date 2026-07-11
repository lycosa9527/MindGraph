"""Structural diagram update routing (verified Bus + legacy Bus / execute).

Callers pass the ``command_router`` module so unittest patches on
``services.kitty.routing.command_router.*`` still apply.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import copy
from types import ModuleType
from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.kitty.ack.ack_failure import render_failure_ack_for_command
from services.kitty.ack.ack_library import render_ack_for_command, render_low_confidence_ack
from services.kitty.ack.ack_slots import enrich_ack_session_context
from services.kitty.context.messaging import resolve_voice_interaction_language
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.routing.one_sentence_edit_helpers import (
    CLIENT_REPORTED_FAILURE_CODES,
    normalize_follow_up_actions,
    should_use_verified_diagram_edit,
    split_parallel_auto_complete_follow_ups,
)
from services.kitty.routing.pending_branch_autocomplete import (
    created_node_id_from_applied_ops,
)
from services.kitty.session.memory import get_session_memory
from services.kitty.session.runtime_state import logger, voice_sessions


async def execute_follow_up_actions(
    router: ModuleType,
    websocket: WebSocket,
    voice_session_id: str,
    follow_ups: list[Dict[str, Any]],
    *,
    session_context: Dict[str, Any],
    command_text: str,
    topic: str | None = None,
) -> None:
    """Run chained actions (e.g. auto_complete), optionally with a topic override."""
    if not follow_ups:
        return
    lang = resolve_voice_interaction_language(session_context)
    topic_text = topic.strip() if isinstance(topic, str) and topic.strip() else ""
    for follow in follow_ups:
        action = str(follow.get("action") or "").strip()
        if action == "auto_complete":
            logger.info("Triggering follow-up AI auto-complete from text/voice command")
            params: Dict[str, Any] = {}
            if topic_text:
                params["topic"] = topic_text
            await router.safe_websocket_send(
                websocket,
                {"type": "action", "action": "auto_complete", "params": params},
            )
            await router.fanout_voice_command_from_session(
                voice_session_id,
                "auto_complete",
                params=params or None,
            )
            await router.emit_user_ack(
                websocket,
                voice_session_id,
                router.render_ack("ui.auto_complete", lang=lang),
            )
            kitty_wf_log(
                "follow_up",
                f"auto_complete topic={topic_text or '—'}",
                voice_session_id=voice_session_id,
                action="auto_complete",
            )
            continue
        if action == "auto_complete_branch":
            target_raw = follow.get("target") or follow.get("node_label") or follow.get("text")
            target = str(target_raw).strip() if isinstance(target_raw, str) else ""
            node_id_raw = follow.get("node_id")
            node_id = str(node_id_raw).strip() if isinstance(node_id_raw, str) else ""
            if not target and not node_id:
                logger.warning("follow-up auto_complete_branch missing target/node_id")
                continue
            await router.emit_auto_complete_branch(
                websocket,
                voice_session_id,
                target,
                command_text=command_text,
                lang=lang,
                node_id=node_id or None,
            )
            kitty_wf_log(
                "follow_up",
                f"auto_complete_branch target={target or node_id}",
                voice_session_id=voice_session_id,
                action="auto_complete_branch",
            )
            continue
        logger.warning("Unsupported follow-up action skipped: %s", action)


async def route_structural_diagram_command(
    router: ModuleType,
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    *,
    action: Any,
    target: Any,
    node_index: Any,
    command_text: str,
    diagram_type: Any,
    user_id: Optional[int],
    live_session: Optional[Dict[str, Any]],
    is_text_message: bool,
    confidence: float,
    confidence_threshold: float,
) -> Any:
    """
    Handle update_center / add_node / update_node / delete_node.

    Returns a RouteResult (never None).
    """
    if confidence < confidence_threshold:
        logger.info(
            "VOIC | Low confidence (%.2f) for diagram update '%s', threshold=%.2f",
            confidence,
            action,
            confidence_threshold,
        )
        lang = resolve_voice_interaction_language(session_context)
        clarify_text = render_low_confidence_ack(
            command,
            lang=lang,
            session_context=session_context,
        )
        await router.send_diagram_failure_ack(
            websocket,
            voice_session_id,
            clarify_text,
            one_sentence_action=str(action) if action else None,
            one_sentence_outcome="low_confidence",
            one_sentence_user_text=command_text,
        )
        return router.finish_route(
            voice_session_id,
            router.RouteOutcome.FAILED,
            reason="low_confidence_diagram",
            action=str(action) if action else None,
        )

    live_voice = voice_sessions.get(voice_session_id)
    if isinstance(live_voice, dict):
        live_voice["last_diagram_command"] = copy.deepcopy(command)
    lang = resolve_voice_interaction_language(session_context)
    use_verified = should_use_verified_diagram_edit(
        session_context,
        live_voice if isinstance(live_voice, dict) else None,
        diagram_type,
        is_text_message=is_text_message,
    )
    scope_raw = None
    if isinstance(live_voice, dict):
        scope_raw = live_voice.get("diagram_session_id")
    scope = str(scope_raw).strip() if isinstance(scope_raw, str) else ""

    follow_up_actions = normalize_follow_up_actions(command)
    parallel_auto_complete, follow_up_actions = split_parallel_auto_complete_follow_ups(
        str(action),
        follow_up_actions,
        primary_command=command,
    )
    center_topic = ""
    if str(action) == "update_center":
        target_raw = command.get("target")
        if isinstance(target_raw, str) and target_raw.strip():
            center_topic = target_raw.strip()

    if use_verified and scope:
        progress_text = render_ack_for_command(
            str(action),
            command,
            enrich_ack_session_context(session_context, live_session),
            lang=lang,
            phase="progress",
        )
        if progress_text:
            await router.emit_user_ack(
                websocket,
                voice_session_id,
                progress_text,
                one_sentence_action=str(action) if action else None,
                one_sentence_outcome="pending",
                one_sentence_user_text=command_text,
                reply_kind="progress",
            )
        if parallel_auto_complete:
            await execute_follow_up_actions(
                router,
                websocket,
                voice_session_id,
                parallel_auto_complete,
                session_context=session_context,
                command_text=command_text,
                topic=center_topic or None,
            )
        bus_result = await router.apply_kitty_legacy_diagram_command(
            websocket,
            voice_session_id,
            command,
            session_context,
            scope=scope,
            diagram_type=str(diagram_type),
            user_id=user_id,
            verify_required=True,
        )
        tool_result = bus_result.tool_result
        if tool_result.status == "applied":
            kitty_wf_log(
                "diagram_execute",
                f"{action} verified target={target or node_index or '—'}",
                voice_session_id=voice_session_id,
                action=str(action),
            )
            ack_ctx = enrich_ack_session_context(session_context, live_session)
            if str(action) == "add_node":
                await router.maybe_start_background_branch_autocomplete(
                    websocket,
                    voice_session_id,
                    command,
                    ack_ctx,
                    command_text=command_text,
                    node_id=created_node_id_from_applied_ops(tool_result.applied_ops),
                )
            ack_text = render_ack_for_command(
                str(action),
                command,
                ack_ctx,
                lang=lang,
                phase="done",
            )
            await router.emit_user_ack(
                websocket,
                voice_session_id,
                ack_text,
                one_sentence_action=str(action) if action else None,
                one_sentence_outcome="executed",
                one_sentence_user_text=command_text,
            )
            memory = get_session_memory(voice_session_id)
            memory.append_action_turn(ack_text, action=str(action))
            await execute_follow_up_actions(
                router,
                websocket,
                voice_session_id,
                follow_up_actions,
                session_context=session_context,
                command_text=command_text,
                topic=center_topic or None,
            )
            return router.finish_route(
                voice_session_id,
                router.RouteOutcome.EXECUTED,
                action=str(action) if action else None,
            )
        err_code = tool_result.error_code or "verify_failed"
        if err_code not in CLIENT_REPORTED_FAILURE_CODES:
            fail_text = render_failure_ack_for_command(
                str(action),
                command,
                enrich_ack_session_context(session_context, live_session),
                error_code=err_code,
                lang=lang,
            )
            await router.send_diagram_failure_ack(
                websocket,
                voice_session_id,
                fail_text,
                one_sentence_action=str(action) if action else None,
                one_sentence_outcome="failed",
                one_sentence_user_text=command_text,
            )
        else:
            kitty_wf_log(
                "diagram_execute",
                f"{action} failed client-reported code={err_code}",
                voice_session_id=voice_session_id,
                action=str(action),
            )
        return router.finish_route(
            voice_session_id,
            router.RouteOutcome.FAILED,
            reason=str(err_code),
            action=str(action) if action else None,
        )

    legacy_scope = scope
    if not legacy_scope and isinstance(live_voice, dict):
        raw_scope = live_voice.get("diagram_session_id")
        legacy_scope = str(raw_scope).strip() if isinstance(raw_scope, str) else ""

    if legacy_scope:
        if parallel_auto_complete:
            await execute_follow_up_actions(
                router,
                websocket,
                voice_session_id,
                parallel_auto_complete,
                session_context=session_context,
                command_text=command_text,
                topic=center_topic or None,
            )
        bus_result = await router.apply_kitty_legacy_diagram_command(
            websocket,
            voice_session_id,
            command,
            session_context,
            scope=legacy_scope,
            diagram_type=str(diagram_type),
            user_id=user_id,
            verify_required=False,
        )
        executed = bus_result.tool_result.status == "applied"
        applied_ops = bus_result.tool_result.applied_ops
    else:
        executed = await router.execute_diagram_update(
            websocket,
            voice_session_id,
            action,
            command,
            session_context,
        )
        applied_ops = None

    if executed:
        kitty_wf_log(
            "diagram_execute",
            f"{action} ok target={target or node_index or '—'}",
            voice_session_id=voice_session_id,
            action=str(action),
        )
        ack_ctx = enrich_ack_session_context(session_context, live_session)
        if str(action) == "add_node":
            await router.maybe_start_background_branch_autocomplete(
                websocket,
                voice_session_id,
                command,
                ack_ctx,
                command_text=command_text,
                node_id=created_node_id_from_applied_ops(applied_ops),
            )
        ack_text = render_ack_for_command(
            str(action),
            command,
            ack_ctx,
            lang=lang,
            phase="done",
        )
        await router.emit_user_ack(
            websocket,
            voice_session_id,
            ack_text,
            one_sentence_action=str(action) if action else None,
            one_sentence_outcome="executed",
            one_sentence_user_text=command_text,
        )
        memory = get_session_memory(voice_session_id)
        memory.append_action_turn(ack_text, action=str(action))
        await execute_follow_up_actions(
            router,
            websocket,
            voice_session_id,
            follow_up_actions,
            session_context=session_context,
            command_text=command_text,
            topic=center_topic or None,
        )
        return router.finish_route(
            voice_session_id,
            router.RouteOutcome.EXECUTED,
            action=str(action) if action else None,
        )
    fail_text = render_failure_ack_for_command(
        str(action),
        command,
        enrich_ack_session_context(session_context, live_session),
        error_code="diagram_execute_failed",
        lang=lang,
    )
    await router.send_diagram_failure_ack(
        websocket,
        voice_session_id,
        fail_text,
        one_sentence_action=str(action) if action else None,
        one_sentence_outcome="failed",
        one_sentence_user_text=command_text,
    )
    return router.finish_route(
        voice_session_id,
        router.RouteOutcome.FAILED,
        reason="diagram_execute_failed",
        action=str(action) if action else None,
    )
