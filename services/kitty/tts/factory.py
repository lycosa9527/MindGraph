"""Create the Kitty / lecture TTS client for the configured family and mode.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
from typing import Optional, Protocol, TypeGuard, runtime_checkable

from services.kitty.tts.cosyvoice_realtime import (
    AudioCallback,
    CosyVoiceRealtimeClient,
    DoneCallback,
    ErrorCallback,
    resolve_kitty_tts_model,
    resolve_kitty_tts_voice,
    split_cosyvoice_text,
)
from services.kitty.tts.qwen_realtime_adapter import QwenRealtimeKittyTtsClient
from services.tts.facade import TtsSynthRequest, synthesize_http
from services.tts.routing import (
    MODE_HTTP,
    TtsRoute,
    resolve_tts_mode,
    resolve_tts_route,
)
from services.tts.voices.types import FAMILY_QWEN_TTS


@runtime_checkable
class KittyTtsClient(Protocol):
    """Lecture / Kitty speak surface (CosyVoice WS, Qwen-TTS WS, or HTTP)."""

    sample_rate: int

    async def speak(self, text: str) -> None:
        """Synthesize ``text`` and emit audio via the constructor callbacks."""

    async def close(self) -> None:
        """Release sockets / HTTP clients."""

    async def interrupt(self) -> None:
        """Cancel in-flight synthesis when the user barges in."""


class HttpKittyTtsClient:
    """Non-realtime HTTP synthesizer with the CosyVoice callback shape."""

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
        """HTTP (or SSE) synthesis; long captions are split like CosyVoice."""
        message = str(text or "").strip()
        if not message or self._cancel:
            return
        heard = False
        try:
            for piece in split_cosyvoice_text(message):
                if self._cancel:
                    return
                request = TtsSynthRequest(
                    text=piece,
                    model=self._route.model,
                    voice=self._voice,
                    mode=self._route.mode,
                    stream=True,
                    audio_format=self._route.audio_format,
                    sample_rate=self._route.sample_rate,
                )
                audio = await synthesize_http(request)
                if self._cancel:
                    return
                if audio:
                    heard = True
                    encoded = base64.b64encode(audio).decode("ascii")
                    await self._on_audio(encoded, self._route.audio_format)
        except RuntimeError as exc:
            if self._on_error:
                await self._on_error(str(exc))
            raise
        if not heard:
            raise RuntimeError("HTTP TTS returned no audio")
        if self._on_done and not self._cancel:
            await self._on_done()

    async def close(self) -> None:
        """HTTP client has no persistent socket."""
        self._cancel = True

    async def interrupt(self) -> None:
        """Stop emitting after the current HTTP call returns."""
        self._cancel = True


def is_kitty_tts_client(obj: object) -> TypeGuard[KittyTtsClient]:
    """True for CosyVoice realtime or the HTTP / Qwen-TTS adapters."""
    return isinstance(obj, KittyTtsClient)


def create_kitty_tts_client(
    *,
    on_audio: AudioCallback,
    on_done: Optional[DoneCallback] = None,
    on_error: Optional[ErrorCallback] = None,
    model: Optional[str] = None,
    voice: Optional[str] = None,
    mode: Optional[str] = None,
) -> KittyTtsClient:
    """Default remains CosyVoice inference WS (v3.5 + designed voice)."""
    chosen_model = (model or "").strip() or resolve_kitty_tts_model()
    chosen_mode = resolve_tts_mode(mode)
    route = resolve_tts_route(chosen_model, mode=chosen_mode)
    chosen_voice = (voice or "").strip() or resolve_kitty_tts_voice() or route.default_voice
    if route.mode == MODE_HTTP:
        return HttpKittyTtsClient(
            route=route,
            voice=chosen_voice,
            on_audio=on_audio,
            on_done=on_done,
            on_error=on_error,
        )
    if route.family == FAMILY_QWEN_TTS:
        return QwenRealtimeKittyTtsClient(
            route=route,
            voice=chosen_voice or "Cherry",
            on_audio=on_audio,
            on_done=on_done,
            on_error=on_error,
        )
    pin_model = None if route.needs_designed_voice else route.model
    pin_voice = None if route.needs_designed_voice else chosen_voice
    client = CosyVoiceRealtimeClient(
        on_audio=on_audio,
        on_done=on_done,
        on_error=on_error,
        model=pin_model,
        voice=pin_voice,
    )
    client.sample_rate = route.sample_rate
    return client
