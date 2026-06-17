"""Workshop WebSocket broadcast helpers (fan-out vs in-memory)."""

import json
import logging
from typing import Any, Dict

from services.features.workshop_ws_broadcast_core import (
    _make_fanout_envelope,
    broadcast_to_all,
    broadcast_to_others,
)
from services.features.workshop_ws_fanout_delivery import (
    force_disconnect_local_workshop_room_idle,
    force_disconnect_local_workshop_session_ended,
)
from services.features.workshop_ws_shutdown_constants import (
    ROOM_IDLE_SHUTDOWN_TYPE,
    SESSION_ENDED_SHUTDOWN_TYPE,
)
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled
from services.features.ws_redis_fanout_publish import publish_workshop_fanout_async
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_broadcast_send_failure,
    record_ws_fanout_publish_failure,
)
from services.utils.error_types import BACKGROUND_INFRA_ERRORS, REDIS_ERRORS

logger = logging.getLogger(__name__)

__all__ = [
    "broadcast_to_all",
    "broadcast_to_others",
    "broadcast_workshop_room_idle_shutdown",
    "broadcast_workshop_session_closing",
    "broadcast_workshop_session_ended",
]


async def broadcast_workshop_session_closing(code: str) -> None:
    """Notify clients merges will stop (owner stop or idle-kick teardown)."""
    msg: Dict[str, Any] = {"type": "session_closing"}
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(msg, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] session_closing shutdown: serialize failed")
            return
        try:
            await publish_workshop_fanout_async(_make_fanout_envelope(code, "all", data_str))
        except REDIS_ERRORS as exc:
            logger.warning(
                "[WorkshopWS] broadcast_workshop_session_closing publish: %s",
                exc,
            )
        return

    await broadcast_to_all(code, msg)


async def broadcast_workshop_session_ended(code: str) -> None:
    """
    Kick all connected clients when the host explicitly ends the session.

    Sends ``kicked {reason: session_ended}`` + close 4011 on every worker
    (via fan-out publish or direct local close).
    """
    shutdown_msg: Dict[str, Any] = {"type": SESSION_ENDED_SHUTDOWN_TYPE}
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(shutdown_msg, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] session_ended_shutdown: serialize failed")
            return
        try:
            await publish_workshop_fanout_async(_make_fanout_envelope(code, "all", data_str))
        except REDIS_ERRORS as exc:
            logger.warning("[WorkshopWS] broadcast_workshop_session_ended publish: %s", exc)
            try:
                record_ws_broadcast_send_failure()
                record_ws_fanout_publish_failure()
            except BACKGROUND_INFRA_ERRORS:
                pass
        return

    await force_disconnect_local_workshop_session_ended(code)


async def broadcast_workshop_room_idle_shutdown(code: str) -> None:
    """
    End collaboration on all workers: publish shutdown (fan-out) or close local
    sockets when fan-out is disabled.
    """
    shutdown_msg: Dict[str, Any] = {"type": ROOM_IDLE_SHUTDOWN_TYPE}
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(shutdown_msg, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] room_idle_shutdown: serialize failed")
            try:
                record_ws_broadcast_send_failure()
            except BACKGROUND_INFRA_ERRORS:
                pass
            return
        try:
            await publish_workshop_fanout_async(_make_fanout_envelope(code, "all", data_str))
        except REDIS_ERRORS as exc:
            logger.warning(
                "[WorkshopWS] broadcast_workshop_room_idle_shutdown publish: %s",
                exc,
            )
            try:
                record_ws_broadcast_send_failure()
                record_ws_fanout_publish_failure()
            except BACKGROUND_INFRA_ERRORS:
                pass
        return

    await force_disconnect_local_workshop_room_idle(code)
