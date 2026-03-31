"""Historical one-off generator (already run). Do not re-run unless restoring voice.py snapshot.

Splits routers/features/voice.py into routers/features/voice/ package. Output required manual
fixes (imports, target= in diagram_add, etc.); prefer editing the package directly.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "routers" / "features"
SRC = FEATURES / "voice.py"
OUT_DIR = FEATURES / "voice"


def main() -> None:
    lines = SRC.read_text(encoding="utf-8").splitlines(keepends=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    def join_slice(start_1: int, end_1: int) -> str:
        return "".join(lines[start_1 - 1 : end_1])

    def dedent8(text: str) -> str:
        out_lines = []
        for ln in text.splitlines(keepends=True):
            if ln.startswith(" " * 8):
                out_lines.append(ln[8:])
            else:
                out_lines.append(ln)
        return "".join(out_lines)

    state_py = '''"""Shared FastAPI router and in-memory voice session state."""
import logging
from typing import Any, Dict, List

from fastapi import APIRouter, WebSocket

logger = logging.getLogger("VOICE")

router = APIRouter()

voice_sessions: Dict[str, Dict[str, Any]] = {}

active_websockets: Dict[str, List[WebSocket]] = {}
'''
    (OUT_DIR / "state.py").write_text(state_py.rstrip() + "\n", encoding="utf-8")

    deps_py = '''"""Optional dependencies for the voice router (prompts, Redis)."""
try:
    from prompts.voice_agent import VOICE_AGENT_PROMPTS
except ImportError:
    VOICE_AGENT_PROMPTS = None

try:
    from services.redis.cache.redis_user_cache import user_cache as redis_user_cache
except ImportError:
    redis_user_cache = None

try:
    from services.redis.session.redis_session_manager import (
        get_session_manager as redis_get_session_manager,
    )
except ImportError:
    redis_get_session_manager = None
'''
    (OUT_DIR / "deps.py").write_text(deps_py.rstrip() + "\n", encoding="utf-8")

    diagram_utils_header = '''"""Diagram helpers for voice command handling."""
from typing import Dict


'''
    (OUT_DIR / "diagram_utils.py").write_text(
        diagram_utils_header + join_slice(77, 159).rstrip() + "\n",
        encoding="utf-8",
    )

    session_ops_header = '''"""Voice session lifecycle and Omni client accessors."""
from datetime import datetime
from typing import Any, Dict, List, Optional
import asyncio
import uuid

from fastapi import WebSocket

from clients.omni_client import OmniClient
from services.features.voice_agent import voice_agent_manager

from routers.features.voice.deps import redis_get_session_manager
from routers.features.voice.state import active_websockets, logger, voice_sessions


'''
    session_body = join_slice(799, 1050)
    old_close = """        if omni_client:
            try:
                # Native WebSocket client uses async close()
                if (hasattr(omni_client, '_native_client') and
                    omni_client._native_client):  # pylint: disable=protected-access
                    # Schedule async close (can't await in sync function)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is running, schedule close
                            asyncio.create_task(
                                omni_client._native_client.close()
                            )  # pylint: disable=protected-access
                        else:
                            loop.run_until_complete(
                                omni_client._native_client.close()
                            )  # pylint: disable=protected-access
                    except RuntimeError:
                        # No event loop, create new one
                        asyncio.run(omni_client._native_client.close())  # pylint: disable=protected-access
                    logger.debug("VOIC | Closed Omni client for session %s", session_id)
                elif hasattr(omni_client, 'close'):
                    # Handle both sync and async close methods
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
                    "VOIC | Error closing Omni client for session %s "
                    "(may already be closed): %s",
                    session_id, e
                )"""
    new_close = """        if omni_client:
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
                    "VOIC | Error closing Omni client for session %s "
                    "(may already be closed): %s",
                    session_id, e
                )"""
    if old_close not in session_body:
        raise SystemExit("end_voice_session block not found; voice.py changed?")
    session_body = session_body.replace(old_close, new_close)
    (OUT_DIR / "session_ops.py").write_text(
        session_ops_header + session_body.rstrip() + "\n",
        encoding="utf-8",
    )

    messaging_header = '''"""WebSocket messaging and Omni instruction strings for voice."""
from typing import Any, Dict, Optional
import re

from fastapi import WebSocket

from routers.features.voice.state import logger, voice_sessions


'''
    (OUT_DIR / "messaging.py").write_text(
        messaging_header + join_slice(1053, 1292).rstrip() + "\n",
        encoding="utf-8",
    )

    diagram_handlers_header = '''"""Handlers for update_center / update_node voice actions."""
from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.messaging import (
    build_voice_instructions,
    parse_double_bubble_target,
    safe_websocket_send,
)
from routers.features.voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
)
from routers.features.voice.state import logger, voice_sessions


'''
    (OUT_DIR / "diagram_handlers.py").write_text(
        diagram_handlers_header + join_slice(1295, 1590).rstrip() + "\n",
        encoding="utf-8",
    )

    add_block = dedent8(join_slice(1618, 2085))
    diagram_add_py = '''"""Add-node branch for voice diagram updates."""
from typing import Any, Dict

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.diagram_utils import get_diagram_prefix_map
from routers.features.voice.messaging import build_voice_instructions, safe_websocket_send
from routers.features.voice.session_ops import get_agent_session_id, get_session_omni_client
from routers.features.voice.state import logger, voice_sessions


async def voice_apply_add_node_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
) -> bool:
'''
    (OUT_DIR / "diagram_add.py").write_text(
        diagram_add_py + add_block.rstrip() + "\n",
        encoding="utf-8",
    )

    delete_block = dedent8(join_slice(2087, 2443))
    diagram_delete_py = '''"""Delete-node branch for voice diagram updates."""
from typing import Any, Dict, Optional

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.diagram_utils import get_diagram_prefix_map
from routers.features.voice.messaging import build_voice_instructions, safe_websocket_send
from routers.features.voice.session_ops import get_agent_session_id, get_session_omni_client
from routers.features.voice.state import logger, voice_sessions


async def voice_apply_delete_node_action(
    websocket: WebSocket,
    voice_session_id: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
    target: Optional[str],
    node_index: Optional[Any],
    node_identifier: Optional[Any],
) -> bool:
'''
    (OUT_DIR / "diagram_delete.py").write_text(
        diagram_delete_py + delete_block.rstrip() + "\n",
        encoding="utf-8",
    )

    diagram_execute_py = '''"""Dispatch diagram update actions from voice commands."""
from typing import Any, Dict

from fastapi import WebSocket

from routers.features.voice.diagram_add import voice_apply_add_node_action
from routers.features.voice.diagram_delete import voice_apply_delete_node_action
from routers.features.voice.diagram_handlers import (
    _handle_update_center_action,
    _handle_update_node_action,
)
from routers.features.voice.state import logger


async def execute_diagram_update(
    websocket: WebSocket,
    voice_session_id: str,
    action: str,
    command: Dict[str, Any],
    session_context: Dict[str, Any],
) -> bool:
    """
    Execute a diagram update action (update_center, update_node, add_node, delete_node).
    Returns True if update was executed, False otherwise.
    """
    target = command.get("target")
    node_index = command.get("node_index")
    node_identifier = command.get("node_identifier")

    try:
        if action == "update_center":
            return await _handle_update_center_action(
                websocket, voice_session_id, command, session_context, target
            )

        if action == "update_node" and target:
            return await _handle_update_node_action(
                websocket,
                voice_session_id,
                command,
                session_context,
                target,
                node_index,
                node_identifier,
            )

        if action == "add_node":
            return await voice_apply_add_node_action(
                websocket, voice_session_id, command, session_context
            )

        if action == "delete_node":
            return await voice_apply_delete_node_action(
                websocket,
                voice_session_id,
                command,
                session_context,
                target,
                node_index,
                node_identifier,
            )

        return False

    except (ValueError, KeyError, RuntimeError, AttributeError) as e:
        logger.error("Diagram update execution error: %s", e, exc_info=True)
        return False
'''
    (OUT_DIR / "diagram_execute.py").write_text(diagram_execute_py.rstrip() + "\n", encoding="utf-8")

    paragraph_header = '''"""Paragraph processing with Qwen Plus for voice input."""
from typing import Any, Dict
import json
import logging
import re

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager
from services.llm import llm_service

from routers.features.voice.deps import VOICE_AGENT_PROMPTS
from routers.features.voice.diagram_execute import execute_diagram_update
from routers.features.voice.messaging import safe_websocket_send
from routers.features.voice.session_ops import get_agent_session_id, get_session_omni_client
from routers.features.voice.state import logger, voice_sessions


'''
    (OUT_DIR / "paragraph.py").write_text(
        paragraph_header + join_slice(162, 796).rstrip() + "\n",
        encoding="utf-8",
    )

    commands_header = '''"""Voice command parsing and UI actions (non-Omni)."""
from typing import Any, Dict

from fastapi import WebSocket

from services.features.voice_agent import voice_agent_manager

from routers.features.voice.deps import redis_user_cache
from routers.features.voice.diagram_execute import execute_diagram_update
from routers.features.voice.diagram_utils import get_diagram_prefix_map, is_paragraph_text
from routers.features.voice.messaging import safe_websocket_send
from routers.features.voice.paragraph import process_paragraph_with_qwen_plus
from routers.features.voice.session_ops import (
    get_agent_session_id,
    get_session_omni_client,
    get_voice_session,
)
from routers.features.voice.state import logger, voice_sessions


'''
    (OUT_DIR / "commands.py").write_text(
        commands_header + join_slice(2451, 2755).rstrip() + "\n",
        encoding="utf-8",
    )

    routes_raw = join_slice(2758, 3518)
    routes_raw = routes_raw.replace(
        "@router.websocket",
        "from routers.features.voice.state import router\n\n\n@router.websocket",
        1,
    )
    old_finally_omni = """                try:
                    # Native WebSocket client uses async close()
                    if (hasattr(omni_client, '_native_client') and
                        omni_client._native_client):  # pylint: disable=protected-access
                        await omni_client._native_client.close()  # pylint: disable=protected-access
                        logger.debug("Closed Omni client for session %s", voice_session_id)
                    elif hasattr(omni_client, 'close'):
                        # Handle both sync and async close methods
                        close_result = omni_client.close()
                        if asyncio.iscoroutine(close_result):
                            await close_result
                        logger.debug("Closed Omni client for session %s", voice_session_id)
                except (RuntimeError, ConnectionError, AttributeError) as e:  # pylint: disable=protected-access
                    logger.debug(
                        "Error closing Omni client for session %s (may already be closed): %s",
                        voice_session_id, e
                    )"""
    new_finally_omni = """                try:
                    close_result = omni_client.close()
                    if asyncio.iscoroutine(close_result):
                        await close_result
                    logger.debug("Closed Omni client for session %s", voice_session_id)
                except (RuntimeError, ConnectionError, AttributeError) as e:
                    logger.debug(
                        "Error closing Omni client for session %s (may already be closed): %s",
                        voice_session_id, e
                    )"""
    if old_finally_omni not in routes_raw:
        raise SystemExit("websocket finally omni block not found")
    routes_raw = routes_raw.replace(old_finally_omni, new_finally_omni)

    routes_header = '''"""Voice WebSocket route and REST cleanup endpoint."""
from typing import Any, Dict, List, Optional
import asyncio
import base64
import json
import random
import uuid

from fastapi import Depends, WebSocket, WebSocketDisconnect

from clients.omni_client import OmniClient
from config.settings import config
from models.domain.auth import User
from services.features.voice_agent import voice_agent_manager
from services.features.websocket_llm_middleware import omni_middleware
from utils.auth import decode_access_token, get_current_user

from routers.features.voice.commands import process_voice_command
from routers.features.voice.messaging import build_greeting_message
from routers.features.voice.session_ops import (
    cleanup_voice_by_diagram_session,
    create_voice_session,
    end_voice_session,
    get_session_omni_client,
    get_voice_session,
    update_panel_context,
)
from routers.features.voice.state import active_websockets, logger, voice_sessions


'''
    (OUT_DIR / "routes.py").write_text(
        routes_header + routes_raw.rstrip() + "\n",
        encoding="utf-8",
    )

    init_py = '''"""VoiceAgent router: real-time voice WebSocket and cleanup API."""

from routers.features.voice.state import router
from routers.features.voice import routes

__all__ = ["router", "routes"]
'''
    (OUT_DIR / "__init__.py").write_text(init_py.rstrip() + "\n", encoding="utf-8")

    SRC.unlink()
    print("Removed", SRC)
    print("Wrote package under", OUT_DIR)


if __name__ == "__main__":
    main()
