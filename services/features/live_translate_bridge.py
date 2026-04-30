"""
Relay browser canvas audio to DashScope Qwen3 LiveTranslate Flash Realtime over WebSocket.

Protocol:
  1. session.update — sets input_audio_transcription.language, translation.language,
     modalities=["text"], input_audio_format="pcm16".
  2. Continuous input_audio_buffer.append — base64 PCM16 audio chunks.
  DashScope auto-detects VAD; no session.finish needed; session stays alive until client disconnects.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

import websockets
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.client import ClientConnection
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from config.settings import config
from utils.ws_limits import (
    DEFAULT_MAX_WS_TEXT_BYTES,
    WebsocketMessageRateLimiter,
    inbound_text_exceeds_limit,
    receive_websocket_text_frame,
    safe_websocket_send_text,
)

logger = logging.getLogger(__name__)

SESSION_READY_TIMEOUT_SEC = 25.0


def translate_error_json(code: str, message: str) -> str:
    """JSON frame matching the Qwen-ASR-Realtime error event shape."""
    return json.dumps(
        {
            "event_id": f"evt_{uuid.uuid4().hex}",
            "type": "error",
            "error": {
                "type": "invalid_request_error",
                "code": code,
                "message": message,
            },
        }
    )


def _resolve_api_key() -> Optional[str]:
    """Prefer DASHSCOPE_API_KEY, then QWEN_API_KEY."""
    for candidate in (config.DASHSCOPE_API_KEY, config.QWEN_API_KEY):
        if not candidate:
            continue
        stripped = str(candidate).strip()
        if stripped:
            return stripped
    return None


def build_translate_session_update(
    source_language: str,
    target_language: str,
) -> Dict[str, Any]:
    """session.update payload for Qwen3 LiveTranslate (text-only output).

    ``input_audio_format`` is hardcoded to ``pcm16`` — the only value accepted
    by the LiveTranslate realtime API.  ``sample_rate`` is not part of the
    LiveTranslate session schema and must not be sent.
    """
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "type": "session.update",
        "session": {
            "modalities": ["text"],
            "input_audio_format": "pcm16",
            "input_audio_transcription": {
                "language": source_language,
            },
            "translation": {
                "language": target_language,
            },
        },
    }


async def run_translate_relay(
    client_ws: WebSocket,
    source_language: str,
    target_language: str,
    *,
    model: Optional[str] = None,
    rate_limiter: Optional[WebsocketMessageRateLimiter] = None,
    max_inbound_text_bytes: int = DEFAULT_MAX_WS_TEXT_BYTES,
) -> None:
    """
    Bridge authenticated browser WebSocket to DashScope LiveTranslate realtime.

    Client messages (after the initial 'start' frame handled by the router):
        input_audio_buffer.append (alias 'append') — base64 audio.

    All DashScope server events are forwarded unchanged.
    The session stays open until the client disconnects; no session.finish needed.
    """
    api_key = _resolve_api_key()
    if not api_key:
        await safe_websocket_send_text(
            client_ws,
            translate_error_json("asr_config", "Translation service is not configured"),
        )
        return

    default_model = "qwen3-livetranslate-flash-realtime"
    env_model = os.getenv("QWEN_LIVE_TRANSLATE_MODEL", "")
    resolved_model = str(model or env_model).strip() or default_model
    base = config.DASHSCOPE_REALTIME_WS_BASE.rstrip("/")
    url = f"{base}?model={resolved_model}"
    extra_headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        upstream: ClientConnection = await websockets.connect(
            url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        )
    except (OSError, TimeoutError) as exc:
        logger.warning("LiveTranslate upstream connect failed: %s", exc)
        await safe_websocket_send_text(
            client_ws,
            translate_error_json("upstream_connect", "Could not connect to translation service"),
        )
        return
    except websockets.exceptions.InvalidHandshake as exc:
        logger.warning("LiveTranslate upstream handshake failed: %s", exc)
        await safe_websocket_send_text(
            client_ws,
            translate_error_json("upstream_handshake", "Translation service rejected connection"),
        )
        return
    except Exception as exc:
        logger.exception("LiveTranslate upstream connect failed (unexpected): %s", exc)
        await safe_websocket_send_text(
            client_ws,
            translate_error_json("upstream_connect", "Could not connect to translation service"),
        )
        return

    session_ready = asyncio.Event()

    async def pump_upstream() -> None:
        try:
            async for raw in upstream:
                text_raw = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                await safe_websocket_send_text(client_ws, text_raw)
                try:
                    payload = json.loads(text_raw)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "session.updated":
                    session_ready.set()
        except ConnectionClosedOK:
            logger.debug("LiveTranslate upstream closed normally")
        except ConnectionClosedError as exc:
            logger.debug("LiveTranslate upstream closed with error: %s", exc)
        except ConnectionClosed:
            logger.debug("LiveTranslate upstream connection closed")

    pump_task = asyncio.create_task(pump_upstream())

    try:
        await upstream.send(
            json.dumps(
                build_translate_session_update(source_language, target_language)
            )
        )

        session_ready_task: asyncio.Task[None] = asyncio.create_task(session_ready.wait())
        try:
            await asyncio.wait(
                {session_ready_task, pump_task},
                timeout=SESSION_READY_TIMEOUT_SEC,
                return_when=asyncio.FIRST_COMPLETED,
            )
        finally:
            session_ready_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await session_ready_task

        if not session_ready.is_set():
            await safe_websocket_send_text(
                client_ws,
                translate_error_json(
                    "session_timeout", "Translation session did not start in time"
                ),
            )
            return

        while True:
            try:
                msg = await receive_websocket_text_frame(client_ws)
            except WebSocketDisconnect:
                break
            if inbound_text_exceeds_limit(msg, max_inbound_text_bytes):
                await safe_websocket_send_text(
                    client_ws,
                    translate_error_json("too_large", "Message too large"),
                )
                break
            if rate_limiter is not None and not rate_limiter.allow():
                await safe_websocket_send_text(
                    client_ws,
                    translate_error_json("rate_limit", "Too many messages"),
                )
                break
            try:
                data = json.loads(msg)
            except json.JSONDecodeError:
                continue

            msg_type = data.get("type")
            if msg_type == "start":
                continue
            if msg_type in ("append", "input_audio_buffer.append"):
                audio_b64 = data.get("audio") or data.get("data")
                if not audio_b64 or not isinstance(audio_b64, str):
                    continue
                evt = {
                    "event_id": data.get("event_id") or f"evt_{uuid.uuid4().hex}",
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                }
                await upstream.send(json.dumps(evt))

    except ConnectionClosedError as exc:
        logger.debug("LiveTranslate upstream error during relay: %s", exc)
    except ConnectionClosed:
        logger.debug("LiveTranslate upstream closed during relay")
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.exception("LiveTranslate relay failed: %s", exc)
        await safe_websocket_send_text(
            client_ws,
            translate_error_json("relay", "Translation relay error"),
        )
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        with contextlib.suppress(OSError, RuntimeError, ConnectionClosed):
            await upstream.close()
