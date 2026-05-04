"""
Relay browser canvas audio to DashScope Qwen3 ASR Flash Realtime over WebSocket.

Protocol matches the official WebSocket API (session.update, append, session.finish).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from typing import Any, Dict, Optional

import websockets
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect
from websockets.asyncio.client import ClientConnection
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


def bridge_error_json(code: str, message: str) -> str:
    """JSON text frame matching Qwen-ASR-Realtime ``error`` event shape (nested ``error``)."""
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


def resolve_dashscope_api_key() -> Optional[str]:
    """Prefer ``DASHSCOPE_API_KEY``, then ``QWEN_API_KEY`` (DashScope ASR docs)."""
    for candidate in (config.DASHSCOPE_API_KEY, config.QWEN_API_KEY):
        if not candidate:
            continue
        stripped = str(candidate).strip()
        if stripped:
            return stripped
    return None


def build_session_update_payload(
    language: str,
    *,
    sample_rate: int = 16000,
    input_audio_format: str = "pcm",
) -> Dict[str, Any]:
    """session.update for Qwen-ASR-Realtime (VAD, multimodal text out)."""
    return {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "type": "session.update",
        "session": {
            "modalities": ["text"],
            "input_audio_format": input_audio_format,
            "sample_rate": sample_rate,
            "input_audio_transcription": {"language": language},
            "turn_detection": {
                "type": "server_vad",
                "threshold": 0.0,
                "silence_duration_ms": 400,
            },
        },
    }


async def _send_audio_append(upstream: ClientConnection, audio_b64: str) -> None:
    payload = {
        "event_id": f"evt_{uuid.uuid4().hex}",
        "type": "input_audio_buffer.append",
        "audio": audio_b64,
    }
    await upstream.send(json.dumps(payload))


async def run_asr_relay(
    client_ws: WebSocket,
    language: str,
    *,
    model: Optional[str] = None,
    sample_rate: int = 16000,
    input_audio_format: str = "pcm",
    rate_limiter: Optional[WebsocketMessageRateLimiter] = None,
    max_inbound_text_bytes: int = DEFAULT_MAX_WS_TEXT_BYTES,
) -> None:
    """
    Bridge authenticated browser WebSocket to DashScope ASR realtime.

    Client messages toward DashScope (shortcuts in parentheses):
        {"type": "start", ...} — MindGraph-only bootstrap; relay sends
        ``session.update``. ``input_audio_buffer.append`` (alias ``append``):
        base64 ``audio``. ``session.finish`` (alias ``finish``).

    DashScope server events are forwarded unchanged (``session.created``,
    ``session.updated``, ``input_audio_buffer.*``, transcription events,
    ``session.finished``, ``error``, etc.).
    """
    api_key = resolve_dashscope_api_key()
    if not api_key:
        await safe_websocket_send_text(
            client_ws,
            bridge_error_json("asr_config", "Speech service is not configured"),
        )
        return

    default_asr_model = "qwen3-asr-flash-realtime"
    raw_model = model or config.QWEN_ASR_REALTIME_MODEL or ""
    resolved_model = str(raw_model).strip() or default_asr_model
    base = config.DASHSCOPE_REALTIME_WS_BASE.rstrip("/")
    url = f"{base}?model={resolved_model}"
    extra_headers = {
        "Authorization": f"Bearer {api_key}",
        "OpenAI-Beta": "realtime=v1",
    }

    try:
        upstream = await websockets.connect(
            url,
            additional_headers=extra_headers,
            ping_interval=20,
            ping_timeout=20,
            max_size=None,
        )
    except (OSError, TimeoutError) as exc:
        logger.warning("ASR upstream connect failed: %s", exc)
        await safe_websocket_send_text(
            client_ws,
            bridge_error_json("upstream_connect", "Could not connect to speech service"),
        )
        return
    except websockets.exceptions.InvalidHandshake as exc:
        logger.warning("ASR upstream handshake failed: %s", exc)
        await safe_websocket_send_text(
            client_ws,
            bridge_error_json("upstream_handshake", "Speech service rejected connection"),
        )
        return
    except Exception as exc:
        logger.exception("ASR upstream connect failed (unexpected): %s", exc)
        err = bridge_error_json(
            "upstream_connect",
            "Could not connect to speech service",
        )
        await safe_websocket_send_text(client_ws, err)
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
            logger.debug("ASR upstream closed normally")
        except ConnectionClosedError as exc:
            logger.debug("ASR upstream closed with error: %s", exc)
        except ConnectionClosed:
            logger.debug("ASR upstream connection closed")

    pump_task = asyncio.create_task(pump_upstream())

    try:
        await upstream.send(
            json.dumps(
                build_session_update_payload(
                    language,
                    sample_rate=sample_rate,
                    input_audio_format=input_audio_format,
                ),
            ),
        )

        # Wait for session.updated OR upstream closure, whichever comes first.
        # If pump_task ends before session_ready is set (e.g. DashScope rejects the
        # key or closes early), we must not stall the full timeout — the client has
        # already received the forwarded error event.
        session_ready_task = asyncio.create_task(session_ready.wait())
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
                bridge_error_json("session_timeout", "Speech session did not start in time"),
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
                    bridge_error_json("too_large", "Message too large"),
                )
                break
            if rate_limiter is not None and not rate_limiter.allow():
                await safe_websocket_send_text(
                    client_ws,
                    bridge_error_json("rate_limit", "Too many messages"),
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
                if msg_type == "input_audio_buffer.append":
                    evt = {
                        "event_id": data.get("event_id") or f"evt_{uuid.uuid4().hex}",
                        "type": "input_audio_buffer.append",
                        "audio": audio_b64,
                    }
                    await upstream.send(json.dumps(evt))
                else:
                    await _send_audio_append(upstream, audio_b64)
            elif msg_type in ("finish", "session.finish"):
                ev_id = data.get("event_id") if isinstance(data.get("event_id"), str) else None
                finish_evt = {
                    "event_id": ev_id or f"evt_{uuid.uuid4().hex}",
                    "type": "session.finish",
                }
                await upstream.send(json.dumps(finish_evt))
            else:
                continue

    except ConnectionClosedError as exc:
        logger.debug("ASR upstream error during relay: %s", exc)
    except ConnectionClosed:
        logger.debug("ASR upstream closed during relay")
    except (RuntimeError, TypeError, ValueError) as exc:
        logger.exception("ASR relay failed: %s", exc)
        await safe_websocket_send_text(
            client_ws,
            bridge_error_json("relay", "Speech relay error"),
        )
    finally:
        pump_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await pump_task
        with contextlib.suppress(OSError, RuntimeError, ConnectionClosed):
            await upstream.close()
