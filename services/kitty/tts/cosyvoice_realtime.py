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

from config.dashscope_urls import (
    build_dashscope_headers,
    build_dashscope_inference_ws_url,
    normalize_dashscope_region,
)
from config.settings import config
from services.kitty.asr.fun_asr_realtime import resolve_dashscope_api_key
from services.kitty.tts.voice_design import cached_designed_voice_id, locate_cosyvoice_v35_voice
from services.tts.routing import default_voice_for_model
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

V3_FLASH_FALLBACK_MODEL = "cosyvoice-v3-flash"
V3_FLASH_FALLBACK_VOICE = "longyumi_v3"

# CosyVoice flash often stops a single continue-task around 20s of audio.
_TTS_CHUNK_CHARS = 90
_TTS_CHUNK_FINISH_SEC = 45.0
_SENTENCE_BREAKS = "。！？；!?…\n"


def split_cosyvoice_text(text: str) -> list[str]:
    """Split lecture captions so each CosyVoice task stays under ~20s of speech."""
    cleaned = str(text or "").strip()
    if not cleaned:
        return []
    if len(cleaned) <= _TTS_CHUNK_CHARS:
        return [cleaned]
    chunks: list[str] = []
    start = 0
    length = len(cleaned)
    while start < length:
        end = min(start + _TTS_CHUNK_CHARS, length)
        if end < length:
            window = cleaned[start:end]
            cut = max(window.rfind(mark) for mark in _SENTENCE_BREAKS)
            if cut < 24:
                cut = max(window.rfind("，"), window.rfind(","), window.rfind("、"))
            if cut >= 24:
                end = start + cut + 1
        piece = cleaned[start:end].strip()
        if piece:
            chunks.append(piece)
        start = end
    return chunks


AudioCallback = Callable[[str, str], Awaitable[None]]
DoneCallback = Callable[[], Awaitable[None]]
ErrorCallback = Callable[[str], Awaitable[None]]


