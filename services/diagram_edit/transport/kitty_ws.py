"""Kitty WebSocket transport — voice_sessions backed CanvasTransport."""

from __future__ import annotations

from typing import Any, Dict, Optional

from services.kitty.session.runtime_state import voice_sessions

OUTBOUND_EXTRAS_KEY = "_diagram_edit_ws_outbound_extras"
# When set on the voice session, diagram_update payloads omit chat user_summary
# so multi-step chains can coalesce progress/done acks without per-step spam.
MULTI_STEP_SUPPRESS_DIAGRAM_CHAT_KEY = "_multi_step_suppress_diagram_chat"


def verified_edit_extras_pending(voice_session_id: str) -> bool:
    """True when diagram_edit stashed a mutation_id for client-owned Hub persist."""
    live = voice_sessions.get(voice_session_id)
    if not isinstance(live, dict):
        return False
    extras = live.get(OUTBOUND_EXTRAS_KEY)
    if not isinstance(extras, dict):
        return False
    mutation_id = extras.get("mutation_id")
    return isinstance(mutation_id, str) and bool(mutation_id.strip())


class KittyWsTransport:
    """Kitty voice session transport for diagram edit executor."""

    def get_live_session(self, voice_session_id: str) -> Optional[Dict[str, Any]]:
        """Return live voice session row or None."""
        live = voice_sessions.get(voice_session_id)
        return live if isinstance(live, dict) else None

    def get_hub_revision(self, voice_session_id: str) -> Optional[int]:
        """Return cached hub scope revision for the session."""
        live = self.get_live_session(voice_session_id)
        if live is None:
            return None
        hub_rev_raw = live.get("_hub_scope_revision")
        return hub_rev_raw if isinstance(hub_rev_raw, int) else None

    def set_hub_revision(self, voice_session_id: str, revision: int) -> None:
        """Update cached hub scope revision after verified persist."""
        live = self.get_live_session(voice_session_id)
        if live is not None:
            live["_hub_scope_revision"] = revision

    def stash_outbound_extras(self, voice_session_id: str, extras: Dict[str, Any]) -> None:
        """Attach WS outbound metadata (mutation_id, expected_effect) for diagram_update."""
        live = self.get_live_session(voice_session_id)
        if live is not None:
            live[OUTBOUND_EXTRAS_KEY] = dict(extras)

    def pop_outbound_extras(self, voice_session_id: str) -> Optional[Dict[str, Any]]:
        """Remove and return stashed outbound extras after send."""
        live = self.get_live_session(voice_session_id)
        if live is None:
            return None
        raw = live.pop(OUTBOUND_EXTRAS_KEY, None)
        return raw if isinstance(raw, dict) else None
