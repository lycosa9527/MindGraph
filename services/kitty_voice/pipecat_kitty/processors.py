"""Pipecat processors bridging Kitty WS messages and Qwen Omni client."""

from __future__ import annotations

import logging
from typing import Any, Callable

from pipecat.frames.frames import Frame, SystemFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from services.kitty_voice.kitty_ws_inbound import (
    KittyWsInboundContext,
    dispatch_kitty_ws_inbound_message,
)
from services.kitty_voice.pipecat_kitty.frames import KittyOmniAudioB64Frame, KittyWsMessageFrame

logger = logging.getLogger(__name__)


class KittyWsMessageDispatchProcessor(FrameProcessor):
    """Runs :func:`dispatch_kitty_ws_inbound_message` for each :class:`KittyWsMessageFrame`."""

    def __init__(self, ctx: KittyWsInboundContext, **kwargs):
        super().__init__(**kwargs)
        self._ctx = ctx

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, SystemFrame):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, KittyWsMessageFrame) and direction == FrameDirection.DOWNSTREAM:
            flow = await dispatch_kitty_ws_inbound_message(self._ctx, frame.message)
            if flow == "stop":
                logger.debug(
                    "Kitty Pipecat: stop routed via pipeline (WS loop handles break separately)"
                )
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)


class KittyOmniBridgeProcessor(FrameProcessor):
    """Forwards :class:`KittyOmniAudioB64Frame` to a session-scoped Omni client."""

    def __init__(
        self,
        get_omni_client: Callable[[], Any],
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._get_omni_client = get_omni_client

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, SystemFrame):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, KittyOmniAudioB64Frame) and direction == FrameDirection.DOWNSTREAM:
            client = self._get_omni_client()
            if client is not None:
                await client.send_audio(frame.audio_b64)
            await self.push_frame(frame, direction)
            return

        await self.push_frame(frame, direction)
