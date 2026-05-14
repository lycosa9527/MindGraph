"""Inbound Kitty WebSocket limits and small binary helpers (no router imports)."""

from __future__ import annotations

import base64
import os
from typing import Any, Dict

from config.settings import config
from models.domain.auth import User
from utils.auth import user_has_feature_access

KITTY_WS_MAX_TEXT_CHARS = max(1024, int(os.getenv("KITTY_WS_MAX_TEXT_CHARS", "12000")))
KITTY_WS_MAX_AUDIO_B64_CHARS = max(4096, int(os.getenv("KITTY_WS_MAX_AUDIO_B64_CHARS", "65536")))
KITTY_WS_IMAGE_B64_MAX_CHARS = max(50_000, int(os.getenv("KITTY_WS_IMAGE_B64_MAX_CHARS", "900000")))
KITTY_WS_IMAGE_RAW_MAX_BYTES = max(50_000, int(os.getenv("KITTY_WS_IMAGE_RAW_MAX_BYTES", "524288")))

KITTY_MOBILE_BOOTSTRAP_DISABLED_BODY: Dict[str, Any] = {
    "recommended_scope": None,
    "desktop_focus": {"diagram_library_id": None, "updated_at": None},
    "context": {
        "diagram_data": {},
        "selected_nodes": [],
        "diagram_type": "circle_map",
    },
    "diagram_type": "circle_map",
    "active_panel": "none",
    "source": "empty",
}


async def kitty_http_allowed(current_user: User) -> bool:
    """Respects ``FEATURE_KITTY_AGENT`` (.env) and optional ``feature_kitty_agent`` org grants."""
    if not config.FEATURE_KITTY_WS_ENABLED:
        return False
    return await user_has_feature_access(current_user, "feature_kitty_agent")


def pcm16_silence_base64(duration_ms: int = 200, sample_rate: int = 24000) -> str:
    """Short silence chunk so image append satisfies prior-audio requirement (Omni realtime)."""
    samples = max(1, int(sample_rate * duration_ms / 1000))
    return base64.b64encode(bytes(samples * 2)).decode("ascii")
