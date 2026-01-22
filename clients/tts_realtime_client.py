"""
Dashscope TTS Realtime Client - Native WebSocket Implementation
================================================================

Native WebSocket client for Dashscope TTS Realtime API.
Based on official Dashscope WebSocket API documentation.

Features:
- Fully async (no threading needed)
- Stream audio chunks as text is generated
- Supports server_commit and commit modes
- Integrates with existing codebase patterns

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from enum import Enum
from typing import Optional, Callable, Dict, Any, AsyncGenerator
import asyncio
import base64
import json
import logging

import binascii
import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException




logger = logging.getLogger('TTS')


class SessionMode(str, Enum):
    """TTS session modes"""
    SERVER_COMMIT = "server_commit"  # Server handles segmentation
    COMMIT = "commit"  # Client controls segmentation


class AudioFormat(str, Enum):
    """Audio output formats"""
    PCM_24000HZ_MONO_16BIT = "pcm"  # PCM format, sample_rate specified separately
    PCM_16000HZ_MONO_16BIT = "pcm"  # PCM format, sample_rate specified separately
    PCM_8000HZ_MONO_16BIT = "pcm"   # PCM format, sample_rate specified separately
    MP3_24000HZ_MONO = "mp3"
    OPUS_24000HZ_MONO = "opus"
    WAV_24000HZ_MONO = "wav"


class TTSRealtimeClient:
    """
    Native WebSocket client for Dashscope TTS Realtime API.

    Provides full async control over TTS generation with streaming audio output.
    """

    # Base URL for Beijing region (use dashscope-intl.aliyuncs.com for Singapore)
    BASE_URL = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-tts-flash-realtime",
        voice: str = "Cherry",
        mode: SessionMode = SessionMode.SERVER_COMMIT,
        response_format: AudioFormat = AudioFormat.MP3_24000HZ_MONO,
        sample_rate: int = 24000,
        language_type: Optional[str] = None,
        # Event handlers
        on_audio_chunk: Optional[Callable[[bytes], None]] = None,
        on_session_created: Optional[Callable[[str], None]] = None,
        on_response_done: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize TTS Realtime client.

        Args:
            api_key: Dashscope API key
            model: TTS model name
            voice: Voice name (see voice list)
            mode: Session mode (server_commit or commit)
            response_format: Audio output format
            sample_rate: Sample rate in Hz (8000, 16000, 24000, or 48000)
            language_type: Language type (Auto, Chinese, English, etc.) or None for Auto
            on_audio_chunk: Callback for audio chunks (bytes)
            on_session_created: Callback when session is created
            on_response_done: Callback when response is complete
            on_error: Callback for errors
        """
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.mode = mode
        self.response_format = response_format
        self.sample_rate = sample_rate
        self.language_type = language_type

        # WebSocket connection
        self.ws = None
        self._connected = False
        self._message_handler_task = None

        # Event handlers
        self.on_audio_chunk = on_audio_chunk
        self.on_session_created = on_session_created
        self.on_response_done = on_response_done
        self.on_error = on_error

        # Session tracking
        self.session_id = None
        self._response_done_event = asyncio.Event()
        self._session_created_event = asyncio.Event()

        logger.debug("[TTS] Initialized: model=%s, voice=%s, mode=%s", model, voice, mode)

    async def connect(self):
        """Connect to TTS WebSocket server"""
        if self._connected:
            logger.warning("[TTS] Already connected")
            return

        try:
            # Build WebSocket URL with model parameter
            url = f"{self.BASE_URL}?model={self.model}"

            # Connect with API key in headers
            # Note: websockets library uses 'additional_headers' parameter
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }

            self.ws = await websockets.connect(
                url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10,
                proxy=None,  # Disable automatic proxy detection (websockets 15.0+)
            )

            self._connected = True
            logger.info("[TTS] WebSocket connected")

            # Start message handler
            self._message_handler_task = asyncio.create_task(self._handle_messages())

            # Send session.update to initialize session
            await self._update_session()

        except (OSError, ConnectionError, WebSocketException) as e:
            self._connected = False
            logger.error("[TTS] Connection error: %s", e, exc_info=True)
            raise

    async def _update_session(self):
        """Send session.update event to configure session"""
        # Build session config according to official API documentation
        # Required fields:
        # - voice: Voice name
        # - response_format: pcm, wav, mp3, or opus
        # Optional fields:
        # - mode: server_commit or commit (defaults to server_commit)
        # - sample_rate: 8000, 16000, 24000, or 48000 (required for pcm)
        # - language_type: Auto, Chinese, English, etc. (defaults to Auto)
        session_config: Dict[str, Any] = {
            "voice": self.voice,
            "response_format": self.response_format.value,
        }

        # Add mode
        if self.mode == SessionMode.SERVER_COMMIT:
            session_config["mode"] = "server_commit"
        else:
            session_config["mode"] = "commit"

        # Add sample_rate (required for pcm, optional for others)
        if self.response_format.value == "pcm":
            session_config["sample_rate"] = self.sample_rate
        elif self.sample_rate != 24000:  # Non-default sample rate
            session_config["sample_rate"] = self.sample_rate

        # Add language_type if specified
        if self.language_type:
            session_config["language_type"] = self.language_type

        event = {
            "type": "session.update",
            "session": session_config
        }

        await self._send_event(event)
        logger.debug("[TTS] Sent session.update: %s", session_config)

    async def append_text(self, text: str):
        """
        Append text to be synthesized.

        Args:
            text: Text to synthesize
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")

        # According to official API: input_text_buffer.append uses "text" field
        # In server_commit mode: server handles segmentation automatically
        # In commit mode: text is buffered until commit() is called
        event = {
            "type": "input_text_buffer.append",
            "text": text
        }

        await self._send_event(event)
        logger.debug("[TTS] Appended text: %s...", text[:50])

    async def commit_text(self):
        """Commit buffered text for synthesis (commit mode only)"""
        if self.mode != SessionMode.COMMIT:
            logger.warning("[TTS] commit_text() only works in commit mode")
            return

        event = {
            "type": "input_text_buffer.commit"
        }
        await self._send_event(event)
        logger.debug("[TTS] Committed text buffer")

    async def finish_session(self):
        """Finish the session (no more text will be sent)"""
        event = {
            "type": "session.finish"
        }
        await self._send_event(event)
        logger.debug("[TTS] Finished session")

    async def wait_for_response_done(self, timeout: float = 30.0):
        """Wait for response.done event"""
        try:
            await asyncio.wait_for(self._response_done_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("[TTS] Timeout waiting for response.done")

    async def wait_for_session_created(self, timeout: float = 10.0):
        """Wait for session.created event"""
        try:
            await asyncio.wait_for(self._session_created_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning("[TTS] Timeout waiting for session.created")

    async def _send_event(self, event: Dict[str, Any]):
        """Send event to WebSocket server"""
        if not self._connected or not self.ws:
            raise RuntimeError("Not connected")

        try:
            await self.ws.send(json.dumps(event))
        except (OSError, ConnectionError, WebSocketException) as e:
            logger.error("[TTS] Send error: %s", e, exc_info=True)
            raise

    async def _handle_messages(self):
        """Handle incoming WebSocket messages"""
        if not self.ws:
            logger.error("[TTS] WebSocket connection is None")
            return
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._process_event(data)
                except json.JSONDecodeError as e:
                    logger.error("[TTS] JSON decode error: %s", e)
                except (KeyError, ValueError, TypeError) as e:
                    logger.error("[TTS] Message processing error: %s", e, exc_info=True)
        except ConnectionClosed:
            logger.info("[TTS] WebSocket connection closed")
            self._connected = False
        except (OSError, ConnectionError, WebSocketException) as e:
            logger.error("[TTS] Message handler error: %s", e, exc_info=True)
            self._connected = False
            if self.on_error:
                self.on_error(str(e))

    async def _process_event(self, event: Dict[str, Any]):
        """Process incoming event"""
        event_type = event.get("type", "")

        if event_type == "session.created":
            self.session_id = event.get("session", {}).get("id")
            logger.info("[TTS] Session created: %s", self.session_id)
            self._session_created_event.set()
            if self.on_session_created:
                self.on_session_created(self.session_id)

        elif event_type == "session.updated":
            logger.debug("[TTS] Session updated")

        elif event_type == "response.created":
            logger.debug("[TTS] Response created")

        elif event_type == "response.audio.delta":
            # Audio chunk received (base64 encoded)
            audio_b64 = event.get("delta", "")
            if audio_b64:
                try:
                    audio_bytes = base64.b64decode(audio_b64)
                    if self.on_audio_chunk:
                        self.on_audio_chunk(audio_bytes)
                except (binascii.Error, TypeError, ValueError) as e:
                    logger.error("[TTS] Audio decode error: %s", e)

        elif event_type == "response.audio.done":
            logger.debug("[TTS] Audio generation done")

        elif event_type == "response.done":
            logger.debug("[TTS] Response done")
            self._response_done_event.set()
            if self.on_response_done:
                self.on_response_done()

        elif event_type == "session.finished":
            logger.info("[TTS] Session finished")
            self._connected = False

        elif event_type == "error":
            error_msg = event.get("error", {}).get("message", "Unknown error")
            logger.error("[TTS] Server error: %s", error_msg)
            if self.on_error:
                self.on_error(error_msg)

        else:
            logger.debug("[TTS] Unhandled event type: %s", event_type)

    async def close(self):
        """Close WebSocket connection"""
        if self._message_handler_task:
            self._message_handler_task.cancel()
            try:
                await self._message_handler_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            try:
                await self.ws.close()
            except Exception:
                pass

        self._connected = False
        logger.info("[TTS] Connection closed")

    async def synthesize_stream(
        self,
        text_chunks: AsyncGenerator[str, None],
        voice: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream TTS audio as text chunks arrive.

        Args:
            text_chunks: Async generator yielding text chunks
            voice: Voice name (overrides default)

        Yields:
            Audio chunks (bytes)
        """
        if voice:
            self.voice = voice

        # Connect if not connected
        if not self._connected:
            await self.connect()
            await self.wait_for_session_created()

        # Collect audio chunks
        audio_chunks = []

        def collect_audio(audio_bytes: bytes):
            audio_chunks.append(audio_bytes)

        self.on_audio_chunk = collect_audio

        # Stream text chunks
        async for text_chunk in text_chunks:
            await self.append_text(text_chunk)
            # Yield any audio chunks we've received
            while audio_chunks:
                yield audio_chunks.pop(0)

        # Finish session
        await self.finish_session()

        # Wait for final audio chunks
        await self.wait_for_response_done()

        # Yield remaining audio chunks
        while audio_chunks:
            yield audio_chunks.pop(0)
