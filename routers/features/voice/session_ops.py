"""Voice session lifecycle and Omni client accessors."""

from datetime import datetime
from typing import Any, Dict, Optional
import asyncio
import uuid

from clients.omni_client import OmniClient
from services.features.voice_agent import voice_agent_manager

from routers.features.voice.state import active_websockets, logger, voice_sessions


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

    VoiceAgent session lifecycle is controlled by:
    1. Black cat click (activation)
    2. Black cat click again (deactivation)
    3. Session manager cleanup (when diagram session ends)
    4. Navigation to gallery (session manager triggers cleanup)
    """
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
    return voice_sessions.get(session_id)


def get_session_omni_client(voice_session_id: str):
    """
    Get the OmniClient instance for a voice session.

    CRITICAL: Each voice session has its own OmniClient instance to support
    concurrent users. This prevents cross-contamination between users.

    Args:
        voice_session_id: Voice session ID

    Returns:
        OmniClient instance for this session, or None if session not found
    """
    session = get_voice_session(voice_session_id)
    if not session:
        logger.warning("Voice session %s not found", voice_session_id)
        return None

    omni_client = session.get("omni_client")
    if not omni_client:
        logger.warning("OmniClient not found for session %s", voice_session_id)
        return None

    return omni_client


def update_panel_context(session_id: str, active_panel: str) -> None:
    """Update active panel context"""
    if session_id in voice_sessions:
        old_panel = voice_sessions[session_id].get("active_panel", "unknown")
        voice_sessions[session_id]["active_panel"] = active_panel
        logger.debug("Panel context updated: %s (%s -> %s)", session_id, old_panel, active_panel)


def end_voice_session(session_id: str, reason: str = "completed") -> None:
    """
    End and cleanup session including persistent agent and OmniClient.

    CRITICAL: This closes the OmniClient WebSocket connection and removes the agent.
    Called when:
    - User navigates back to gallery
    - User switches to a different diagram
    - WebSocket connection closes
    """
    if session_id in voice_sessions:
        logger.debug("VOIC | Session ended: %s (reason=%s)", session_id, reason)
        session = voice_sessions[session_id]

        # Get diagram_session_id before deleting the session
        diagram_session_id = session.get("diagram_session_id")

        # CRITICAL: Close OmniClient WebSocket connection before deleting session
        # Each voice session has its own OmniClient instance that must be closed
        omni_client = session.get("omni_client")
        if omni_client:
            try:
                close_result = omni_client.close()
                if asyncio.iscoroutine(close_result):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(close_result)
                        else:
                            loop.run_until_complete(close_result)
                    except RuntimeError:
                        asyncio.run(close_result)
                logger.debug("VOIC | Closed Omni client for session %s", session_id)
            except (RuntimeError, AttributeError, asyncio.CancelledError) as e:
                logger.debug(
                    "VOIC | Error closing Omni client for session %s (may already be closed): %s",
                    session_id,
                    e,
                )

        # Delete session from memory
        del voice_sessions[session_id]

        # Cleanup the persistent LangGraph agent using diagram_session_id
        # CRITICAL: Agent is scoped to diagram_session_id, not voice_session_id
        if diagram_session_id:
            agent_session_id = f"diagram_{diagram_session_id}"
            voice_agent_manager.remove(agent_session_id)
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
            end_voice_session(voice_session_id, reason="diagram_session_ended")
            cleaned_count += 1
        return True

    if cleaned_count > 0:
        return True

    return False
