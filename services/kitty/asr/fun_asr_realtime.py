"""Fun-ASR realtime WebSocket client (MaaS inference endpoint).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from typing import Any, Awaitable, Callable, Optional

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, ConnectionClosedOK

from config.dashscope_urls import build_dashscope_inference_ws_url, normalize_dashscope_region
from config.settings import config
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

PartialCallback = Callable[[str, bool], Awaitable[None]]
ErrorCallback = Callable[[str], Awaitable[None]]


def resolve_kitty_asr_model() -> str:
    """``KITTY_ASR_MODEL`` default ``fun-asr-realtime``."""
    raw = os.getenv("KITTY_ASR_MODEL", "fun-asr-realtime").strip()
    return raw or "fun-asr-realtime"


def resolve_dashscope_api_key() -> Optional[str]:
    """Prefer ``DASHSCOPE_API_KEY``, then ``QWEN_API_KEY``."""
    for candidate in (config.DASHSCOPE_API_KEY, config.QWEN_API_KEY):
        if not candidate:
            continue
        stripped = str(candidate).strip()
        if stripped:
            return stripped
    return None


def build_fun_asr_run_task(
    task_id: str,
    *,
    model: str,
    language_hints: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Client ``run-task`` for Fun-ASR realtime (PCM 16 kHz)."""
    parameters: dict[str, Any] = {
        "format": "pcm",
        "sample_rate": 16000,
        "semantic_punctuation_enabled": False,
    }
    if language_hints:
        parameters["language_hints"] = language_hints
    return {
        "header": {
            "action": "run-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {
            "task_group": "audio",
            "task": "asr",
            "function": "recognition",
            "model": model,
            "parameters": parameters,
            "input": {},
        },
    }


def build_fun_asr_finish_task(task_id: str) -> dict[str, Any]:
    """Client ``finish-task``."""
    return {
        "header": {
            "action": "finish-task",
            "task_id": task_id,
            "streaming": "duplex",
        },
        "payload": {"input": {}},
    }


def _extract_asr_text(payload: dict[str, Any]) -> tuple[str, bool]:
    """Return (text, sentence_end) from a ``result-generated`` payload."""
    raw_output = payload.get("output")
    output: dict[str, Any] = raw_output if isinstance(raw_output, dict) else {}
    raw_sentence = output.get("sentence")
    sentence: dict[str, Any] = raw_sentence if isinstance(raw_sentence, dict) else {}
    text = str(sentence.get("text") or output.get("text") or "").strip()
    sentence_end = bool(sentence.get("sentence_end") or output.get("sentence_end"))
    return text, sentence_end


