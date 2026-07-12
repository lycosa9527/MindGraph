"""Inbound JSON message handling for Kitty WebSocket.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import WebSocket

from models.domain.auth import User
from services.agent_hub import build_desktop_pairing_snapshot, get_mind_graph_agent_hub
from services.diagram_edit.ack import complete_mutation_ack_from_client
from services.kitty.audio.session_bridge import (
    feed_session_asr_audio,
    interrupt_kitty_tts,
    start_session_asr,
    stop_session_asr,
)
from services.kitty.context.hub_context import apply_kitty_ws_context_patch
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_outbound_type,
)
from services.kitty.infra.bootstrap.kitty_context_hydrate import (
    diagram_data_has_visible_content,
    merge_voice_context_with_library,
)
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.infra.desktop.kitty_desktop_wake_fanout import (
    kitty_llm_model_update_from_context,
    publish_kitty_llm_model_update,
    publish_kitty_selection_update,
)
from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.session.events import KittyEvent, get_session_event_bus
from services.kitty.session.ops import (
    get_agent_session_id,
    update_panel_context,
)
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.ws.guards import KITTY_WS_MAX_AUDIO_B64_CHARS, KITTY_WS_MAX_TEXT_CHARS

logger = logging.getLogger(__name__)

KittyInboundFlow = Literal["continue", "stop"]


@dataclass(slots=True)
class KittyWsInboundContext:
    """Per-connection state required to dispatch one client JSON message."""

    websocket: WebSocket
    current_user: User
    diagram_session_id: str
    voice_session_id: str
    hub_session_id: str
    hub: Any
    agent_session_id: str
    user_id: str


async def dispatch_kitty_ws_inbound_message(
    ctx: KittyWsInboundContext,
    message: dict,
) -> KittyInboundFlow:
    """
    Handle a single validated inbound JSON object from the Kitty client.

    Returns:
        ``continue`` to keep the receive loop running, ``stop`` when the client
        asked to end the conversation (``type: stop``).
    """
    websocket = ctx.websocket
    current_user = ctx.current_user
    diagram_session_id = ctx.diagram_session_id
    voice_session_id = ctx.voice_session_id
    hub_session_id = ctx.hub_session_id
    hub = ctx.hub

    msg_type = message.get("type")

    if msg_type == "audio":
        # Omni duplex retired; mic PCM uses asr_start / asr_audio / asr_stop (Fun-ASR).
        logger.debug("Ignoring legacy Omni audio frame on text-first Kitty session")
        return "continue"

    if msg_type == "asr_start":
        hints_raw = message.get("language_hints")
        language_hints: list[str] | None = None
        if isinstance(hints_raw, list):
            language_hints = [str(item) for item in hints_raw if str(item).strip()]
        elif str(message.get("language") or "").strip().lower().startswith("zh"):
            language_hints = ["zh"]
        utterance_raw = message.get("utterance_id")
        utterance_id = (
            str(utterance_raw).strip() if isinstance(utterance_raw, str) and str(utterance_raw).strip() else None
        )
        sess = voice_sessions.get(voice_session_id) or {}
        lane_raw = sess.get("_kitty_client_lane")
        lane = lane_raw if isinstance(lane_raw, str) and lane_raw.strip() else "—"
        debug_ctx = message.get("debug_ctx")
        ctx_label = str(debug_ctx) if debug_ctx is not None else "—"
        logger.info(
            "Kitty PTT asr_start sid=%s lane=%s hints=%s ctx=%s utt=%s",
            voice_session_id[:12],
            lane,
            language_hints or ["zh"],
            ctx_label,
            (utterance_id or "—")[:16],
        )
        kitty_wf_log(
            "asr_start",
            f"lane={lane} hints={language_hints or ['zh']} ctx={ctx_label} utt={utterance_id or '—'}",
            voice_session_id=voice_session_id,
        )
        await start_session_asr(
            websocket,
            voice_session_id,
            language_hints=language_hints,
            utterance_id=utterance_id,
        )
        return "continue"

    if msg_type == "asr_audio":
        audio_data = message.get("data")
        if isinstance(audio_data, str) and audio_data:
            if len(audio_data) > KITTY_WS_MAX_AUDIO_B64_CHARS:
                logger.warning(
                    "Kitty PTT asr_audio too large sid=%s chars=%d",
                    voice_session_id[:12],
                    len(audio_data),
                )
                await safe_websocket_send(
                    websocket,
                    {"type": "error", "error": "Audio frame too large"},
                )
                return "continue"
            utterance_raw = message.get("utterance_id")
            utterance_id = (
                str(utterance_raw).strip() if isinstance(utterance_raw, str) and str(utterance_raw).strip() else None
            )
            await feed_session_asr_audio(
                voice_session_id,
                audio_data,
                utterance_id=utterance_id,
            )
        return "continue"

    if msg_type == "asr_stop":
        sess = voice_sessions.get(voice_session_id) or {}
        lane_raw = sess.get("_kitty_client_lane")
        lane = lane_raw if isinstance(lane_raw, str) and lane_raw.strip() else "—"
        utterance_raw = message.get("utterance_id")
        utterance_id = (
            str(utterance_raw).strip() if isinstance(utterance_raw, str) and str(utterance_raw).strip() else None
        )
        logger.info(
            "Kitty PTT asr_stop sid=%s lane=%s utt=%s",
            voice_session_id[:12],
            lane,
            (utterance_id or "—")[:16],
        )
        kitty_wf_log(
            "asr_stop",
            f"lane={lane} client release utt={utterance_id or '—'}",
            voice_session_id=voice_session_id,
        )
        final_text = await stop_session_asr(voice_session_id, utterance_id=utterance_id)
        stopped_payload: dict[str, object] = {"type": "asr_stopped"}
        if utterance_id:
            stopped_payload["utterance_id"] = utterance_id
        if final_text:
            stopped_payload["text"] = final_text
        await safe_websocket_send(websocket, stopped_payload)
        await fanout_voice_phase_from_outbound_type(voice_session_id, "asr_stopped")
        return "continue"

    if msg_type == "tts_interrupt":
        await interrupt_kitty_tts(voice_session_id)
        await safe_websocket_send(websocket, {"type": "tts_interrupted"})
        return "continue"

    if msg_type == "tts_set_enabled":
        enabled = bool(message.get("enabled", True))
        voice_sessions[voice_session_id]["_kitty_tts_enabled"] = enabled
        await safe_websocket_send(
            websocket,
            {"type": "tts_enabled", "enabled": enabled},
        )
        return "continue"

    if msg_type == "text":
        await interrupt_kitty_tts(voice_session_id)
        await safe_websocket_send(websocket, {"type": "tts_interrupted"})
        text = message.get("text", "").strip()
        if len(text) > KITTY_WS_MAX_TEXT_CHARS:
            await safe_websocket_send(
                websocket,
                {"type": "error", "error": "Text too long"},
            )
            return "continue"
        if text:
            logger.debug("Received text message (%d chars)", len(text))
            kitty_wf_log(
                "text_inbound",
                text[:120],
                voice_session_id=voice_session_id,
            )
            voice_sessions[voice_session_id]["conversation_history"].append({"role": "user", "content": text})
            raw_request_id = message.get("request_id")
            request_id = (
                str(raw_request_id).strip() if isinstance(raw_request_id, str) and str(raw_request_id).strip() else None
            )
            if request_id:
                voice_sessions[voice_session_id]["_one_sentence_request_id"] = request_id
            bus = get_session_event_bus(voice_session_id)
            inbound_payload: dict[str, Any] = {"text": text}
            if request_id:
                inbound_payload["request_id"] = request_id
            await bus.emit(
                KittyEvent(
                    kind="text_inbound",
                    voice_session_id=voice_session_id,
                    payload=inbound_payload,
                )
            )
        return "continue"

    if msg_type == "get_desktop_session_snapshot":
        lane = voice_sessions[voice_session_id].get("_kitty_client_lane")
        snapshot_payload = await build_desktop_pairing_snapshot(
            int(current_user.id),
            diagram_session_id,
            client_lane=lane if isinstance(lane, str) else None,
        )
        await safe_websocket_send(
            websocket,
            {
                "type": "desktop_session_snapshot",
                "snapshot": snapshot_payload,
            },
        )
        return "continue"

    if msg_type == "context_update":
        new_context_in = message.get("context", {}) or {}
        cur_panel = voice_sessions[voice_session_id].get("active_panel", "none")
        active_panel = message.get("active_panel") or new_context_in.get("active_panel") or cur_panel or "none"
        session_dt = (
            voice_sessions[voice_session_id].get("diagram_type") or new_context_in.get("diagram_type") or "circle_map"
        )
        client_lane = voice_sessions[voice_session_id].get("_kitty_client_lane")
        delta_dd_raw = new_context_in.get("diagram_data")
        delta_dd: dict[str, Any] = delta_dd_raw if isinstance(delta_dd_raw, dict) else {}
        lib_raw = new_context_in.get("diagram_library_id")
        prefer_server = bool(
            client_lane == "mobile"
            and isinstance(lib_raw, str)
            and lib_raw.strip()
            and not diagram_data_has_visible_content(delta_dd)
        )
        merged_ctx, res_dt, res_panel = await merge_voice_context_with_library(
            current_user.id,
            new_context_in,
            diagram_type=session_dt,
            active_panel=active_panel,
            prefer_server_diagram_nodes=prefer_server,
        )
        new_diagram_type = res_dt

        old_diagram_type = voice_sessions[voice_session_id].get("diagram_type")
        voice_sessions[voice_session_id]["diagram_type"] = new_diagram_type
        if old_diagram_type != new_diagram_type:
            logger.info(
                "VOIC | Diagram type updated: %s -> %s for session %s",
                old_diagram_type,
                new_diagram_type,
                voice_session_id,
            )

        update_panel_context(voice_session_id, res_panel)
        voice_sessions[voice_session_id]["context"] = copy.deepcopy(merged_ctx)
        voice_sessions[voice_session_id]["context"]["diagram_type"] = new_diagram_type

        agent_session_id_mu = get_agent_session_id(voice_session_id)
        agent = kitty_agent_manager.get_or_create(agent_session_id_mu)
        diagram_data = dict(merged_ctx.get("diagram_data", {}))
        diagram_data["diagram_type"] = new_diagram_type
        agent.update_diagram_state(diagram_data)
        agent.update_panel_state(res_panel, merged_ctx.get("panels", {}))

        ctx_reason = "diagram_type_change" if old_diagram_type != new_diagram_type else "context_update"
        bus = get_session_event_bus(voice_session_id)
        await bus.emit(
            KittyEvent(
                kind="context_update",
                voice_session_id=voice_session_id,
                payload={"diagram_type": new_diagram_type, "reason": ctx_reason},
            )
        )

        hub_rev_raw = voice_sessions[voice_session_id].get("_hub_scope_revision")
        hub_rev = hub_rev_raw if isinstance(hub_rev_raw, int) else None
        client_rev_raw = message.get("expected_revision")
        if isinstance(client_rev_raw, int):
            hub_rev = client_rev_raw
        elif isinstance(client_rev_raw, (float, str)):
            try:
                hub_rev = int(client_rev_raw)
            except (TypeError, ValueError):
                pass
        idempotency_key_raw = message.get("idempotency_key")
        idempotency_key = (
            str(idempotency_key_raw).strip()
            if isinstance(idempotency_key_raw, str) and idempotency_key_raw.strip()
            else None
        )
        persist_library = message.get("persist_library") is True
        library_snapshot_raw = message.get("library_snapshot")
        library_snapshot = library_snapshot_raw if isinstance(library_snapshot_raw, dict) else None
        try:
            mutation_out = await apply_kitty_ws_context_patch(
                hub,
                hub_session_id=hub_session_id,
                diagram_scope=diagram_session_id,
                merged_context=merged_ctx,
                diagram_type=new_diagram_type,
                active_panel=res_panel,
                expected_revision=hub_rev,
                idempotency_key=idempotency_key,
                persist_library=persist_library,
                library_snapshot=library_snapshot,
            )
        except ValueError as mut_err:
            if "stale expected revision" in str(mut_err).lower():
                fresh_rev = get_mind_graph_agent_hub().get_binding_revision(hub_session_id)
                if fresh_rev is not None:
                    try:
                        mutation_out = await apply_kitty_ws_context_patch(
                            hub,
                            hub_session_id=hub_session_id,
                            diagram_scope=diagram_session_id,
                            merged_context=merged_ctx,
                            diagram_type=new_diagram_type,
                            active_panel=res_panel,
                            expected_revision=fresh_rev,
                            idempotency_key=(f"{idempotency_key}-retry" if idempotency_key else None),
                            persist_library=persist_library,
                            library_snapshot=library_snapshot,
                        )
                    except ValueError as retry_err:
                        logger.warning(
                            "Hub mutation retry rejected for %s: %s",
                            voice_session_id,
                            retry_err,
                        )
                        kitty_wf_log(
                            "hub_context_fail",
                            str(retry_err)[:120],
                            voice_session_id=voice_session_id,
                            scope=diagram_session_id,
                        )
                        await safe_websocket_send(
                            websocket,
                            {
                                "type": "context_mutation_ack",
                                "ok": False,
                                "error": str(retry_err),
                                "idempotency_key": idempotency_key,
                                "persist_library": persist_library,
                            },
                        )
                        return "continue"
                else:
                    logger.warning("Hub mutation rejected for %s: %s", voice_session_id, mut_err)
                    kitty_wf_log(
                        "hub_context_fail",
                        str(mut_err)[:120],
                        voice_session_id=voice_session_id,
                        scope=diagram_session_id,
                    )
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "context_mutation_ack",
                            "ok": False,
                            "error": str(mut_err),
                            "idempotency_key": idempotency_key,
                            "persist_library": persist_library,
                        },
                    )
                    return "continue"
            else:
                logger.warning("Hub mutation rejected for %s: %s", voice_session_id, mut_err)
                kitty_wf_log(
                    "hub_context_fail",
                    str(mut_err)[:120],
                    voice_session_id=voice_session_id,
                    scope=diagram_session_id,
                )
                await safe_websocket_send(
                    websocket,
                    {
                        "type": "context_mutation_ack",
                        "ok": False,
                        "error": str(mut_err),
                        "idempotency_key": idempotency_key,
                        "persist_library": persist_library,
                    },
                )
                return "continue"
        new_rev = mutation_out.get("revision")
        if isinstance(new_rev, int):
            voice_sessions[voice_session_id]["_hub_scope_revision"] = new_rev
        live_ts = mutation_out.get("live_spec_updated_at")
        if isinstance(live_ts, int) and live_ts > 0:
            voice_sessions[voice_session_id]["_kitty_redis_seen_ts"] = live_ts

        nodes_raw = diagram_data.get("nodes")
        nodes_count = len(nodes_raw) if isinstance(nodes_raw, list) else 0
        children_count = len(diagram_data.get("children", []))

        kitty_wf_log(
            "hub_context",
            f"ack ok rev={new_rev} persist={persist_library} nodes={nodes_count or children_count}",
            voice_session_id=voice_session_id,
            scope=diagram_session_id,
        )

        await safe_websocket_send(
            websocket,
            {
                "type": "context_mutation_ack",
                "ok": True,
                "revision": new_rev,
                "library_snapshot_saved": mutation_out.get("library_snapshot_saved"),
                "library_snapshot_error": mutation_out.get("library_snapshot_error"),
                "idempotency_key": idempotency_key,
                "persist_library": persist_library,
            },
        )

        logger.debug(
            "Context updated for %s with %d nodes",
            voice_session_id,
            nodes_count or children_count,
        )
        sel_raw = merged_ctx.get("selected_nodes")
        selected_nodes: list[str] = []
        if isinstance(sel_raw, list):
            for item in sel_raw:
                if isinstance(item, str) and item.strip():
                    selected_nodes.append(item.strip())
        if selected_nodes:
            await publish_kitty_selection_update(
                int(current_user.id),
                diagram_session_id,
                selected_nodes,
            )
        should_llm, llm_model = kitty_llm_model_update_from_context(merged_ctx)
        if should_llm:
            await publish_kitty_llm_model_update(
                int(current_user.id),
                diagram_session_id,
                llm_model,
            )
        return "continue"

    if msg_type == "diagram_mutation_ack":
        matched = complete_mutation_ack_from_client(message)
        kitty_wf_log(
            "diagram_ack",
            "matched" if matched else "orphan",
            voice_session_id=voice_session_id,
        )
        return "continue"

    if msg_type == "stop":
        return "stop"

    if msg_type == "cancel_response":
        logger.debug("User requested to cancel response (no Omni; CosyVoice interrupt separate)")
        await safe_websocket_send(websocket, {"type": "response_cancelled"})
        return "continue"

    if msg_type == "clear_audio_buffer":
        logger.debug("Ignoring clear_audio_buffer (Omni retired)")
        await safe_websocket_send(websocket, {"type": "audio_buffer_cleared"})
        return "continue"

    if msg_type == "commit_audio_buffer":
        logger.debug("Ignoring commit_audio_buffer (Omni retired)")
        await safe_websocket_send(websocket, {"type": "audio_buffer_committed"})
        return "continue"

    if msg_type == "append_image":
        await safe_websocket_send(
            websocket,
            {"type": "error", "error": "Image append requires Omni (retired)"},
        )
        return "continue"

    return "continue"


def build_kitty_inbound_context(
    *,
    websocket: WebSocket,
    current_user: User,
    diagram_session_id: str,
    voice_session_id: str,
    hub_session_id: str,
    hub: Any,
    agent_session_id: str,
    user_id: str,
) -> KittyWsInboundContext:
    """Factory for :class:`KittyWsInboundContext` (keyword-only for call-site clarity)."""

    return KittyWsInboundContext(
        websocket=websocket,
        current_user=current_user,
        diagram_session_id=diagram_session_id,
        voice_session_id=voice_session_id,
        hub_session_id=hub_session_id,
        hub=hub,
        agent_session_id=agent_session_id,
        user_id=user_id,
    )
