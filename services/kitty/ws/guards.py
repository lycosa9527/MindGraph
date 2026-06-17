"""Inbound Kitty WebSocket limits and small binary helpers (no router imports).

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import base64
import os

KITTY_WS_MAX_TEXT_CHARS = max(1024, int(os.getenv("KITTY_WS_MAX_TEXT_CHARS", "12000")))
KITTY_WS_MAX_AUDIO_B64_CHARS = max(4096, int(os.getenv("KITTY_WS_MAX_AUDIO_B64_CHARS", "65536")))
KITTY_WS_IMAGE_B64_MAX_CHARS = max(50_000, int(os.getenv("KITTY_WS_IMAGE_B64_MAX_CHARS", "900000")))
KITTY_WS_IMAGE_RAW_MAX_BYTES = max(50_000, int(os.getenv("KITTY_WS_IMAGE_RAW_MAX_BYTES", "524288")))


def pcm16_silence_base64(duration_ms: int = 200, sample_rate: int = 24000) -> str:
    """Short silence chunk so image append satisfies prior-audio requirement (Omni realtime)."""
    samples = max(1, int(sample_rate * duration_ms / 1000))
    return base64.b64encode(bytes(samples * 2)).decode("ascii")
