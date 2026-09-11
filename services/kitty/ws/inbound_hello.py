"""Hello + abort turn-cancel handlers (keep inbound.py under the line cap).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

from services.kitty.audio.session_bridge import interrupt_kitty_tts
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.session.device_hello import apply_hello_to_session
from services.kitty.session.turn_task import cancel_active_turn
from services.kitty.ws.inbound_types import KittyInboundFlow, KittyWsInboundContext


async def handle_hello(ctx: KittyWsInboundContext, message: dict) -> KittyInboundFlow:
    """Advertise listen_mode / firmware; register the device for admin."""
    try:
        user_id = int(ctx.user_id)
    except (TypeError, ValueError):
        return "continue"
    ack = await apply_hello_to_session(ctx.voice_session_id, user_id, message)
    await safe_websocket_send(ctx.websocket, ack)
    return "continue"


async def interrupt_turn_and_tts(
    ctx: KittyWsInboundContext,
    *,
    reason: str,
    extra_type: str | None = None,
) -> None:
    """Cancel the agent-loop Task, bump CosyVoice generation, ack the client."""
    await cancel_active_turn(ctx.voice_session_id, reason=reason)
    await interrupt_kitty_tts(ctx.voice_session_id)
    await safe_websocket_send(ctx.websocket, {"type": "tts_interrupted"})
    if extra_type:
        await safe_websocket_send(ctx.websocket, {"type": extra_type})


def abort_reason(message: dict) -> str:
    """Normalize abort reason for the interrupted observation."""
    raw = message.get("reason")
    text = str(raw).strip() if raw is not None else ""
    if text in {"user_ptt", "text_input", "user"}:
        return text
    return "user"