def resolve_kitty_tts_enabled() -> bool:
    """``KITTY_TTS_ENABLED`` default true."""
    raw = os.getenv("KITTY_TTS_ENABLED", "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def resolve_kitty_tts_model() -> str:
    """Default ``cosyvoice-v3.5-flash``. Override via ``KITTY_TTS_MODEL``."""
    raw = os.getenv("KITTY_TTS_MODEL", "cosyvoice-v3.5-flash").strip()
    return raw or "cosyvoice-v3.5-flash"


def resolve_kitty_tts_voice() -> str:
    """Voice for the configured ``KITTY_TTS_MODEL``.

    Unset ``KITTY_TTS_VOICE`` uses the family default (YUMI, Cherry, …).
    CosyVoice v3.5 has no system voice: empty until design/locate, then the
    process-local ``mgv35f`` id.
    """
    raw = os.getenv("KITTY_TTS_VOICE", "").strip()
    if raw:
        return raw
    catalog = default_voice_for_model(resolve_kitty_tts_model())
    if catalog:
        return catalog
    return cached_designed_voice_id()


def resolve_kitty_tts_model_and_voice() -> tuple[str, str]:
    """Return (model, voice). v3.5 voice may be empty until design runs."""
    return resolve_kitty_tts_model(), resolve_kitty_tts_voice()


async def resolve_runtime_model_and_voice() -> tuple[str, str]:
    """v3.5 + designed voice, or v3-flash + YUMI when the voice cannot be located."""
    model, voice = resolve_kitty_tts_model_and_voice()
    if not model.startswith("cosyvoice-v3.5"):
        return model, voice or V3_FLASH_FALLBACK_VOICE
    located = await locate_cosyvoice_v35_voice(voice, model)
    if located:
        return model, located
    logger.warning(
        "CosyVoice v3.5 voice not found; falling back to %s + %s",
        V3_FLASH_FALLBACK_MODEL,
        V3_FLASH_FALLBACK_VOICE,
    )
    return V3_FLASH_FALLBACK_MODEL, V3_FLASH_FALLBACK_VOICE


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


def build_cosyvoice_finish_task(task_id: str, *, cancel: bool = False) -> dict[str, Any]:
    """Client ``finish-task``. ``cancel=True`` stops audio (Aliyun ``directive``)."""
    payload_input: dict[str, Any] = {"directive": "cancel"} if cancel else {}
    return {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": payload_input},
    }


class CosyVoiceRealtimeClient:
    """Reusable CosyVoice MaaS WS; one synthesis task per ``speak()``."""

    sample_rate: int = 22050

    def __init__(
        self,
        *,
        on_audio: AudioCallback,
        on_done: Optional[DoneCallback] = None,
        on_error: Optional[ErrorCallback] = None,
        model: Optional[str] = None,
        voice: Optional[str] = None,
    ) -> None:
        self._on_audio = on_audio
        self._on_done = on_done
        self._on_error = on_error
        self._pin_model = (model or "").strip()
        self._pin_voice = (voice or "").strip()
        self._ws: Optional[ClientConnection] = None
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._task_id = ""
        self._started = asyncio.Event()
        self._finished = asyncio.Event()
        self._closed = False
        self._cancel_requested = False
        self._heard_audio = False
        self._live_task_ran = False
        self._task_failed = ""

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
        headers = build_dashscope_headers(
            api_key,
            workspace_id=workspace_id,
            content_type=None,
        )
        self._closed = False
        self._ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def _release_socket(self) -> None:
        """Drop the inference socket without cancelling the current ``speak()``."""
        self._closed = True
        reader = self._reader_task
        self._reader_task = None
        socket = self._ws
        self._ws = None
        if reader is not None and not reader.done():
            reader.cancel()
            try:
                await reader
            except (asyncio.CancelledError, ConnectionClosed, ConnectionClosedError):
                pass
        if socket is not None:
            try:
                await socket.close()
            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK, OSError):
                pass
        self._closed = False

    async def speak(self, text: str) -> None:
        """Synthesize ``text`` and stream base64 PCM via ``on_audio``."""
        message = str(text or "").strip()
        if not message:
            return
        if not resolve_kitty_tts_enabled():
            return
        self._cancel_requested = False
        self._heard_audio = False
        self._live_task_ran = False
        self._task_failed = ""
        chunks = split_cosyvoice_text(message)
        for index, chunk in enumerate(chunks):
            if self._cancel_requested or self._task_failed:
                break
            await self._speak_chunk(chunk)
            if index < len(chunks) - 1 and not self._cancel_requested and not self._task_failed:
                await self._release_socket()
        if self._cancel_requested:
            return
        if self._task_failed:
            raise RuntimeError(self._task_failed)
        if self._live_task_ran and not self._heard_audio:
            raise RuntimeError("CosyVoice returned no audio")
        if self._on_done:
            await self._on_done()

    async def _speak_chunk(self, message: str) -> None:
        """One CosyVoice run-task. Flash models drop audio after ~20s per task."""
        await self.connect()
        assert self._ws is not None
        self._live_task_ran = True
        if self._pin_model:
            model, voice = self._pin_model, self._pin_voice
        else:
            model, voice = await resolve_runtime_model_and_voice()
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
            await asyncio.wait_for(self._finished.wait(), timeout=_TTS_CHUNK_FINISH_SEC)
        except asyncio.TimeoutError:
            logger.warning("CosyVoice task-finished timeout")

    async def interrupt(self) -> None:
        """Cancel in-flight synthesis."""
        self._cancel_requested = True
        if self._task_id and self._ws is not None:
            try:
                await self._send_finish(cancel=True)
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

    async def _send_finish(self, *, cancel: bool = False) -> None:
        if self._ws is None or not self._task_id:
            return
        await self._ws.send(json.dumps(build_cosyvoice_finish_task(self._task_id, cancel=cancel)))

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, (bytes, bytearray)):
                    if self._cancel_requested:
                        continue
                    encoded = base64.b64encode(bytes(message)).decode("ascii")
                    self._heard_audio = True
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
            self._task_failed = err
            self._finished.set()
            if self._on_error:
                await self._on_error(err)
            return
