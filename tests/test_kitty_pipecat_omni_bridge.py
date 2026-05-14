"""Tests for Kitty Pipecat helpers (lightweight; no full pipeline)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pipecat.processors.frame_processor import FrameDirection

from services.kitty_voice.pipecat_kitty.frames import KittyOmniAudioB64Frame
from services.kitty_voice.pipecat_kitty.processors import KittyOmniBridgeProcessor


@pytest.mark.asyncio
async def test_kitty_omni_bridge_forwards_audio_b64():
    omni = MagicMock()
    omni.send_audio = AsyncMock()
    proc = KittyOmniBridgeProcessor(lambda: omni, name="test-bridge", enable_direct_mode=True)
    proc._clock = MagicMock()
    proc._task_manager = MagicMock()
    proc._observer = None
    push_mock = AsyncMock()
    proc.push_frame = push_mock

    frame = KittyOmniAudioB64Frame(audio_b64="abcd")
    await proc.process_frame(frame, FrameDirection.DOWNSTREAM)
    omni.send_audio.assert_awaited_once_with("abcd")


def test_kitty_omni_audio_frame_dataclass():
    frame = KittyOmniAudioB64Frame(audio_b64="qq==")
    assert "KittyOmniAudioB64Frame" in frame.name
