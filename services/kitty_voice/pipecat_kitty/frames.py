"""Pipecat frame types for MindGraph Kitty (JSON WebSocket ingress)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pipecat.frames.frames import DataFrame


@dataclass
class KittyWsMessageFrame(DataFrame):
    """One parsed client JSON object from ``/ws/kitty`` (after ``start``)."""

    message: dict[str, Any]


@dataclass
class KittyOmniAudioB64Frame(DataFrame):
    """PCM audio chunk as base64 for :class:`KittyOmniBridgeProcessor`."""

    audio_b64: str
