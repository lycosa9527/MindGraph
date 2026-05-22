"""Process-local registries for Kitty voice (importable without loading HTTP routers)."""

import logging
from typing import Any, Dict, List

from fastapi import WebSocket

logger = logging.getLogger("VOICE")

voice_sessions: Dict[str, Dict[str, Any]] = {}

active_websockets: Dict[str, List[WebSocket]] = {}
