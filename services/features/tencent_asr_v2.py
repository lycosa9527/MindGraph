"""Tencent Cloud realtime ASR V2 (WebSocket) for Voice Notes.

Contract: https://cloud.tencent.com/document/api/1093/131127
Engine catalog: https://cloud.tencent.com/document/product/1093/35682
Signature: HMAC-SHA1 of ``asr.cloud.tencent.com/asr/v2/<appid>?{sorted params}``
(no ``wss://``), Base64, then URL-encode ``+`` / ``=``.

Realtime 大模型2.0 engines on 35682: ``16k_zh_en_2.0`` and
``16k_zh_en_speaker_2.0`` (话者分离 is on by default for the speaker SKU).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, List, Optional
from urllib.parse import quote

import websockets
from websockets.asyncio.client import ClientConnection
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
    InvalidHandshake,
    InvalidURI,
)

from services.features.tencent_asr_v2_errors import (
    TencentAsrClassifiedError,
    TencentAsrHandshakeError,
    classify_tencent_asr_error,
    format_tencent_asr_v2_log,
    tencent_asr_connect_error,
    tencent_asr_upstream_error,
)
from services.features.tencent_asr_v2_sentences import (
    TencentAsrSentence,
    TencentAsrTranscriptStore,
    normalize_speaker_context_id,
    parse_speaker_context_id,
    parse_tencent_asr_sentences,
)
from services.utils.error_types import LLM_PIPELINE_ERRORS

logger = logging.getLogger(__name__)

TENCENT_ASR_HOST = "asr.cloud.tencent.com"
TENCENT_ASR_PATH_PREFIX = "/asr/v2/"
TENCENT_ASR_ENGINE_DEFAULT = "16k_zh_en_2.0"
TENCENT_ASR_ENGINE_SPEAKER = "16k_zh_en_speaker_2.0"
TENCENT_ASR_ENGINE_SPEAKER_FALLBACK = "16k_zh_en_speaker"
# 200 ms of 16 kHz 16-bit mono PCM — Tencent 1:1 realtime hint.
KEEPALIVE_PCM_BYTES = bytes(6400)
KEEPALIVE_INTERVAL_S = 1.5
HANDSHAKE_TIMEOUT_S = 15.0
CONNECT_ATTEMPTS = 2
CONNECT_RETRY_BACKOFF_S = 0.5
FINISH_TIMEOUT_S = 5.0
TENCENT_ASR_CONNECT_ERRORS = (OSError, InvalidHandshake, InvalidURI)

SnapshotCallback = Callable[[List[TencentAsrSentence]], Awaitable[None]]
ErrorCallback = Callable[[TencentAsrClassifiedError], Awaitable[None]]


@dataclass(frozen=True)
class TencentAsrCredentials:
    """CAM account AppID + API key pair for ASR V2."""

    app_id: str
    secret_id: str
    secret_key: str


@dataclass(frozen=True)
class TencentAsrHandshake:
    """Per-connection V2 query fields (new ``voice_id`` every socket)."""

    engine_model_type: str
    voice_id: str
    timestamp: int
    expired: int
    nonce: int
    speaker_diarization: bool = False
    speaker_context_id: str = ""


@dataclass
class _TencentAsrRuntime:
    """Mutable socket/lifecycle holder for one V2 session."""

    ws: Optional[ClientConnection] = None
    bg_tasks: list[asyncio.Task[None]] = field(default_factory=list)
    finished: asyncio.Event = field(default_factory=asyncio.Event)
    closed: bool = False
    finishing: bool = False
    error_notified: bool = False
    last_send_at: float = 0.0


def load_tencent_asr_credentials() -> TencentAsrCredentials:
    """Account AppID from TENCENT_ASR_APP_ID; SecretId/Key reuse the SMS CAM pair."""
    app_id = os.getenv("TENCENT_ASR_APP_ID", "").strip()
    secret_id = os.getenv("TENCENT_ASR_SECRET_ID", "").strip() or os.getenv("TENCENT_SMS_SECRET_ID", "").strip()
    secret_key = os.getenv("TENCENT_ASR_SECRET_KEY", "").strip() or os.getenv("TENCENT_SMS_SECRET_KEY", "").strip()
    if not app_id or not secret_id or not secret_key:
        raise RuntimeError("Tencent ASR is not configured (TENCENT_ASR_APP_ID plus SecretId/SecretKey)")
    return TencentAsrCredentials(app_id=app_id, secret_id=secret_id, secret_key=secret_key)


def resolve_tencent_asr_engine(*, speaker_diarization: bool) -> str:
    """35682 大模型2.0: speaker SKU when diarization is on, else 16k_zh_en_2.0."""
    if speaker_diarization:
        raw = os.getenv("TENCENT_ASR_SPEAKER_ENGINE", TENCENT_ASR_ENGINE_SPEAKER).strip()
        return raw or TENCENT_ASR_ENGINE_SPEAKER
    raw = os.getenv("TENCENT_ASR_ENGINE", TENCENT_ASR_ENGINE_DEFAULT).strip()
    return raw or TENCENT_ASR_ENGINE_DEFAULT


def speaker_engine_candidates(*, speaker_diarization: bool) -> tuple[str, ...]:
    """Prefer 16k_zh_en_speaker_2.0; some accounts only have 16k_zh_en_speaker."""
    primary = resolve_tencent_asr_engine(speaker_diarization=speaker_diarization)
    if not speaker_diarization:
        return (primary,)
    raw = os.getenv(
        "TENCENT_ASR_SPEAKER_ENGINE_FALLBACK",
        TENCENT_ASR_ENGINE_SPEAKER_FALLBACK,
    ).strip()
    fallback = raw or TENCENT_ASR_ENGINE_SPEAKER_FALLBACK
    if fallback == primary:
        return (primary,)
    return (primary, fallback)


def is_tencent_unsupported_engine(classified: TencentAsrClassifiedError) -> bool:
    """4001 ``Not support [engine_model_type: …]`` — try the next speaker SKU."""
    if classified.provider_code != "4001":
        return False
    compact = classified.message.replace(" ", "").lower()
    return "notsupport" in compact and "engine_model_type" in compact


def sign_tencent_asr_v2(sign_plain: str, secret_key: str) -> str:
    """HMAC-SHA1 + Base64 (not yet URL-encoded)."""
    digest = hmac.new(secret_key.encode("utf-8"), sign_plain.encode("utf-8"), hashlib.sha1).digest()
    return base64.b64encode(digest).decode("ascii")


def build_tencent_asr_v2_query_params(
    secret_id: str,
    handshake: TencentAsrHandshake,
) -> dict[str, str]:
    """Handshake query without ``signature``. ``result_mod=1`` forces sentence snapshots."""
    params = {
        "convert_num_mode": "1",
        "engine_model_type": handshake.engine_model_type,
        "expired": str(handshake.expired),
        "needvad": "1",
        "nonce": str(handshake.nonce),
        "result_mod": "1",
        "secretid": secret_id,
        "sentence_strategy": "1",
        "timestamp": str(handshake.timestamp),
        "voice_format": "1",
        "voice_id": handshake.voice_id,
    }
    if handshake.speaker_diarization:
        if handshake.engine_model_type != TENCENT_ASR_ENGINE_SPEAKER:
            params["speaker_diarization"] = "1"
        params["enable_speaker_context"] = "1"
        context_id = normalize_speaker_context_id(handshake.speaker_context_id)
        if context_id:
            params["speaker_context_id"] = context_id
    return params


def format_tencent_asr_v2_sign_plain(app_id: str, params: dict[str, str]) -> str:
    """Signature source: host + path + sorted query (no ``wss://``, no signature)."""
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    return f"{TENCENT_ASR_HOST}{TENCENT_ASR_PATH_PREFIX}{app_id}?{query}"


def build_tencent_asr_v2_signed_url(
    credentials: TencentAsrCredentials,
    handshake: TencentAsrHandshake,
) -> str:
    """Full ``wss://`` URL with URL-encoded signature."""
    params = build_tencent_asr_v2_query_params(credentials.secret_id, handshake)
    sign_plain = format_tencent_asr_v2_sign_plain(credentials.app_id, params)
    signature = sign_tencent_asr_v2(sign_plain, credentials.secret_key)
    query = "&".join(f"{key}={params[key]}" for key in sorted(params))
    encoded_sig = quote(signature, safe="")
    return f"wss://{TENCENT_ASR_HOST}{TENCENT_ASR_PATH_PREFIX}{credentials.app_id}?{query}&signature={encoded_sig}"


def _int_field(raw: Any, default: int) -> int:
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def _new_tencent_asr_handshake(
    *,
    speaker_diarization: bool,
    speaker_context_id: str = "",
    engine_model_type: str = "",
) -> TencentAsrHandshake:
    now = int(time.time())
    engine = engine_model_type.strip() or resolve_tencent_asr_engine(speaker_diarization=speaker_diarization)
    return TencentAsrHandshake(
        engine_model_type=engine,
        voice_id=str(uuid.uuid4()),
        timestamp=now,
        expired=now + 24 * 60 * 60,
        nonce=secrets.randbelow(2_147_483_647) + 1,
        speaker_diarization=speaker_diarization,
        speaker_context_id=normalize_speaker_context_id(speaker_context_id),
    )


async def connect_tencent_asr_v2(
    credentials: TencentAsrCredentials,
    *,
    speaker_diarization: bool,
    speaker_context_id: str = "",
    engine_model_type: str = "",
) -> tuple[ClientConnection, str]:
    """Open the signed V2 socket. Retry once on opening-handshake timeout."""
    last_error: Optional[BaseException] = None
    for attempt in range(CONNECT_ATTEMPTS):
        handshake = _new_tencent_asr_handshake(
            speaker_diarization=speaker_diarization,
            speaker_context_id=speaker_context_id,
            engine_model_type=engine_model_type,
        )
        url = build_tencent_asr_v2_signed_url(credentials, handshake)
        try:
            socket = await websockets.connect(
                url,
                max_size=8 * 1024 * 1024,
                open_timeout=HANDSHAKE_TIMEOUT_S,
            )
        except TENCENT_ASR_CONNECT_ERRORS as exc:
            last_error = exc
            classified = tencent_asr_connect_error(str(exc))
            logger.warning(
                "%s attempt=%s/%s",
                format_tencent_asr_v2_log(
                    classified,
                    voice_id=handshake.voice_id,
                    phase="opening_handshake",
                ),
                attempt + 1,
                CONNECT_ATTEMPTS,
            )
            if attempt + 1 < CONNECT_ATTEMPTS:
                await asyncio.sleep(CONNECT_RETRY_BACKOFF_S * (attempt + 1))
            continue
        return socket, handshake.voice_id
    detail = str(last_error) if last_error is not None else "opening handshake timed out"
    raise TencentAsrHandshakeError(tencent_asr_connect_error(detail))


class TencentAsrV2Client:
    """One Tencent V2 connection per Voice Notes capture session."""

    def __init__(
        self,
        *,
        on_snapshot: SnapshotCallback,
        on_error: Optional[ErrorCallback] = None,
        speaker_diarization: bool = False,
        speaker_context_id: str = "",
    ) -> None:
        self._on_snapshot = on_snapshot
        self._on_error = on_error
        self._speaker_diarization = bool(speaker_diarization)
        self._runtime = _TencentAsrRuntime()
        self._transcript = TencentAsrTranscriptStore()
        self.voice_id = ""
        self.speaker_context_id = parse_speaker_context_id({"speaker_context_id": speaker_context_id})

    async def start(self) -> None:
        """Sign, connect (one retry), wait for handshake ``code=0``."""
        credentials = load_tencent_asr_credentials()
        engines = speaker_engine_candidates(speaker_diarization=self._speaker_diarization)
        last_error: Optional[TencentAsrHandshakeError] = None
        for index, engine in enumerate(engines):
            self._runtime = _TencentAsrRuntime()
            try:
                await self._start_engine(credentials, engine)
                return
            except TencentAsrHandshakeError as exc:
                last_error = exc
                await self.close()
                if index + 1 >= len(engines) or not is_tencent_unsupported_engine(exc.classified):
                    raise
                logger.warning(
                    "Tencent ASR engine %s rejected; retrying %s",
                    engine,
                    engines[index + 1],
                )
        if last_error is not None:
            raise last_error
        raise TencentAsrHandshakeError(tencent_asr_connect_error("Tencent ASR handshake failed"))

    async def _start_engine(
        self,
        credentials: TencentAsrCredentials,
        engine_model_type: str,
    ) -> None:
        runtime = self._runtime
        runtime.ws, self.voice_id = await connect_tencent_asr_v2(
            credentials,
            speaker_diarization=self._speaker_diarization,
            speaker_context_id=self.speaker_context_id,
            engine_model_type=engine_model_type,
        )
        try:
            raw = await asyncio.wait_for(runtime.ws.recv(), timeout=HANDSHAKE_TIMEOUT_S)
        except (TimeoutError, ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as exc:
            classified = tencent_asr_connect_error("Tencent ASR did not send a handshake frame")
            logger.warning(
                "%s",
                format_tencent_asr_v2_log(
                    classified,
                    voice_id=self.voice_id,
                    phase="handshake",
                ),
            )
            raise TencentAsrHandshakeError(classified) from exc
        handshake = _parse_tencent_json(raw)
        self._remember_speaker_context(handshake)
        code = _int_field(handshake.get("code"), -1)
        if code != 0:
            classified = classify_tencent_asr_error(handshake)
            logger.warning(
                "%s",
                format_tencent_asr_v2_log(
                    classified,
                    voice_id=self.voice_id,
                    phase="handshake",
                ),
            )
            raise TencentAsrHandshakeError(classified)
        runtime.last_send_at = time.monotonic()
        runtime.bg_tasks = [
            asyncio.create_task(self._read_loop()),
            asyncio.create_task(self._keepalive_loop()),
        ]

    async def send_pcm(self, pcm: bytes) -> None:
        """Forward binary PCM (voice_format=1)."""
        runtime = self._runtime
        if runtime.closed or runtime.finishing or runtime.ws is None or not pcm:
            return
        try:
            await runtime.ws.send(pcm)
            runtime.last_send_at = time.monotonic()
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as exc:
            logger.debug("Tencent ASR WS closed while sending PCM: %s", exc)
            await self._emit_provider_disconnect(
                tencent_asr_upstream_error("Tencent ASR connection closed while sending audio")
            )

    async def finish(self) -> None:
        """Send ``{"type":"end"}`` and wait for ``final=1``."""
        runtime = self._runtime
        if runtime.closed or runtime.ws is None:
            await self.close()
            return
        runtime.finishing = True
        try:
            await runtime.ws.send(json.dumps({"type": "end"}))
            try:
                await asyncio.wait_for(runtime.finished.wait(), timeout=FINISH_TIMEOUT_S)
            except asyncio.TimeoutError:
                logger.debug("Tencent ASR finish wait timed out voice_id=%s", self.voice_id)
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            pass
        finally:
            await self.close()

    async def close(self) -> None:
        """Cancel reader/keepalive and close the socket."""
        runtime = self._runtime
        if runtime.closed:
            return
        runtime.closed = True
        runtime.finishing = True
        runtime.finished.set()
        pending = list(runtime.bg_tasks)
        runtime.bg_tasks = []
        for task in pending:
            await self._cancel_task(task)
        ws_conn = runtime.ws
        runtime.ws = None
        if ws_conn is None:
            return
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

    async def _cancel_task(self, task: Optional[asyncio.Task[None]]) -> None:
        if task is None or task.done():
            return
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=0.5)
        except (asyncio.TimeoutError, asyncio.CancelledError):
            pass
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK):
            pass

    async def _keepalive_loop(self) -> None:
        """Silence frames so pause does not trip Tencent's 6s / 15s idle disconnect."""
        runtime = self._runtime
        try:
            while not runtime.closed and not runtime.finishing:
                await asyncio.sleep(KEEPALIVE_INTERVAL_S)
                if runtime.closed or runtime.finishing:
                    return
                if time.monotonic() - runtime.last_send_at < KEEPALIVE_INTERVAL_S:
                    continue
                await self.send_pcm(KEEPALIVE_PCM_BYTES)
        except asyncio.CancelledError:
            return
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("Tencent ASR keepalive stopped: %s", exc)

    async def _emit_provider_disconnect(self, classified: TencentAsrClassifiedError) -> None:
        runtime = self._runtime
        if runtime.closed or runtime.error_notified:
            return
        runtime.error_notified = True
        runtime.finished.set()
        if self._on_error is None:
            return
        try:
            await self._on_error(classified)
        except LLM_PIPELINE_ERRORS as exc:
            logger.debug("Tencent ASR on_error callback failed: %s", exc)

    async def _read_loop(self) -> None:
        runtime = self._runtime
        ws_conn = runtime.ws
        if ws_conn is None:
            runtime.finished.set()
            return
        try:
            async for message in ws_conn:
                if isinstance(message, bytes):
                    continue
                data = _parse_tencent_json(message)
                if not data:
                    continue
                await self._handle_server_event(data)
        except (ConnectionClosed, ConnectionClosedError, ConnectionClosedOK) as exc:
            if not runtime.closed and not runtime.finished.is_set():
                classified = tencent_asr_connect_error(str(exc))
                logger.warning(
                    "%s",
                    format_tencent_asr_v2_log(
                        classified,
                        voice_id=self.voice_id,
                        phase="provider_disconnect",
                    ),
                )
                await self._emit_provider_disconnect(classified)
        except LLM_PIPELINE_ERRORS as exc:
            classified = tencent_asr_upstream_error(str(exc))
            logger.warning(
                "%s",
                format_tencent_asr_v2_log(
                    classified,
                    voice_id=self.voice_id,
                    phase="read_loop",
                ),
            )
            if self._on_error and not runtime.error_notified:
                runtime.error_notified = True
                await self._on_error(classified)
        finally:
            runtime.finished.set()

    async def _handle_server_event(self, data: dict[str, Any]) -> None:
        runtime = self._runtime
        code = _int_field(data.get("code"), 0)
        if code != 0:
            if code == 4009 and runtime.finishing:
                runtime.finished.set()
                return
            classified = classify_tencent_asr_error(data)
            logger.warning(
                "%s",
                format_tencent_asr_v2_log(
                    classified,
                    voice_id=str(data.get("voice_id") or self.voice_id),
                    phase="recognition",
                ),
            )
            runtime.finished.set()
            if self._on_error and not runtime.error_notified:
                runtime.error_notified = True
                await self._on_error(classified)
            return
        self._remember_speaker_context(data)
        if _int_field(data.get("final"), 0) == 1:
            ordered = self._transcript.commit_live()
            if ordered:
                await self._on_snapshot(ordered)
            runtime.finished.set()
            return
        incoming = parse_tencent_asr_sentences(data)
        if not incoming:
            return
        await self._on_snapshot(self._transcript.apply(incoming))

    def _remember_speaker_context(self, data: dict[str, Any]) -> None:
        context_id = parse_speaker_context_id(data)
        if context_id:
            self.speaker_context_id = context_id


def _parse_tencent_json(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}
