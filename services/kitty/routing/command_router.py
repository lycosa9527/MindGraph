"""Unified voice/text command router for Kitty diagram intents."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.kitty.diagram.review_annotate import compute_kitty_diagram_review_annotations
from services.kitty.session.agent_state import kitty_agent_manager

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

from services.kitty.content.paragraph import process_paragraph_with_qwen_plus
from services.kitty.context.library_refresh import (
    live_spec_newer_than_library,
    should_skip_library_refresh,
    throttled_refresh_voice_context_from_library,
)
from services.kitty.context.messaging import (
    safe_websocket_send,
    user_requests_diagram_pedagogical_review,
)
from services.kitty.diagram.diagram_execute import execute_diagram_update
from services.kitty.diagram.diagram_utils import (
    NODE_TARGET_ACTIONS,
    is_paragraph_text,
    resolve_voice_node_reference,
)
from services.kitty.diagram.hub_bridge import try_sync_voice_diagram_to_hub
from services.kitty.infra.bootstrap.kitty_diagram_vocabulary import normalize_voice_desktop_canvas_diagram_type
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.desktop.kitty_desktop_action_queue import enqueue_kitty_desktop_action
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    publish_kitty_desktop_action_pending,
    publish_kitty_selection_update,
)
from services.kitty.infra.desktop.kitty_voice_command_fanout import fanout_voice_command_from_session
from services.kitty.infra.redis.kitty_session_redis import (
    apply_redis_live_to_voice_session,
    load_kitty_live_context,
)
from services.kitty.omni.context_refresh import schedule_omni_context_refresh
from services.kitty.omni.tools import omni_function_call_to_command, parse_node_index_from_identifier
from services.kitty.routing.intent_parser import parse_voice_intent_with_tools
from services.kitty.session.memory import get_session_memory
from services.kitty.session.omni_client_access import get_session_omni_client
from services.kitty.session.ops import (
    get_agent_session_id,
    get_voice_session,
)
from services.kitty.session.runtime_state import logger, voice_sessions

VOICE_COMMAND_CONFIDENCE_TEXT = 0.5
VOICE_COMMAND_CONFIDENCE_VOICE = 0.5


class RouteOutcome(str, Enum):
    """RouteOutcome helper."""
    EXECUTED = "executed"
    CONVERSATIONAL_FALLBACK = "conversational_fallback"
    FAILED = "failed"


@dataclass(slots=True)
class RouteResult:
    """RouteResult helper."""
    outcome: RouteOutcome
    reason: Optional[str] = None


def _finish_route(
    voice_session_id: str,
    outcome: RouteOutcome,
    *,
    reason: Optional[str] = None,
    action: Optional[str] = None,
) -> RouteResult:
    """Finish route."""
    detail = reason or outcome.value
    if action and str(action) not in ("none", ""):
        detail = f"{action} → {detail}"
    kitty_wf_log(
        "route_outcome",
        detail,
        voice_session_id=voice_session_id,
        action=str(action) if action else None,
    )
    return RouteResult(outcome=outcome, reason=reason)


async def _send_diagram_failure_ack(voice_session_id: str, message: str) -> None:
    """Send diagram failure ack."""
    omni_client = get_session_omni_client(voice_session_id)
    if omni_client:
        try:
            await omni_client.create_response(instructions=message)
        except (RuntimeError, ConnectionError, AttributeError) as exc:
            logger.debug("Diagram failure ack skipped: %s", exc)


def _normalize_open_panel_action(command: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize open panel action."""
    action = command.get("action")
    if action != "open_panel":
        return command
    panel = command.get("target") or command.get("panel_name")
    panel_map = {
        "thinkguide": "open_mindmate",
        "mindmate": "open_mindmate",
        "node_palette": "open_node_palette",
        "palette": "open_node_palette",
    }
    if isinstance(panel, str):
        mapped = panel_map.get(panel.lower())
        if mapped:
            command = dict(command)
            command["action"] = mapped
    return command


