"""CosyVoice realtime WebSocket client (MaaS inference endpoint).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Optional

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from config.settings import config
from config.dashscope_urls import build_dashscope_inference_ws_url, normalize_dashscope_region
from services.kitty.asr.fun_asr_realtime import resolve_dashscope_api_key
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

AudioCallback = Callable[[str, str], Awaitable[None]]
DoneCallback = Callable[[], Awaitable[None]]
ErrorCallback = Callable[[str], Awaitable[None]]


def resolve_kitty_tts_enabled() -> bool:
    """``KITTY_TTS_ENABLED`` default true."""
    raw = os.getenv("KITTY_TTS_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def resolve_kitty_tts_model() -> str:
    """Primary ``cosyvoice-v3.5-flash``; override via ``KITTY_TTS_MODEL``."""
    raw = os.getenv("KITTY_TTS_MODEL", "cosyvoice-v3.5-flash").strip()
    return raw or "cosyvoice-v3.5-flash"


def resolve_kitty_tts_voice() -> str:
    """
    Voice id for CosyVoice (default YUMI: ``longyumi_v3``).

    v3.5 clone/design voices can override via ``KITTY_TTS_VOICE``.
    """
    raw = os.getenv("KITTY_TTS_VOICE", "longyumi_v3").strip()
    return raw or "longyumi_v3"


def resolve_kitty_tts_model_and_voice() -> tuple[str, str]:
    """Return (model, voice); YUMI ``longyumi_v3`` is the default voice.

    When ``KITTY_TTS_MODEL`` is v3.5 and voice is still the system default,
    fall back to ``cosyvoice-v3-flash`` (v3.5 has no system voices).
    """
    model = resolve_kitty_tts_model()
    voice = resolve_kitty_tts_voice()
    voice_explicit = bool(os.getenv("KITTY_TTS_VOICE", "").strip())
    if model.startswith("cosyvoice-v3.5") and not voice_explicit:
        logger.info("KITTY_TTS_VOICE unset with v3.5 model; using cosyvoice-v3-flash + longyumi_v3 (YUMI)")
        return "cosyvoice-v3-flash", "longyumi_v3"
    return model, voice


def build_cosyvoice_run_task(
    task_id: str,
    *,
    model: str,
    voice: str,
) -> dict[str, Any]:
    """Client ``run-task`` for CosyVoice realtime (PCM 22050)."""
    return {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "tts",
            "function": "SpeechSynthesizer",
            "model": model,
            "parameters": {
                "text_type": "PlainText",
                "voice": voice,
                "format": "pcm",
                "sample_rate": 22050,
            },
            "input": {},
        },
    }


def build_cosyvoice_continue_task(task_id: str, text: str) -> dict[str, Any]:
    """Client ``continue-task`` with synthesis text."""
    return {
        "header": {
            "action": "continue-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {"text": text}},
    }


def build_cosyvoice_finish_task(task_id: str) -> dict[str, Any]:
    """Client ``finish-task`` (required)."""
    return {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {}},
    }


class CosyVoiceRealtimeClient:
    """Reusable CosyVoice MaaS WS; one synthesis task per ``speak()``."""

    def __init__(
        self,
        *,
        on_audio: AudioCallback,
        on_done: Optional[DoneCallback] = None,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self._on_audio = on_audio
        self._on_done = on_done
        self._on_error = on_error
        self._ws: Optional[ClientConnection] = None
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._task_id = ""
        self._started = asyncio.Event()
        self._finished = asyncio.Event()
        self._closed = False
        self._cancel_requested = False

    async def connect(self) -> None:
        """Open (or reuse) the inference WebSocket."""
        if self._ws is not None and not self._closed:
            return
        api_key = resolve_dashscope_api_key()
        if not api_key:
            raise RuntimeError("DashScope API key not configured for CosyVoice")
        workspace_id = config.DASHSCOPE_WORKSPACE_ID
        region = normalize_dashscope_region(str(getattr(config, "DASHSCOPE_REGION", None) or "cn-beijing"))
        if not workspace_id:
            raise RuntimeError("DASHSCOPE_WORKSPACE_ID required for CosyVoice MaaS inference")

        url = build_dashscope_inference_ws_url(workspace_id=workspace_id, region=region)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-WorkSpace": workspace_id,
        }
        self._closed = False
        self._ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def speak(self, text: str) -> None:
        """Synthesize ``text`` and stream base64 PCM via ``on_audio``."""
        message = str(text or "").strip()
        if not message:
            return
        if not resolve_kitty_tts_enabled():
            return
        self._cancel_requested = False
        await self.connect()
        assert self._ws is not None
        model, voice = resolve_kitty_tts_model_and_voice()
        self._task_id = str(uuid.uuid4())
        self._started = asyncio.Event()
        self._finished = asyncio.Event()
        await self._ws.send(json.dumps(build_cosyvoice_run_task(self._task_id, model=model, voice=voice)))
        try:
            await asyncio.wait_for(self._started.wait(), timeout=20.0)
        except asyncio.TimeoutError as exc:
            raise RuntimeError("CosyVoice task-started timeout") from exc
        if self._cancel_requested:
            await self._send_finish()
            return
        await self._ws.send(json.dumps(build_cosyvoice_continue_task(self._task_id, message)))
        await self._send_finish()
        try:
            await asyncio.wait_for(self._finished.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning("CosyVoice task-finished timeout")
        if self._on_done and not self._cancel_requested:
            await self._on_done()

    async def interrupt(self) -> None:
        """Cancel in-flight synthesis."""
        self._cancel_requested = True
        if self._task_id and self._ws is not None:
            try:
                await self._send_finish()
            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, OSError):
                pass
        self._finished.set()

    async def close(self) -> None:
        """Close WebSocket and reader."""
        self._cancel_requested = True
        self._closed = True
        self._finished.set()
        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, ConnectionClosed, ConnectionClosedError):
                pass
        self._reader_task = None
        if self._ws is not None:
            try:
                await self._ws.close()
            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, OSError):
                pass
            self._ws = None

    async def _send_finish(self) -> None:
        if self._ws is None or not self._task_id:
            return
        await self._ws.send(json.dumps(build_cosyvoice_finish_task(self._task_id)))

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, (bytes, bytearray)):
                    if self._cancel_requested:
                        continue
                    encoded = base64.b64encode(bytes(message)).decode("ascii")
                    await self._on_audio(encoded, "pcm")
                    continue
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                await self._handle_server_event(data)
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            return
        except LLM_PIPELINE_ERRORS as exc:
            logger.warning("CosyVoice read loop error: %s", exc)
            if self._on_error:
                await self._on_error(str(exc))

    async def _handle_server_event(self, data: dict[str, Any]) -> None:
        raw_header = data.get("header")
        header: dict[str, Any] = raw_header if isinstance(raw_header, dict) else {}
        event = str(header.get("event") or "")
        if event == "task-started":
            self._started.set()
            return
        if event == "task-finished":
            self._finished.set()
            return
        if event == "task-failed":
            raw_payload = data.get("payload")
            payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
            err = str(payload.get("message") or header.get("error_message") or "CosyVoice failed")
            self._finished.set()
            if self._on_error:
                await self._on_error(err)
            return
