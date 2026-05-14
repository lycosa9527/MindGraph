"""Inbound JSON message handling for Kitty WebSocket (shared by direct loop and Pipecat path)."""

from __future__ import annotations

import copy
import logging
import random
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import WebSocket

from models.domain.auth import User
from services.features.voice_agent import kitty_agent_manager
from services.kitty.kitty_context_hydrate import merge_voice_context_with_library
from services.kitty_voice.hub_context import apply_kitty_ws_context_patch
from services.kitty_voice.messaging import build_voice_instructions, safe_websocket_send
from services.kitty_voice.runtime_state import voice_sessions
from routers.features.voice.commands import process_voice_command
from routers.features.voice.kitty_library_context_refresh import (
    throttled_refresh_voice_context_from_library,
)
from services.kitty_voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
    update_panel_context,
)
from services.kitty_voice.ws_append_image import kitty_ws_handle_append_image
from services.kitty_voice.ws_guards import KITTY_WS_MAX_AUDIO_B64_CHARS, KITTY_WS_MAX_TEXT_CHARS

from services.agent_hub import build_desktop_pairing_snapshot

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
        audio_data = message.get("data")
        if audio_data:
            if not isinstance(audio_data, str) or len(audio_data) > KITTY_WS_MAX_AUDIO_B64_CHARS:
                await safe_websocket_send(
                    websocket,
                    {"type": "error", "error": "Audio frame too large"},
                )
                return "continue"
            if random.random() < 0.05:
                logger.debug(
                    "Forwarding audio to Omni: %d bytes (base64)",
                    len(audio_data),
                )
            omni_client = get_session_omni_client(voice_session_id)
            if omni_client:
                await throttled_refresh_voice_context_from_library(
                    user_id=int(current_user.id),
                    voice_session_id=voice_session_id,
                    diagram_session_id=diagram_session_id,
                )
                await omni_client.send_audio(audio_data)
            else:
                logger.warning(
                    "Cannot send audio: OmniClient not found for session %s",
                    voice_session_id,
                )
        return "continue"

    if msg_type == "text":
        text = message.get("text", "").strip()
        if len(text) > KITTY_WS_MAX_TEXT_CHARS:
            await safe_websocket_send(
                websocket,
                {"type": "error", "error": "Text too long"},
            )
            return "continue"
        if text:
            logger.debug("Received text message (%d chars)", len(text))
            voice_sessions[voice_session_id]["conversation_history"].append(
                {"role": "user", "content": text}
            )
            session_context = voice_sessions[voice_session_id].get("context", {})
            command_executed = await process_voice_command(
                websocket,
                voice_session_id,
                text,
                session_context,
                is_text_message=True,
            )
            if command_executed:
                return "continue"
            try:
                logger.debug("Text message is conversational, sending to Omni")
                omni_client = get_session_omni_client(voice_session_id)
                if omni_client:
                    await omni_client.send_text_message(text)
                else:
                    logger.warning(
                        "Cannot send text: OmniClient not found for session %s",
                        voice_session_id,
                    )
                    await safe_websocket_send(
                        websocket,
                        {
                            "type": "error",
                            "error": "Voice session not initialized",
                        },
                    )
            except (RuntimeError, ConnectionError, AttributeError) as text_error:
                logger.error(
                    "Text message processing error: %s",
                    text_error,
                    exc_info=True,
                )
                await safe_websocket_send(
                    websocket,
                    {"type": "error", "error": str(text_error)},
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
        active_panel = (
            message.get("active_panel") or new_context_in.get("active_panel") or cur_panel or "none"
        )
        session_dt = (
            voice_sessions[voice_session_id].get("diagram_type")
            or new_context_in.get("diagram_type")
            or "circle_map"
        )
        merged_ctx, res_dt, res_panel = await merge_voice_context_with_library(
            current_user.id,
            new_context_in,
            diagram_type=session_dt,
            active_panel=active_panel,
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

        updated_context = {
            "diagram_type": new_diagram_type,
            "active_panel": res_panel,
            "conversation_history": voice_sessions[voice_session_id].get("conversation_history", []),
            "selected_nodes": merged_ctx.get("selected_nodes", []),
            "diagram_data": diagram_data,
            "diagram_library_id": merged_ctx.get("diagram_library_id"),
            "diagram_display_title": merged_ctx.get("diagram_display_title"),
        }
        new_instructions = build_voice_instructions(updated_context)
        try:
            omni_client = get_session_omni_client(voice_session_id)
            if omni_client:
                await omni_client.update_instructions(new_instructions)
            else:
                logger.debug(
                    "Cannot update instructions: OmniClient not found for session %s",
                    voice_session_id,
                )
        except (RuntimeError, ConnectionError, AttributeError) as err:
            logger.debug("Error updating Omni instructions: %s", err)

        hub_rev_raw = voice_sessions[voice_session_id].get("_hub_scope_revision")
        hub_rev = hub_rev_raw if isinstance(hub_rev_raw, int) else None
        idempotency_key_raw = message.get("idempotency_key")
        idempotency_key = (
            str(idempotency_key_raw).strip()
            if isinstance(idempotency_key_raw, str) and idempotency_key_raw.strip()
            else None
        )
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
            )
        except ValueError as mut_err:
            logger.warning("Hub mutation rejected for %s: %s", voice_session_id, mut_err)
            await safe_websocket_send(
                websocket,
                {"type": "error", "error": f"Context mutation rejected: {mut_err}"},
            )
            return "continue"
        new_rev = mutation_out.get("revision")
        if isinstance(new_rev, int):
            voice_sessions[voice_session_id]["_hub_scope_revision"] = new_rev

        children_count = len(diagram_data.get("children", []))
        logger.debug(
            "Context updated for %s with %d nodes",
            voice_session_id,
            children_count,
        )
        return "continue"

    if msg_type == "stop":
        return "stop"

    if msg_type == "cancel_response":
        logger.debug("User requested to cancel response")
        omni_client = get_session_omni_client(voice_session_id)
        if omni_client:
            await omni_client.cancel_response()
            await safe_websocket_send(websocket, {"type": "response_cancelled"})
        else:
            logger.warning(
                "Cannot cancel response: OmniClient not found for session %s",
                voice_session_id,
            )
        return "continue"

    if msg_type == "clear_audio_buffer":
        logger.debug("User requested to clear audio buffer")
        omni_client = get_session_omni_client(voice_session_id)
        if omni_client:
            await omni_client.clear_audio_buffer()
            await safe_websocket_send(websocket, {"type": "audio_buffer_cleared"})
        else:
            logger.warning(
                "Cannot clear audio buffer: OmniClient not found for session %s",
                voice_session_id,
            )
        return "continue"

    if msg_type == "commit_audio_buffer":
        logger.debug("User requested to commit audio buffer")
        omni_client = get_session_omni_client(voice_session_id)
        if omni_client:
            await omni_client.commit_audio_buffer()
            await safe_websocket_send(websocket, {"type": "audio_buffer_committed"})
        else:
            logger.warning(
                "Cannot commit audio buffer: OmniClient not found for session %s",
                voice_session_id,
            )
        return "continue"

    if msg_type == "append_image":
        await kitty_ws_handle_append_image(
            websocket,
            voice_session_id,
            message,
            voice_sessions,
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