def _normalize_close_panel_action(command: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize close panel action."""
    action = command.get("action")
    if action != "close_panel":
        return command
    panel = command.get("target") or command.get("panel_name") or "all"
    if str(panel).lower() == "all":
        command = dict(command)
        command["action"] = "close_all_panels"
        return command
    panel_map = {
        "thinkguide": "close_mindmate",
        "mindmate": "close_mindmate",
        "node_palette": "close_node_palette",
    }
    if isinstance(panel, str):
        mapped = panel_map.get(panel.lower())
        if mapped:
            command = dict(command)
            command["action"] = mapped
    return command


def _resolve_node_index(command: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve node index."""
    if command.get("node_index") is not None:
        return command
    ident = command.get("node_identifier")
    action = command.get("action")
    if ident is None and action in NODE_TARGET_ACTIONS:
        ident = command.get("target")
    idx = parse_node_index_from_identifier(ident if isinstance(ident, str) else None)
    if idx is not None:
        out = dict(command)
        out["node_index"] = idx
        return out
    return command


def _diagram_type_for_session(
    voice_session_id: str,
    session_context: Dict[str, Any],
) -> str:
    """Diagram type for session."""
    diagram_type = None
    if voice_session_id in voice_sessions:
        diagram_type = voice_sessions[voice_session_id].get("diagram_type")
    if not diagram_type:
        diagram_type = session_context.get("diagram_type")
    return str(diagram_type or "circle_map")


def _resolve_command_node(
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    *,
    prefer_selected: bool = True,
) -> Optional[Dict[str, Any]]:
    """Resolve command node."""
    diagram_type = _diagram_type_for_session(voice_session_id, session_context)
    node_identifier = command.get("node_identifier")
    ident_str = node_identifier if isinstance(node_identifier, str) else None
    node_index = command.get("node_index")
    idx_val = node_index if isinstance(node_index, int) else None
    node_id = command.get("node_id")
    id_str = node_id if isinstance(node_id, str) else None
    return resolve_voice_node_reference(
        session_context,
        diagram_type,
        node_id=id_str,
        node_index=idx_val,
        node_identifier=ident_str,
        prefer_selected=prefer_selected,
    )


def _sync_agent_diagram_from_session(
    voice_session_id: str,
    session_context: Dict[str, Any],
    diagram_type: str,
) -> None:
    """Keep LangGraph parser state aligned with the latest canvas context."""
    agent_session_id = get_agent_session_id(voice_session_id)
    agent = kitty_agent_manager.get_or_create(agent_session_id)
    diagram_data = dict(session_context.get("diagram_data") or {})
    diagram_data["diagram_type"] = diagram_type
    agent.update_diagram_state(diagram_data)
    active_panel = None
    if voice_session_id in voice_sessions:
        active_panel = voice_sessions[voice_session_id].get("active_panel")
    if active_panel is None:
        active_panel = session_context.get("active_panel", "none")
    panels = session_context.get("panels")
    if isinstance(panels, dict):
        agent.update_panel_state(str(active_panel), panels)


async def route_voice_command(
    websocket: WebSocket,
    voice_session_id: str,
    command_text: str,
    session_context: Dict[str, Any],
    *,
    is_text_message: bool = False,
    from_voice: bool = False,
    pre_parsed_command: Optional[Dict[str, Any]] = None,
) -> RouteResult:
    """
    Single entry for voice transcription and typed text command routing.

    Returns RouteResult indicating executed, conversational fallback, or failure.
    """
    try:
        live_session = get_voice_session(voice_session_id)
        if live_session:
            ws_diagram_id = live_session.get("diagram_session_id")
            if isinstance(ws_diagram_id, str) and ws_diagram_id.strip():
                live_payload = await load_kitty_live_context(ws_diagram_id.strip())
                if live_payload:
                    apply_redis_live_to_voice_session(live_session, live_payload)
            session_context = dict(live_session.get("context") or session_context)

            refresh_uid = None
            uid_raw = live_session.get("user_id")
            if uid_raw is not None:
                try:
                    refresh_uid = int(uid_raw) if isinstance(uid_raw, str) else int(uid_raw)
                except (ValueError, TypeError):
                    refresh_uid = None
            ws_scope = live_session.get("diagram_session_id")
            ctx0 = dict(live_session.get("context") or {})
            lib_id = ctx0.get("diagram_library_id")
            skip_refresh = should_skip_library_refresh(
                voice_session_id,
                force=bool(is_text_message),
            )
            if skip_refresh:
                kitty_wf_log(
                    "library_refresh",
                    "skipped (fresh voice context)",
                    voice_session_id=voice_session_id,
                )
            if (
                not skip_refresh
                and refresh_uid is not None
                and isinstance(ws_scope, str)
                and ws_scope.strip()
                and isinstance(lib_id, str)
                and lib_id.strip()
            ):
                live_newer = await live_spec_newer_than_library(
                    refresh_uid,
                    lib_id.strip(),
                    ws_scope.strip(),
                )
                if not live_newer:
                    await throttled_refresh_voice_context_from_library(
                        user_id=refresh_uid,
                        voice_session_id=voice_session_id,
                        diagram_session_id=ws_scope.strip(),
                        force=bool(is_text_message),
                    )
                    kitty_wf_log(
                        "library_refresh",
                        "merged library into voice session",
                        voice_session_id=voice_session_id,
                        scope=ws_scope.strip(),
                    )
                    session_context = dict(live_session.get("context") or session_context)

        if user_requests_diagram_pedagogical_review(command_text):
            try:
                await schedule_omni_context_refresh(
                    voice_session_id,
                    reason="pedagogical_review",
                )
            except (RuntimeError, ConnectionError, AttributeError, ValueError) as hydrate_exc:
                logger.debug("[Kitty] diagram review instruction refresh skipped: %s", hydrate_exc)

        # CRITICAL: Check if input is a paragraph (long text for processing)
        # Common case: Teachers paste whole paragraphs expecting diagram generation
        if is_paragraph_text(command_text):
            logger.info(
                "Detected paragraph input (length: %d), processing with Qwen Plus",
                len(command_text),
            )
            executed = await process_paragraph_with_qwen_plus(
                websocket, voice_session_id, command_text, session_context
            )
            if executed:
                return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action="paragraph")
            return _finish_route(
                voice_session_id,
                RouteOutcome.FAILED,
                reason="paragraph_processing_failed",
                action="paragraph",
            )

        session = live_session or get_voice_session(voice_session_id)
        user_id = None
        organization_id = None
        if session:
            user_id_str = session.get("user_id")
            # Convert user_id to int if it's a string (voice_sessions stores as string)
            if user_id_str:
                try:
                    user_id = int(user_id_str) if isinstance(user_id_str, str) else user_id_str
                    # Get organization_id from user if available (use cache)
                    if redis_user_cache:
                        try:
                            user = await redis_user_cache.get_by_id(user_id)
                            if user:
                                organization_id = user.organization_id
                        except (AttributeError, KeyError) as e:
                            logger.debug(
                                "Error getting organization_id for token tracking: %s",
                                e,
                            )
                except (ValueError, TypeError) as e:
                    logger.debug("Error converting user_id for token tracking: %s", e)

        # CRITICAL: Get diagram_type directly from voice_sessions (source of truth)
        # session_context may be stale when diagram type changes
        # Always check voice_sessions first, then fallback to session_context
        diagram_type = None
        if voice_session_id in voice_sessions:
            diagram_type = voice_sessions[voice_session_id].get("diagram_type")
        if not diagram_type and session:
            diagram_type = session.get("diagram_type")
        if not diagram_type:
            diagram_type = session_context.get("diagram_type")

        if not diagram_type:
            logger.warning("VOIC | Could not determine diagram_type for voice command, defaulting to circle_map")
            diagram_type = "circle_map"

        logger.debug("VOIC | Using diagram_type=%s for voice command processing", diagram_type)

        _sync_agent_diagram_from_session(voice_session_id, session_context, str(diagram_type))

        if user_requests_diagram_pedagogical_review(command_text):
            try:
                annotations = await compute_kitty_diagram_review_annotations(
                    command_text,
                    diagram_type=str(diagram_type),
                    diagram_data=dict(session_context.get("diagram_data") or {}),
                    user_id=user_id,
                    organization_id=organization_id,
                    voice_session_id=voice_session_id,
                )
                if annotations.get("items") or str(annotations.get("summary") or "").strip():
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "diagram_review_annotation",
                            "summary": annotations.get("summary", ""),
                            "items": annotations.get("items", []),
                        },
                    )
            except (RuntimeError, ConnectionError, AttributeError, ValueError, TypeError) as ann_exc:
                logger.debug("[Kitty] diagram review annotations skipped: %s", ann_exc)

        if pre_parsed_command is not None:
            command = dict(pre_parsed_command)
        elif from_voice:
            return _finish_route(
                voice_session_id,
                RouteOutcome.CONVERSATIONAL_FALLBACK,
                reason="from_voice_no_preparse",
            )
        else:
            command = await parse_voice_intent_with_tools(
                command_text,
                voice_session_id=voice_session_id,
                diagram_type=str(diagram_type),
                user_id=user_id,
                organization_id=organization_id,
            )

        command = _normalize_open_panel_action(command)
        command = _normalize_close_panel_action(command)
        command = _resolve_node_index(command)

        action = command.get("action")
        target = command.get("target")
        node_index = command.get("node_index")
        confidence = command.get("confidence", 0.0)

        logger.info(
            "VOIC | Routed command action=%s target=%s node_index=%s confidence=%.2f text=%s voice=%s",
            action,
            target,
            node_index,
            confidence,
            is_text_message,
            from_voice,
        )

        route_detail = command_text.strip()[:120] if command_text.strip() else f"tool:{action}"
        if target:
            route_detail = f"{route_detail} → {str(target)[:48]}"
        kitty_wf_log(
            "route",
            route_detail,
            voice_session_id=voice_session_id,
            action=str(action) if action else None,
            extra={"confidence": confidence, "from_voice": from_voice},
        )

        confidence_threshold = VOICE_COMMAND_CONFIDENCE_TEXT if is_text_message else VOICE_COMMAND_CONFIDENCE_VOICE

        ui_actions = [
            "open_thinkguide",
            "close_thinkguide",
            "open_node_palette",
            "close_node_palette",
            "open_mindmate",
            "close_mindmate",
            "close_all_panels",
            "select_node",
            "explain_node",
            "ask_thinkguide",
            "ask_mindmate",
            "auto_complete",
            "start_inline_recommendations",
            "add_node_with_recommendations",
            "help",
            "open_desktop_canvas",
        ]

        # Check if this is a diagram update action
        diagram_update_actions = [
            "update_center",
            "update_node",
            "add_node",
            "delete_node",
        ]
        if action in diagram_update_actions:
            if confidence >= confidence_threshold:
                executed = await execute_diagram_update(websocket, voice_session_id, action, command, session_context)
                if executed:
                    kitty_wf_log(
                        "diagram_execute",
                        f"{action} ok target={target or node_index or '—'}",
                        voice_session_id=voice_session_id,
                        action=str(action),
                    )
                    memory = get_session_memory(voice_session_id)
                    memory.append_action_turn(
                        f"{action}: {target or node_index or ''}".strip(),
                        action=str(action),
                    )
                    return _finish_route(
                        voice_session_id,
                        RouteOutcome.EXECUTED,
                        action=str(action) if action else None,
                    )
                await _send_diagram_failure_ack(
                    voice_session_id,
                    "抱歉，我没能更新这张导图，请换个说法再试一次。",
                )
                return _finish_route(
                    voice_session_id,
                    RouteOutcome.FAILED,
                    reason="diagram_execute_failed",
                    action=str(action) if action else None,
                )
            logger.info(
                "VOIC | Low confidence (%.2f) for diagram update '%s', threshold=%.2f",
                confidence,
                action,
                confidence_threshold,
            )
            await _send_diagram_failure_ack(
                voice_session_id,
                "我不太确定要怎么改这张导图，请再说具体一点。",
            )
            return _finish_route(
                voice_session_id,
                RouteOutcome.FAILED,
                reason="low_confidence_diagram",
                action=str(action) if action else None,
            )

        # For non-diagram-update actions, check confidence
        if action not in ui_actions and confidence < confidence_threshold:
            logger.debug(
                "Low confidence (%s), conversational fallback",
                confidence,
            )
            return _finish_route(
                voice_session_id,
                RouteOutcome.CONVERSATIONAL_FALLBACK,
                action=str(action) if action else None,
            )

        # Handle UI actions first
        if action == "open_thinkguide":
            # Redirect to MindMate
            logger.debug("Opening MindMate panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "open_mindmate", "params": {}})
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "close_thinkguide":
            # Redirect to MindMate
            logger.debug("Closing MindMate panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "close_mindmate", "params": {}})
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "open_node_palette":
            logger.debug("Opening Node Palette")
            await safe_websocket_send(
                websocket,
                {"type": "action", "action": "open_node_palette", "params": {}},
            )
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "close_node_palette":
            logger.debug("Closing Node Palette")
            await safe_websocket_send(
                websocket,
                {"type": "action", "action": "close_node_palette", "params": {}},
            )
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "open_mindmate":
            logger.debug("Opening MindMate AI panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "open_mindmate", "params": {}})
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "close_mindmate":
            logger.debug("Closing MindMate AI panel")
            await safe_websocket_send(websocket, {"type": "action", "action": "close_mindmate", "params": {}})
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "close_all_panels":
            logger.debug("Closing all panels")
            await safe_websocket_send(
                websocket,
                {"type": "action", "action": "close_all_panels", "params": {}},
            )
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        # Interaction control
        if action == "auto_complete":
            logger.info("Triggering AI auto-complete from text/voice command")
            await safe_websocket_send(websocket, {"type": "action", "action": "auto_complete", "params": {}})
            await fanout_voice_command_from_session(voice_session_id, "auto_complete")
            # Send acknowledgment message to user via Omni
            try:
                # Create a response acknowledging the action
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.create_response(instructions="收到，正在自动补全。")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Could not send acknowledgment to Omni: %s", e)
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "start_inline_recommendations":
            logger.info("Kitty: start inline recommendations action")
            resolved = _resolve_command_node(
                voice_session_id,
                command,
                session_context,
                prefer_selected=True,
            )
            inline_rec_params: Dict[str, Any] = {}
            if resolved and resolved.get("node_id"):
                inline_rec_params["node_id"] = resolved["node_id"]
                if resolved.get("node_index") is not None:
                    inline_rec_params["node_index"] = resolved["node_index"]
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "start_inline_recommendations",
                    "params": inline_rec_params,
                },
            )
            await fanout_voice_command_from_session(
                voice_session_id,
                "start_inline_recommendations",
                params=inline_rec_params,
            )
            try:
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    if inline_rec_params.get("node_id"):
                        await omni_client.create_response(instructions="好，打开联想建议。")
                    else:
                        await omni_client.create_response(instructions="请先在画布上选中一个节点，再说要推荐的内容。")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Could not send acknowledgment to Omni: %s", e)
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "add_node_with_recommendations":
            logger.info("Kitty: add node with inline recommendations")
            add_node_params: Dict[str, Any] = {}
            seed = command.get("target")
            if isinstance(seed, str) and seed.strip():
                add_node_params["text"] = seed.strip()
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "add_node_with_recommendations",
                    "params": add_node_params,
                },
            )
            await fanout_voice_command_from_session(
                voice_session_id,
                "add_node_with_recommendations",
                params=add_node_params,
            )
            try:
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.create_response(instructions="好，已添加节点，请从推荐里选一个。")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Could not send acknowledgment to Omni: %s", e)
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "ask_thinkguide" and target:
            # Redirect to MindMate
            logger.debug("Sending question to MindMate: %s", target)
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "ask_mindmate",
                    "params": {"message": target},
                },
            )
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "ask_mindmate" and target:
            logger.debug("Sending question to MindMate: %s", target)
            await safe_websocket_send(
                websocket,
                {
                    "type": "action",
                    "action": "ask_mindmate",
                    "params": {"message": target},
                },
            )
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "select_node":
            resolved = _resolve_command_node(
                voice_session_id,
                command,
                session_context,
                prefer_selected=False,
            )
            if resolved and resolved.get("node_id"):
                resolved_node_id = str(resolved["node_id"])
                resolved_index = resolved.get("node_index")
                logger.debug("Selecting node: %s", resolved_node_id)
                session_row = voice_sessions.get(voice_session_id)
                if session_row is not None:
                    ctx = copy.deepcopy(session_row.get("context") or {})
                    ctx["selected_nodes"] = [resolved_node_id]
                    diagram_data = ctx.get("diagram_data")
                    if not isinstance(diagram_data, dict):
                        diagram_data = {}
                        ctx["diagram_data"] = diagram_data
                    diagram_data["selected_nodes"] = [resolved_node_id]
                    session_row["context"] = ctx
                    await try_sync_voice_diagram_to_hub(voice_session_id)
                    user_id_raw = session_row.get("user_id")
                    diagram_scope = session_row.get("diagram_session_id")
                    if user_id_raw is not None and isinstance(diagram_scope, str) and diagram_scope.strip():
                        try:
                            await publish_kitty_selection_update(
                                int(user_id_raw),
                                diagram_scope.strip(),
                                [resolved_node_id],
                            )
                        except (TypeError, ValueError) as sel_exc:
                            logger.debug(
                                "select_node selection fanout skipped for %s: %s",
                                voice_session_id,
                                sel_exc,
                            )
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "action",
                            "action": "select_node",
                            "params": {
                                "node_id": resolved_node_id,
                                "node_index": resolved_index,
                            },
                        },
                    )
                    return _finish_route(
                        voice_session_id,
                        RouteOutcome.EXECUTED,
                        action=str(action) if action else None,
                    )
                return _finish_route(
                    voice_session_id,
                    RouteOutcome.FAILED,
                    reason="select_node_session_missing",
                    action=str(action) if action else None,
                )
            return _finish_route(
                voice_session_id,
                RouteOutcome.FAILED,
                reason="select_node_unresolved",
                action=str(action) if action else None,
            )

        if action == "explain_node":
            resolved = _resolve_command_node(
                voice_session_id,
                command,
                session_context,
                prefer_selected=True,
            )
            if resolved and resolved.get("node_id"):
                resolved_node_id = str(resolved["node_id"])
                node_label = str(resolved.get("node_label") or target or "").strip()
                if not node_label and isinstance(resolved.get("node_index"), int):
                    nodes = session_context.get("diagram_data", {}).get("children", [])
                    idx = int(resolved["node_index"])
                    if 0 <= idx < len(nodes):
                        node = nodes[idx]
                        if isinstance(node, dict):
                            node_label = str(node.get("text", node.get("label", ""))).strip()
                if node_label:
                    logger.debug("Explaining node: %s (%s)", resolved_node_id, node_label)
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "action",
                            "action": "explain_node",
                            "params": {
                                "node_id": resolved_node_id,
                                "node_label": node_label,
                                "prompt": f'请解释一下"{node_label}"这个概念，用简单的语言，适合K12学生理解。',
                            },
                        },
                    )
                    await fanout_voice_command_from_session(
                        voice_session_id,
                        "explain_node",
                        params={"node_label": node_label, "node_id": resolved_node_id},
                    )
                    return _finish_route(
                        voice_session_id,
                        RouteOutcome.EXECUTED,
                        action=str(action) if action else None,
                    )
            return _finish_route(
                voice_session_id,
                RouteOutcome.FAILED,
                reason="explain_node_unresolved",
                action=str(action) if action else None,
            )

        if action == "open_desktop_canvas":
            if user_id is None:
                logger.warning("Kitty open_desktop_canvas: missing user_id")
                return _finish_route(
                    voice_session_id,
                    RouteOutcome.CONVERSATIONAL_FALLBACK,
                    action=str(action) if action else None,
                )
            raw_slug = command.get("diagram_type")
            slug = normalize_voice_desktop_canvas_diagram_type(raw_slug if isinstance(raw_slug, str) else None)
            if slug is None:
                logger.info("Kitty open_desktop_canvas: rejected diagram_type=%s", raw_slug)
                return _finish_route(
                    voice_session_id,
                    RouteOutcome.CONVERSATIONAL_FALLBACK,
                    action=str(action) if action else None,
                )

            payload: Dict[str, Any] = {
                "kind": "open_canvas",
                "diagram_type": slug,
            }
            targ = command.get("target")
            if isinstance(targ, str) and targ.strip():
                payload["topic"] = targ.strip()
            left_val = command.get("left")
            if isinstance(left_val, str) and left_val.strip():
                payload["left"] = left_val.strip()
            right_val = command.get("right")
            if isinstance(right_val, str) and right_val.strip():
                payload["right"] = right_val.strip()

            ok = await enqueue_kitty_desktop_action(user_id, payload)
            if ok:
                await publish_kitty_desktop_action_pending(user_id)
            try:
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    ack = "好，已在电脑端打开画布。" if ok else "电脑端暂时打不开画布，请稍后重试。"
                    await omni_client.create_response(instructions=ack)
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("open_desktop_canvas Omni ack skipped: %s", e)
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "help":
            logger.debug("User requested help - opening MindMate")
            await safe_websocket_send(websocket, {"type": "action", "action": "open_mindmate", "params": {}})
            return _finish_route(voice_session_id, RouteOutcome.EXECUTED, action=str(action) if action else None)

        if action == "none":
            logger.debug("No command detected - should send to Omni for conversational response")
            return _finish_route(
                voice_session_id,
                RouteOutcome.CONVERSATIONAL_FALLBACK,
                action=str(action) if action else None,
            )

        # Unknown action - send to Omni
        return _finish_route(
            voice_session_id,
            RouteOutcome.CONVERSATIONAL_FALLBACK,
            action=str(action) if action else None,
        )

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Command processing error: %s", e, exc_info=True)
        return _finish_route(
            voice_session_id,
            RouteOutcome.CONVERSATIONAL_FALLBACK,
            reason=str(e),
        )


async def route_omni_function_call(
    websocket: WebSocket,
    voice_session_id: str,
    function_name: str,
    arguments_json: str,
    session_context: Dict[str, Any],
) -> RouteResult:
    """Execute a diagram/UI command from an Omni native tool call."""
    command = omni_function_call_to_command(function_name, arguments_json)
    return await route_voice_command(
        websocket,
        voice_session_id,
        "",
        session_context,
        is_text_message=False,
        from_voice=True,
        pre_parsed_command=command,
    )
