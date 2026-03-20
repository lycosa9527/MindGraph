"""Shared FastAPI router and in-memory voice session state."""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket

logger = logging.getLogger("VOICE")

router = APIRouter()

voice_sessions: Dict[str, Dict[str, Any]] = {}

active_websockets: Dict[str, List[WebSocket]] = {}
