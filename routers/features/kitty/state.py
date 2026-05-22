"""Shared FastAPI router and in-memory voice session state."""

from fastapi import APIRouter

from services.kitty.session.runtime_state import active_websockets, logger, voice_sessions

router = APIRouter()

__all__ = [
    "active_websockets",
    "logger",
    "router",
    "voice_sessions",
]
