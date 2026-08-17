"""Qwen-TTS Realtime WebSocket adapter for Kitty lecture callbacks.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
from typing import Optional

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed, WebSocketException

from config.dashscope_urls import (
    build_dashscope_headers,
    build_qwen_tts_realtime_ws_url,
    normalize_dashscope_region,
)
from config.settings import config
from services.kitty.asr.fun_asr_realtime import resolve_dashscope_api_key
from services.kitty.tts.cosyvoice_realtime import (
    AudioCallback,
    DoneCallback,
    ErrorCallback,
    split_cosyvoice_text,
)
from services.tts.qwen_realtime_events import (
    build_qwen_session_finish,
    build_qwen_session_update,
    build_qwen_text_append,
)
from services.tts.routing import TtsRoute
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)
_QWEN_RT_ERRORS = LLM_PIPELINE_ERRORS + (WebSocketException, ConnectionClosed)


class QwenRealtimeKittyTtsClient:
    """Qwen-TTS Realtime WS, adapted to Kitty ``on_audio(b64, format)``."""

    def __init__(
        self,
        *,
        route: TtsRoute,
        voice: str,
        on_audio: AudioCallback,
        on_done: Optional[DoneCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.sample_rate = route.sample_rate
        self._route = route
        self._voice = voice
        self._on_audio = on_audio
        self._on_done = on_done
        self._on_error = on_error
        self._cancel = False

    async def speak(self, text: str) -> None:
        """Connect, append text, finish session, forward PCM chunks."""
        message = str(text or "").strip()
        if not message or self._cancel:
            return
        api_key = resolve_dashscope_api_key()
        if not api_key:
            raise RuntimeError("DashScope API key not configured for Qwen-TTS Realtime")
        try:
            chunks = await self._synthesize(api_key, message)
        except _QWEN_RT_ERRORS as exc:
            if self._on_error:
                await self._on_error(str(exc))
            raise
        if self._cancel:
            return
        if not chunks:
            raise RuntimeError("Qwen-TTS Realtime returned no audio")
        for piece in chunks:
            encoded = base64.b64encode(piece).decode("ascii")
            await self._on_audio(encoded, "pcm")
        if self._on_done:
            await self._on_done()

    async def _synthesize(self, api_key: str, message: str) -> list[bytes]:
        region = normalize_dashscope_region(str(getattr(config, "DASHSCOPE_REGION", None) or "cn-beijing"))
        explicit = str(getattr(config, "DASHSCOPE_REALTIME_WS_BASE", None) or "").strip() or None
        url = build_qwen_tts_realtime_ws_url(
            self._route.model,
            workspace_id=config.DASHSCOPE_WORKSPACE_ID,
            region=region,
            explicit_url=explicit,
        )
        headers = build_dashscope_headers(
            api_key,
            workspace_id=config.DASHSCOPE_WORKSPACE_ID,
            content_type=None,
        )
        chunks: list[bytes] = []
        created = asyncio.Event()
        updated = asyncio.Event()
        done = asyncio.Event()
        socket = await websockets.connect(url, additional_headers=headers, ping_interval=20, ping_timeout=10)
        reader = asyncio.create_task(self._read_events(socket, chunks, created, updated, done))
        try:
            await asyncio.wait_for(created.wait(), timeout=10.0)
            if self._cancel:
                return []
            await socket.send(
                json.dumps(
                    build_qwen_session_update(
                        voice=self._voice or "Cherry",
                        response_format="pcm",
                        mode="server_commit",
                        sample_rate=self._route.sample_rate,
                    )
                )
            )
            await asyncio.wait_for(updated.wait(), timeout=10.0)
            if self._cancel:
                return []
            for piece in split_cosyvoice_text(message):
                await socket.send(json.dumps(build_qwen_text_append(piece)))
            await socket.send(json.dumps(build_qwen_session_finish()))
            await asyncio.wait_for(done.wait(), timeout=45.0)
        finally:
            if not reader.done():
                reader.cancel()
                try:
                    await reader
                except asyncio.CancelledError:
                    pass
            await socket.close()
        return chunks

    async def _read_events(
        self,
        socket: ClientConnection,
        chunks: list[bytes],
        created: asyncio.Event,
        updated: asyncio.Event,
        done: asyncio.Event,
    ) -> None:
        try:
            async for raw in socket:
                if isinstance(raw, (bytes, bytearray)):
                    continue
                try:
                    event = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue
                kind = str(event.get("type") or "")
                if kind == "session.created":
                    created.set()
                elif kind == "session.updated":
                    updated.set()
                elif kind == "response.audio.delta":
                    encoded = str(event.get("delta") or "")
                    if encoded:
                        try:
                            chunks.append(base64.b64decode(encoded))
                        except (binascii.Error, ValueError):
                            continue
                elif kind in ("response.done", "session.finished"):
                    done.set()
                elif kind == "error":
                    err = event.get("error")
                    detail = err.get("message") if isinstance(err, dict) else "Qwen-TTS Realtime error"
                    logger.warning("Qwen-TTS Realtime error: %s", detail)
                    updated.set()
                    done.set()
        except ConnectionClosed:
            created.set()
            updated.set()
            done.set()

    async def close(self) -> None:
        """Mark the session cancelled; speak() closes the socket."""
        self._cancel = True

    async def interrupt(self) -> None:
        """Abandon remaining audio after the current WS turn."""
        self._cancel = True
