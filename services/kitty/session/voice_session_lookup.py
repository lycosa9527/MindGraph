"""Direct voice session dict lookups without lifecycle side effects."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.kitty.session.runtime_state import voice_sessions


def lookup_voice_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Return the live voice session record, if present."""
    return voice_sessions.get(session_id)
