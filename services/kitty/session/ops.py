"""Voice session lifecycle and Omni client accessors."""

import asyncio
import copy
import uuid
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, cast

from clients.omni_client import OmniClient
from services.agent_hub.scope_lifecycle import (
    configure_kitty_control_state,
    configure_kitty_scope_cleanup,
)
from services.kitty.infra.redis.kitty_session_redis import configure_voice_session_getter
from services.kitty.session.agent_state import kitty_agent_manager
from services.kitty.session.omni_client_access import get_session_omni_client as _get_session_omni_client_impl
from services.kitty.session.runtime_state import active_websockets, logger, voice_sessions
from services.kitty.session.session_teardown import teardown_session_event_handlers


def get_agent_session_id(voice_session_id: str) -> str:
    """
    Get the agent session ID scoped to diagram_session_id.

    CRITICAL: Voice agent sessions must be scoped to diagram_session_id, not voice_session_id.
    This ensures:
    - One agent per diagram session (not per WebSocket connection)
    - Proper cleanup when switching diagrams
    - No cross-contamination between diagram sessions

    Args:
        voice_session_id: The voice session ID (WebSocket connection identifier)

    Returns:
        Agent session ID (scoped to diagram_session_id)
    """
    if voice_session_id in voice_sessions:
        diagram_session_id = voice_sessions[voice_session_id].get("diagram_session_id")
        if diagram_session_id:
            return f"diagram_{diagram_session_id}"

    # Fallback: use voice_session_id if diagram_session_id not available (shouldn't happen)
    logger.warning(
        "Voice session %s has no diagram_session_id, using voice_session_id as fallback",
        voice_session_id,
    )
    return voice_session_id


def create_voice_session(
    user_id: str,
    diagram_session_id: Optional[str] = None,
    diagram_type: Optional[str] = None,
    active_panel: Optional[str] = None,
) -> str:
    """
    Create new voice session (session-bound to diagram session).

    CRITICAL: Creates a NEW OmniClient instance for this session to support
    multiple concurrent users. Each voice session gets its own OmniClient,
    preventing cross-contamination between users.

    Kitty Agent session lifecycle is controlled by:
    1. Black cat click (activation)
    2. Black cat click again (deactivation)
    3. Session manager cleanup (when diagram session ends)
    4. Navigation to gallery (session manager triggers cleanup)
    """
    ensure_kitty_hub_wired()
    session_id = f"voice_{uuid.uuid4().hex[:12]}"

    # CRITICAL: Create a NEW OmniClient instance for this voice session
    # This ensures each user gets their own isolated Omni conversation
    # Without this, multiple users would share the same OmniClient singleton,
    # causing cross-contamination (User A's messages going to User B's conversation)
    omni_client = OmniClient()

    voice_sessions[session_id] = {
        "session_id": session_id,
        "user_id": user_id,
        "diagram_session_id": diagram_session_id,
        "diagram_type": diagram_type,
        "active_panel": active_panel or "mindmate",
        "created_at": datetime.now(),
        "last_activity": datetime.now(),
        "conversation_history": [],
        "omni_client": omni_client,  # Per-session OmniClient instance
    }

    logger.debug(
        "Session created: %s (linked to diagram=%s, has own OmniClient)",
        session_id,
        diagram_session_id,
    )
    return session_id


