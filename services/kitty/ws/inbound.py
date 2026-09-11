"""Inbound JSON message handling for Kitty WebSocket.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from fastapi import WebSocket

from models.domain.auth import User
from services.kitty.asr.audio_format import parse_asr_audio_format
from services.kitty.audio.session_bridge import (
    feed_session_asr_audio,
    interrupt_kitty_tts,
    start_session_asr,
    stop_session_asr,
)
from services.kitty.ws.inbound_text import (
    KittyTextIngest,
    asr_utterance_already_ingested,
    ingest_kitty_user_text,
    mark_asr_utterance_ingested,
)
from services.kitty.ws.inbound_hello import (
    abort_reason,
    handle_hello,
    interrupt_turn_and_tts,
)
from services.kitty.ws.narrate import handle_kitty_narrate, handle_kitty_prefetch
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.infra.desktop.kitty_voice_phase_fanout import (
    fanout_voice_phase_from_outbound_type,
)
from services.kitty.infra.control.kitty_workflow_trace import kitty_wf_log
from services.kitty.session.events import KittyEvent, get_session_event_bus
from services.kitty.session.runtime_state import voice_sessions
from services.kitty.ws.guards import KITTY_WS_MAX_AUDIO_B64_CHARS
from services.kitty.ws.inbound_context import (
    handle_context_update,
    handle_diagram_mutation_ack,
    handle_get_desktop_session_snapshot,
)
from services.kitty.ws.inbound_types import KittyInboundFlow, KittyWsInboundContext

__all__ = [
    "KittyInboundFlow",
    "KittyWsInboundContext",
    "build_kitty_inbound_context",
    "dispatch_kitty_ws_inbound_message",
]

logger = logging.getLogger(__name__)

KittyInboundHandler = Callable[[KittyWsInboundContext, dict], Awaitable[KittyInboundFlow]]


async def _handle_asr_start(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    hints_raw = message.get("language_hints")
    language_hints: list[str] | None = None
    if isinstance(hints_raw, list):
        language_hints = [str(item) for item in hints_raw if str(item).strip()]
    elif str(message.get("language") or "").strip().lower().startswith("zh"):
        language_hints = ["zh"]
    utterance_raw = message.get("utterance_id")
    utterance_id = str(utterance_raw).strip() if isinstance(utterance_raw, str) and str(utterance_raw).strip() else None
    sess = voice_sessions.get(ctx.voice_session_id) or {}
    lane_raw = sess.get("_kitty_client_lane")
    lane = lane_raw if isinstance(lane_raw, str) and lane_raw.strip() else "—"
    debug_ctx = message.get("debug_ctx")
    ctx_label = str(debug_ctx) if debug_ctx is not None else "—"
    audio_format = parse_asr_audio_format(message)
    logger.info(
        "Kitty PTT asr_start sid=%s lane=%s hints=%s fmt=%s ctx=%s utt=%s",
        ctx.voice_session_id[:12],
        lane,
        language_hints or ["zh"],
        audio_format,
        ctx_label,
        (utterance_id or "—")[:16],
    )
    kitty_wf_log(
        "asr_start",
        f"lane={lane} hints={language_hints or ['zh']} fmt={audio_format} ctx={ctx_label} utt={utterance_id or '—'}",
        voice_session_id=ctx.voice_session_id,
    )
    await start_session_asr(
        ctx.websocket,
        ctx.voice_session_id,
        language_hints=language_hints,
        utterance_id=utterance_id,
        audio_format=audio_format,
    )
    return "continue"


async def _handle_asr_audio(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    audio_data = message.get("data")
    if isinstance(audio_data, str) and audio_data:
        if len(audio_data) > KITTY_WS_MAX_AUDIO_B64_CHARS:
            logger.warning(
                "Kitty PTT asr_audio too large sid=%s chars=%d",
                ctx.voice_session_id[:12],
                len(audio_data),
            )
            await safe_websocket_send(
                ctx.websocket,
                {"type": "error", "error": "Audio frame too large"},
            )
            return "continue"
        utterance_raw = message.get("utterance_id")
        utterance_id = (
            str(utterance_raw).strip() if isinstance(utterance_raw, str) and str(utterance_raw).strip() else None
        )
        await feed_session_asr_audio(
            ctx.voice_session_id,
            audio_data,
            utterance_id=utterance_id,
        )
    return "continue"


async def _handle_asr_stop(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    sess = voice_sessions.get(ctx.voice_session_id) or {}
    lane_raw = sess.get("_kitty_client_lane")
    lane = lane_raw if isinstance(lane_raw, str) and lane_raw.strip() else "—"
    utterance_raw = message.get("utterance_id")
    utterance_id = str(utterance_raw).strip() if isinstance(utterance_raw, str) and str(utterance_raw).strip() else None
    peak_raw = message.get("peak")
    client_peak = peak_raw if isinstance(peak_raw, int) and not isinstance(peak_raw, bool) else None
    logger.info(
        "Kitty PTT asr_stop sid=%s lane=%s utt=%s peak=%s",
        ctx.voice_session_id[:12],
        lane,
        (utterance_id or "—")[:16],
        client_peak if client_peak is not None else "—",
    )
    kitty_wf_log(
        "asr_stop",
        f"lane={lane} client release utt={utterance_id or '—'}",
        voice_session_id=ctx.voice_session_id,
    )
    final_text = await stop_session_asr(ctx.voice_session_id, utterance_id=utterance_id)
    stopped_payload: dict[str, object] = {"type": "asr_stopped", "text": final_text}
    if utterance_id:
        stopped_payload["utterance_id"] = utterance_id
    await safe_websocket_send(ctx.websocket, stopped_payload)
    await fanout_voice_phase_from_outbound_type(ctx.voice_session_id, "asr_stopped")
    cleaned = final_text.strip()
    if not cleaned:
        return "continue"
    mark_asr_utterance_ingested(ctx.voice_session_id, utterance_id)
    kitty_wf_log(
        "asr_auto_ingest",
        cleaned[:120],
        voice_session_id=ctx.voice_session_id,
    )
    return await ingest_kitty_user_text(
        ctx,
        cleaned,
        KittyTextIngest(
            utterance_id=utterance_id,
            ingress_source="asr",
            cancel_prior=False,
        ),
    )


async def _handle_prefetch(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    await handle_kitty_prefetch(ctx.websocket, ctx.voice_session_id, message)
    return "continue"


async def _handle_narrate(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    await handle_kitty_narrate(ctx.websocket, ctx.voice_session_id, message)
    return "continue"


async def _interrupt_tts(ctx: KittyWsInboundContext) -> None:
    await interrupt_kitty_tts(ctx.voice_session_id)
    await safe_websocket_send(ctx.websocket, {"type": "tts_interrupted"})


async def _handle_tts_interrupt(ctx: KittyWsInboundContext, _message: dict) -> KittyInboundFlow:
    await _interrupt_tts(ctx)
    return "continue"


async def _handle_abort(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    await interrupt_turn_and_tts(ctx, reason=abort_reason(message))
    return "continue"


async def _handle_cancel_response(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    await interrupt_turn_and_tts(
        ctx,
        reason=abort_reason(message),
        extra_type="response_cancelled",
    )
    return "continue"


async def _handle_tts_set_enabled(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    enabled = bool(message.get("enabled", True))
    voice_sessions[ctx.voice_session_id]["_kitty_tts_enabled"] = enabled
    await safe_websocket_send(
        ctx.websocket,
        {"type": "tts_enabled", "enabled": enabled},
    )
    return "continue"


async def _handle_text(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    raw_utt = message.get("utterance_id")
    utterance_id = str(raw_utt).strip() if isinstance(raw_utt, str) and str(raw_utt).strip() else None
    if asr_utterance_already_ingested(ctx.voice_session_id, utterance_id):
        kitty_wf_log(
            "text_inbound_dedup",
            (utterance_id or "—")[:16],
            voice_session_id=ctx.voice_session_id,
        )
        return "continue"
    await _interrupt_tts(ctx)
    raw_request_id = message.get("request_id")
    request_id = str(raw_request_id).strip() if isinstance(raw_request_id, str) and str(raw_request_id).strip() else ""
    return await ingest_kitty_user_text(
        ctx,
        str(message.get("text") or ""),
        KittyTextIngest(
            utterance_id=utterance_id,
            ingress_source=str(message.get("ingress_source") or "text"),
            request_id=request_id,
        ),
    )


async def _handle_auto_complete_done(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    status_raw = message.get("status")
    status = status_raw.strip() if isinstance(status_raw, str) and status_raw.strip() else "finished"
    node_raw = message.get("node_id")
    node_id = node_raw.strip() if isinstance(node_raw, str) else None
    done_payload: dict[str, Any] = {"status": status}
    if node_id:
        done_payload["node_id"] = node_id
    bus = get_session_event_bus(ctx.voice_session_id)
    await bus.emit(
        KittyEvent(
            kind="auto_complete_done",
            voice_session_id=ctx.voice_session_id,
            payload=done_payload,
        )
    )
    return "continue"


async def _handle_stop(_ctx: KittyWsInboundContext, _message: dict) -> KittyInboundFlow:
    return "stop"


async def _handle_append_image(ctx: KittyWsInboundContext, _message: dict) -> KittyInboundFlow:
    await safe_websocket_send(
        ctx.websocket,
        {
            "type": "error",
            "error": "append_image is retired; use POST /api/kitty/conversation_image",
        },
    )
    return "continue"


async def _handle_listen(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    """Alias of asr_start / asr_stop (Xiaozhi listen shape, Kitty wire)."""
    state_raw = message.get("state")
    state = str(state_raw).strip().lower() if state_raw is not None else ""
    if state == "stop":
        return await _handle_asr_stop(ctx, message)
    return await _handle_asr_start(ctx, message)


_HANDLERS: Dict[str, KittyInboundHandler] = {
    "asr_start": _handle_asr_start,
    "asr_audio": _handle_asr_audio,
    "asr_stop": _handle_asr_stop,
    "listen": _handle_listen,
    "hello": handle_hello,
    "prefetch": _handle_prefetch,
    "narrate": _handle_narrate,
    "tts_interrupt": _handle_tts_interrupt,
    "abort": _handle_abort,
    "cancel_response": _handle_cancel_response,
    "tts_set_enabled": _handle_tts_set_enabled,
    "text": _handle_text,
    "auto_complete_done": _handle_auto_complete_done,
    "get_desktop_session_snapshot": handle_get_desktop_session_snapshot,
    "context_update": handle_context_update,
    "diagram_mutation_ack": handle_diagram_mutation_ack,
    "stop": _handle_stop,
    "append_image": _handle_append_image,
}


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
    msg_type = message.get("type")
    if not isinstance(msg_type, str) or not msg_type.strip():
        return "continue"
    handler = _HANDLERS.get(msg_type.strip())
    if handler is None:
        return "continue"
    return await handler(ctx, message)


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
