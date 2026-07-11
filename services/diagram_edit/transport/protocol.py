"""Canvas transport protocol — decouple executor from voice_sessions."""

from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class CanvasTransport(Protocol):
    """Owning-canvas session bridge for diagram edit executor."""

    def get_live_session(self, voice_session_id: str) -> Optional[Dict[str, Any]]:
        """Return live voice session row or None."""

    def get_hub_revision(self, voice_session_id: str) -> Optional[int]:
        """Return cached hub scope revision for the session."""

    def set_hub_revision(self, voice_session_id: str, revision: int) -> None:
        """Update cached hub scope revision after verified persist."""

    def stash_outbound_extras(self, voice_session_id: str, extras: Dict[str, Any]) -> None:
        """Attach WS outbound metadata (mutation_id, expected_effect) for diagram_update."""

    def pop_outbound_extras(self, voice_session_id: str) -> Optional[Dict[str, Any]]:
        """Remove and return stashed outbound extras after send."""