def get_voice_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Get session"""
    ensure_kitty_hub_wired()
    return voice_sessions.get(session_id)


def persist_voice_session_context(voice_session_id: str, session_context: Dict[str, Any]) -> None:
    """Write merged session context into the live ``voice_sessions`` record."""
    session = voice_sessions.get(voice_session_id)
    if session is None:
        return
    session["context"] = copy.deepcopy(session_context)


def get_session_omni_client(voice_session_id: str):
    """Return the OmniClient for a voice session (delegates to leaf accessor)."""
    ensure_kitty_hub_wired()
    return _get_session_omni_client_impl(voice_session_id)


def update_panel_context(session_id: str, active_panel: Optional[str]) -> None:
    """Update active panel context; ``None`` leaves the stored panel unchanged."""
    if session_id not in voice_sessions:
        return
    if active_panel is None:
        return
    old_panel = voice_sessions[session_id].get("active_panel", "unknown")
    voice_sessions[session_id]["active_panel"] = active_panel
    logger.debug("Panel context updated: %s (%s -> %s)", session_id, old_panel, active_panel)


async def _close_omni_client_for_session(omni_client: Any, session_id: str) -> None:
    """Await async Omni close; offload sync close to a thread if needed."""
    try:
        close_result = omni_client.close()
        if asyncio.iscoroutine(close_result):
            await close_result
        elif callable(close_result):
            await asyncio.to_thread(close_result)
    except (RuntimeError, AttributeError, asyncio.CancelledError) as exc:
        logger.debug(
            "VOIC | Error closing Omni client for session %s (may already be closed): %s",
            session_id,
            exc,
        )


async def _close_omni_generator_for_session(session: Dict[str, Any], session_id: str) -> None:
    """Close the Omni async generator stored on the voice session, if any."""
    generator = session.get("omni_generator")
    if generator is None:
        return
    aclose = getattr(generator, "aclose", None)
    if not callable(aclose):
        return
    try:
        await cast(Callable[[], Awaitable[Any]], aclose)()
    except (RuntimeError, AttributeError, GeneratorExit, StopAsyncIteration) as exc:
        logger.debug(
            "VOIC | Omni generator close skipped for session %s: %s",
            session_id,
            exc,
        )


async def end_voice_session_async(session_id: str, reason: str = "completed") -> None:
    """
    End and cleanup session including persistent agent and OmniClient (asyncio-native).

    Always ``await`` Omni ``close()`` from async contexts — never ``asyncio.run``.
    Idempotent and safe under concurrent cleanup (e.g. WebSocket teardown vs HTTP).
    """
    await teardown_session_event_handlers(session_id)
    session = voice_sessions.pop(session_id, None)
    if session is None:
        return

    logger.debug("VOIC | Session ended: %s (reason=%s)", session_id, reason)
    await _close_omni_generator_for_session(session, session_id)
    diagram_session_id = session.get("diagram_session_id")
    omni_client = session.get("omni_client")

    if omni_client:
        await _close_omni_client_for_session(omni_client, session_id)
        logger.debug("VOIC | Closed Omni client for session %s", session_id)

    if diagram_session_id:
        agent_session_id = f"diagram_{diagram_session_id}"
        kitty_agent_manager.remove(agent_session_id)
        logger.debug("VOIC | Removed agent for diagram session %s", diagram_session_id)


async def cleanup_voice_by_diagram_session(diagram_session_id: str) -> bool:
    """
    Cleanup voice session and WebSocket connections when diagram session ends.
    Called by session manager on session end or navigation to gallery.

    CRITICAL: This closes all WebSocket connections for the diagram session,
    ensuring fresh state when switching diagrams.
    """
    cleaned_count = 0

    # CRITICAL: Close all WebSocket connections for this diagram session
    if diagram_session_id in active_websockets:
        ws_list = active_websockets[diagram_session_id].copy()  # Copy to avoid modification during iteration
        logger.debug(
            "Closing %d WebSocket connection(s) for diagram %s",
            len(ws_list),
            diagram_session_id,
        )
        for ws in ws_list:
            try:
                # Check WebSocket state before attempting to close
                # This prevents errors when WebSocket is already closed by frontend
                if hasattr(ws, "client_state"):
                    if ws.client_state.name == "DISCONNECTED":
                        logger.debug("WebSocket already disconnected, skipping close")
                    else:
                        await ws.close(code=1001, reason="Diagram session ended")
                else:
                    # Fallback: try to close anyway (for non-FastAPI WebSocket implementations)
                    await ws.close(code=1001, reason="Diagram session ended")
            except (RuntimeError, ConnectionError, AttributeError) as e:
                logger.debug("Error closing WebSocket (may already be closed): %s", e)
            finally:
                # CRITICAL: Always remove from list, even if close failed
                # This prevents memory leaks from orphaned WebSocket references
                try:
                    if diagram_session_id in active_websockets:
                        active_websockets[diagram_session_id].remove(ws)
                except ValueError:
                    # WebSocket not in list (already removed or list was cleared)
                    pass
        # Clear the list and remove entry
        if diagram_session_id in active_websockets:
            if not active_websockets[diagram_session_id]:  # List is empty after removals
                del active_websockets[diagram_session_id]
            else:
                # Some WebSockets couldn't be removed (shouldn't happen, but defensive)
                active_websockets[diagram_session_id] = []
                del active_websockets[diagram_session_id]
        cleaned_count += len(ws_list)

    # CRITICAL: Cleanup ALL voice sessions for this diagram_session_id (not just the first one)
    # This handles cases where cleanup failed before and multiple sessions exist
    voice_session_ids_to_cleanup = []
    for sid, session in list(voice_sessions.items()):  # Use list() to avoid modification during iteration
        if session.get("diagram_session_id") == diagram_session_id:
            voice_session_ids_to_cleanup.append(sid)

    if voice_session_ids_to_cleanup:
        logger.debug(
            "Found %d voice session(s) for diagram %s, cleaning up all",
            len(voice_session_ids_to_cleanup),
            diagram_session_id,
        )
        for voice_session_id in voice_session_ids_to_cleanup:
            logger.debug(
                "Cleaning up voice session %s (diagram session %s ended)",
                voice_session_id,
                diagram_session_id,
            )
            await end_voice_session_async(voice_session_id, reason="diagram_session_ended")
            cleaned_count += 1
        return True

    if cleaned_count > 0:
        return True

    return False


class _HubVoiceInfraState:
    """One-time Agent Hub wiring flag holder."""

    wired: bool = False


def ensure_kitty_hub_wired() -> None:
    """Register Agent Hub + Redis getters once (avoids import-time agent_hub cycles)."""
    if _HubVoiceInfraState.wired:
        return
    _wire_agent_hub_infrastructure()
    _HubVoiceInfraState.wired = True


def _wire_agent_hub_infrastructure() -> None:
    """Wire agent hub infrastructure."""
    configure_voice_session_getter(get_voice_session)
    configure_kitty_scope_cleanup(cleanup_voice_by_diagram_session)
    configure_kitty_control_state(active_websockets, voice_sessions)
