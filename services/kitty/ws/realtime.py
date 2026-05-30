"""Kitty Agent WebSocket realtime session (Omni + inbound dispatch)."""

from __future__ import annotations

import asyncio
import time

from fastapi import WebSocket, WebSocketDisconnect

from services.infrastructure.monitoring.ws_metrics import redis_increment_active_total
from services.kitty.omni.event_loop import run_kitty_omni_event_loop
from services.kitty.ws.lifecycle import (
    authenticate_kitty_websocket,
    cleanup_kitty_websocket_session,
    prepare_diagram_voice_lock,
    receive_kitty_start_message,
    run_kitty_client_message_loop,
    run_kitty_idle_watchdog,
    start_kitty_session,
)
from services.kitty.context.messaging import safe_websocket_send
from services.kitty.session.runtime_state import logger
from services.kitty.session.event_handlers import (
    KittySessionRuntime,
    setup_session_event_handlers,
    teardown_session_event_handlers,
)
from services.kitty.session.events import get_session_event_bus
from utils.ws_limits import kitty_ws_idle_timeout_seconds
from utils.ws_session_registry import _registry as _ws_registry


async def kitty_realtime_websocket(websocket: WebSocket, diagram_session_id: str) -> None:
    """
    WebSocket endpoint for real-time voice conversation.

    Protocol:
    Client -> Server:
    - {"type": "start", "diagram_type": str, "active_panel": str, "context": {...}}
    - {"type": "audio", "data": str}  # base64 PCM audio
    - {"type": "context_update", "active_panel": str, "context": {...}}
    - {"type": "stop"}

    Server -> Client:
    - {"type": "connected", "session_id": str}
    - {"type": "transcription", "text": str}
    - {"type": "text_chunk", "text": str}
    - {"type": "audio_chunk", "audio": str}  # base64
    - {"type": "speech_started", "audio_start_ms": int}
    - {"type": "speech_stopped", "audio_end_ms": int}
    - {"type": "response_done"}
    - {"type": "action", "action": str, "params": {...}}
    - {"type": "error", "error": str}
    """
    auth = await authenticate_kitty_websocket(websocket, diagram_session_id)
    if auth is None:
        return

    current_user = auth.current_user
    diagram_session_id = auth.diagram_session_id
    hub = auth.hub
    hub_session_id = auth.hub_session_id

    voice_ws_session = await _ws_registry.register(
        current_user.id,
        "voice",
        websocket,
        diagram_session_id=diagram_session_id,
    )
    await redis_increment_active_total(1)
    ws_session_started = time.monotonic()
    logger.info(
        "[WSSession] OPEN  session=%s endpoint=voice user_id=%s remote=%s",
        voice_ws_session.session_id,
        current_user.id,
        voice_ws_session.remote_addr,
    )

    voice_session_id: str | None = None
    kitty_hub_registered = False

    try:
        start_msg = await receive_kitty_start_message(websocket)
        if start_msg is None:
            return

        agent_session_id = f"diagram_{diagram_session_id}"
        await prepare_diagram_voice_lock(websocket, diagram_session_id, agent_session_id)

        start_result = await start_kitty_session(
            websocket=websocket,
            auth=auth,
            start_msg=start_msg,
        )
        if start_result is None:
            return

        voice_session_id = start_result.voice_session_id
        kitty_hub_registered = True
        last_client_inbound: list[float] = [time.monotonic()]

        session_runtime = KittySessionRuntime(
            websocket=websocket,
            voice_session_id=voice_session_id,
        )
        await setup_session_event_handlers(session_runtime)
        event_bus = get_session_event_bus(voice_session_id)

        client_task = asyncio.create_task(
            run_kitty_client_message_loop(
                websocket=websocket,
                inbound_ctx=start_result.inbound_ctx,
                voice_session_id=voice_session_id,
                user_id=str(current_user.id),
                last_client_inbound=last_client_inbound,
            )
        )
        omni_task = asyncio.create_task(
            run_kitty_omni_event_loop(
                websocket,
                voice_session_id,
                start_result.omni_generator,
                event_bus,
            )
        )

        idle_timeout_sec = kitty_ws_idle_timeout_seconds()

        try:
            if idle_timeout_sec is None:
                await asyncio.gather(client_task, omni_task)
            else:
                idle_task = asyncio.create_task(
                    run_kitty_idle_watchdog(
                        websocket=websocket,
                        hub=hub,
                        diagram_session_id=diagram_session_id,
                        current_user=current_user,
                        voice_session_id=voice_session_id,
                        last_client_inbound=last_client_inbound,
                    )
                )
                _done, _pending = await asyncio.wait(
                    {client_task, omni_task, idle_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if idle_task in _done:
                    if not client_task.done():
                        client_task.cancel()
                    if not omni_task.done():
                        omni_task.cancel()
                else:
                    idle_task.cancel()
                await asyncio.gather(client_task, omni_task, idle_task, return_exceptions=True)
        finally:
            if voice_session_id:
                await teardown_session_event_handlers(voice_session_id)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", voice_session_id)

    except (RuntimeError, ConnectionError, AttributeError) as exc:
        logger.error("WebSocket error: %s", exc, exc_info=True)
        try:
            await safe_websocket_send(websocket, {"type": "error", "error": str(exc)})
        except Exception as send_exc:
            logger.debug("Failed to send WebSocket error response: %s", send_exc)

    finally:
        await _ws_registry.unregister(voice_ws_session.session_id)
        await redis_increment_active_total(-1)
        logger.info(
            "[WSSession] CLOSE session=%s endpoint=kitty user_id=%s duration=%.1fs",
            voice_ws_session.session_id,
            current_user.id,
            time.monotonic() - ws_session_started,
        )

        await cleanup_kitty_websocket_session(
            websocket=websocket,
            diagram_session_id=diagram_session_id,
            hub=hub,
            hub_session_id=hub_session_id,
            voice_session_id=voice_session_id,
            kitty_hub_registered=kitty_hub_registered,
            current_user=current_user,
        )
