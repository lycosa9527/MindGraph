"""Read OmniClient handles from in-memory voice sessions (no ops import cycle)."""

from __future__ import annotations

from typing import Any

from services.kitty.session.runtime_state import logger, voice_sessions


def get_session_omni_client(voice_session_id: str) -> Any:
    """
    Return the OmniClient for a voice session, or ``None`` if missing.

    Each voice session owns an isolated OmniClient instance for concurrent users.
    """
    session = voice_sessions.get(voice_session_id)
    if not session:
        logger.warning("Voice session %s not found", voice_session_id)
        return None

    omni_client = session.get("omni_client")
    if not omni_client:
        logger.warning("OmniClient not found for session %s", voice_session_id)
        return None

    return omni_client