class FunAsrRealtimeClient:
    """One Fun-ASR task per mic session; tear down on stop / error."""

    def __init__(
        self,
        *,
        on_partial: PartialCallback,
        on_error: Optional[ErrorCallback] = None,
        language_hints: Optional[list[str]] = None,
    ) -> None:
        self._on_partial = on_partial
        self._on_error = on_error
        self._language_hints = language_hints
        self._ws: Optional[ClientConnection] = None
        self._task_id = ""
        self._reader_task: Optional[asyncio.Task[None]] = None
        self._started = asyncio.Event()
        self._task_finished = asyncio.Event()
        self._closed = False
        self._last_text = ""
        self._emitted_sentence_end = False
        self._error_notified = False

    @property
    def task_id(self) -> str:
        """Active DashScope task id."""
        return self._task_id

    @property
    def last_text(self) -> str:
        """Most recent non-empty ASR transcript for this mic session."""
        return self._last_text

    async def start(self) -> None:
        """Connect, send run-task, wait for task-started."""
        api_key = resolve_dashscope_api_key()
        if not api_key:
            raise RuntimeError("DashScope API key not configured for Fun-ASR")

        workspace_id = config.DASHSCOPE_WORKSPACE_ID
        region = normalize_dashscope_region(str(getattr(config, "DASHSCOPE_REGION", None) or "cn-beijing"))
        if not workspace_id:
            raise RuntimeError("DASHSCOPE_WORKSPACE_ID required for Fun-ASR MaaS inference")

        url = build_dashscope_inference_ws_url(workspace_id=workspace_id, region=region)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "X-DashScope-WorkSpace": workspace_id,
        }
        self._task_id = str(uuid.uuid4())
        self._ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=8 * 1024 * 1024,
        )
        model = resolve_kitty_asr_model()
        await self._ws.send(
            json.dumps(
                build_fun_asr_run_task(
                    self._task_id,
                    model=model,
                    language_hints=self._language_hints,
                )
            )
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        try:
            await asyncio.wait_for(self._started.wait(), timeout=20.0)
        except asyncio.TimeoutError as exc:
            await self.close()
            raise RuntimeError("Fun-ASR task-started timeout") from exc

    async def send_pcm(self, pcm: bytes) -> None:
        """Forward binary PCM frames to Fun-ASR."""
        if self._closed or self._ws is None or not pcm:
            return
        try:
            await self._ws.send(pcm)
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as exc:
            logger.debug("Fun-ASR WS closed while sending PCM: %s", exc)
            await self._emit_provider_disconnect("Fun-ASR connection closed while sending audio")

    async def finish(self) -> None:
        """Send finish-task, wait for final transcript, then tear down.

        PTT release must not cancel the reader before DashScope emits the last
        ``result-generated`` / ``task-finished`` — otherwise FE never gets
        ``asr_final`` and Mobile Kitty never sends the edit.
        """
        if self._closed or self._ws is None or not self._task_id:
            await self.close()
            return
        try:
            await self._ws.send(json.dumps(build_fun_asr_finish_task(self._task_id)))
            try:
                await asyncio.wait_for(self._task_finished.wait(), timeout=2.5)
            except asyncio.TimeoutError:
                logger.debug("Fun-ASR finish wait timed out task_id=%s", self._task_id)
            if self._last_text and not self._emitted_sentence_end:
                await self._on_partial(self._last_text, True)
                self._emitted_sentence_end = True
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            if self._last_text and not self._emitted_sentence_end:
                try:
                    await self._on_partial(self._last_text, True)
                    self._emitted_sentence_end = True
                except LLM_PIPELINE_ERRORS as exc:
                    logger.debug("Fun-ASR promote last text after close: %s", exc)
        finally:
            await self.close()

    async def close(self) -> None:
        """Tear down reader + WebSocket with short timeouts (DashScope close can hang ~10s)."""
        if self._closed:
            return
        self._closed = True
        self._task_finished.set()
        reader = self._reader_task
        self._reader_task = None
        if reader is not None and not reader.done():
            reader.cancel()
            try:
                await asyncio.wait_for(reader, timeout=0.5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                pass
            except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
                pass
        ws_conn = self._ws
        self._ws = None
        if ws_conn is not None:
            try:
                await asyncio.wait_for(ws_conn.close(), timeout=0.5)
            except (
                asyncio.TimeoutError,
                ConnectionClosed,
                ConnectionClosedError,
                ConnectionClosedOK,
                OSError,
            ):
                pass

    async def _emit_provider_disconnect(self, message: str) -> None:
        """Surface unexpected provider close/send failures to the matching utterance."""
        if self._closed or self._error_notified:
            return
        self._error_notified = True
        self._task_finished.set()
        if self._on_error:
            try:
                await self._on_error(message)
            except LLM_PIPELINE_ERRORS as exc:
                logger.debug("Fun-ASR on_error callback failed: %s", exc)

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    continue
                try:
                    data = json.loads(message)
                except json.JSONDecodeError:
                    continue
                await self._handle_server_event(data)
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as exc:
            if not self._closed and not self._task_finished.is_set():
                logger.warning("Fun-ASR provider disconnected: %s", exc)
                await self._emit_provider_disconnect(
                    "Fun-ASR provider disconnected before task finished"
                )
            return
        except LLM_PIPELINE_ERRORS as exc:
            logger.warning("Fun-ASR read loop error: %s", exc)
            if self._on_error and not self._error_notified:
                self._error_notified = True
                await self._on_error(str(exc))
        finally:
            self._task_finished.set()

    async def _handle_server_event(self, data: dict[str, Any]) -> None:
        raw_header = data.get("header")
        header: dict[str, Any] = raw_header if isinstance(raw_header, dict) else {}
        event = str(header.get("event") or "")
        if event == "task-started":
            self._started.set()
            return
        if event == "result-generated":
            raw_payload = data.get("payload")
            payload: dict[str, Any] = raw_payload if isinstance(raw_payload, dict) else {}
            text, sentence_end = _extract_asr_text(payload)
            if text:
                self._last_text = text
                if sentence_end:
                    self._emitted_sentence_end = True
                await self._on_partial(text, sentence_end)
            return
        if event == "task-failed":
            raw_payload = data.get("payload")
            payload = raw_payload if isinstance(raw_payload, dict) else {}
            err = str(payload.get("message") or header.get("error_message") or "Fun-ASR failed")
            self._task_finished.set()
            if self._on_error and not self._error_notified:
                self._error_notified = True
                await self._on_error(err)
            return
        if event == "task-finished":
            self._task_finished.set()
            return
