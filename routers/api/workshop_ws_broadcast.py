"""Workshop WebSocket broadcast helpers (fan-out vs in-memory)."""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict

from services.features.ws_redis_fanout_config import is_ws_fanout_enabled

# Shared secret stamped on every fan-out envelope so the subscriber can reject
# messages that did not originate from this application.  Empty string means
# the check is skipped (backward-compatible default; set in production via env).
_FANOUT_ORIGIN_SECRET: str = os.getenv("COLLAB_FANOUT_ORIGIN_SECRET", "")


def _make_fanout_envelope(
    code: str,
    mode: str,
    data_str: str,
    exclude_user_id: Any = None,
) -> Dict[str, Any]:
    """Build a fan-out envelope, optionally stamping an origin secret."""
    env: Dict[str, Any] = {
        "v": 1,
        "k": "ws",
        "code": code,
        "mode": mode,
        "ex": exclude_user_id,
        "d": data_str,
    }
    if _FANOUT_ORIGIN_SECRET:
        env["origin"] = _FANOUT_ORIGIN_SECRET
    return env
from services.features.ws_redis_fanout_publish import publish_workshop_fanout_async
from services.features.workshop_ws_connection_state import (
    ACTIVE_CONNECTIONS as active_connections,
    _SHARD_SIZE,
    _evict_slow_consumer,
)
from services.features.workshop_ws_fanout_delivery import (
    ROOM_IDLE_SHUTDOWN_TYPE,
    SESSION_ENDED_SHUTDOWN_TYPE,
    force_disconnect_local_workshop_room_idle,
    force_disconnect_local_workshop_session_ended,
)
from services.infrastructure.monitoring.ws_metrics import (
    record_ws_broadcast_send_failure,
    record_ws_broadcast_shards,
    record_ws_fanout_publish_failure,
)

logger = logging.getLogger(__name__)


async def _push_shard_local(
    shard: list,
    data_str: str,
    exclude_user_id: Any,
    code: str,
) -> None:
    """Push JSON text to a shard of local handles."""
    body_payload = ("text", data_str)
    for user_id, handle in shard:
        if exclude_user_id is not None and user_id == exclude_user_id:
            continue
        try:
            handle.send_queue.put_nowait(body_payload)
            handle.qsize_high_water = max(
                handle.qsize_high_water, handle.send_queue.qsize()
            )
            logger.debug(
                "[CollabDebug] local push code=%s recipient_user=%s qsize=%d",
                code, user_id, handle.send_queue.qsize(),
            )
        except asyncio.QueueFull:
            await _evict_slow_consumer(handle, "local broadcast queue full")
        except Exception as exc:
            logger.debug(
                "[WorkshopWS] local broadcast push error user=%s code=%s: %s",
                user_id, code, exc,
            )


async def _fanout_local_participants(
    code: str,
    data_str: str,
    exclude_user_id: Any,
) -> None:
    """
    Sharded parallel fan-out to all local participants.

    Shares the same data_str across all handles (no per-peer serialisation).
    Slow peers are evicted without affecting others.
    """
    if code not in active_connections:
        return
    handles = list(active_connections[code].items())
    if not handles:
        return

    shards = [handles[i: i + _SHARD_SIZE] for i in range(0, len(handles), _SHARD_SIZE)]
    try:
        record_ws_broadcast_shards(len(shards))
    except Exception:
        pass

    t0 = time.perf_counter()
    async with asyncio.TaskGroup() as task_group:
        for shard in shards:
            task_group.create_task(
                _push_shard_local(shard, data_str, exclude_user_id, code),
                name=f"local_shard:{code}",
            )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    if elapsed_ms > 100:
        logger.warning(
            "[WorkshopWS] local fanout slow code=%s peers=%d elapsed_ms=%.1f",
            code, len(handles), elapsed_ms,
        )


async def broadcast_to_others(code: str, sender_id: int, message: Dict[str, Any]) -> bool:
    """Broadcast message to all participants except sender. Returns True on success."""
    logger.info(
        "[CollabDebug] broadcast_to_others mode=%s code=%s sender=%s msg_type=%s"
        " seq=%s version=%s ws_msg_id=%s",
        "fanout" if is_ws_fanout_enabled() else "local",
        code, sender_id, message.get("type"),
        message.get("seq"), message.get("version"), message.get("ws_msg_id"),
    )
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(message, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] broadcast_to_others: serialize failed")
            try:
                record_ws_broadcast_send_failure()
            except Exception:
                pass
            return False
        try:
            await publish_workshop_fanout_async(
                _make_fanout_envelope(code, "others", data_str, sender_id)
            )
        except Exception as exc:
            logger.warning("[WorkshopWS] broadcast_to_others publish failed: %s", exc)
            try:
                record_ws_broadcast_send_failure()
                record_ws_fanout_publish_failure()
            except Exception:
                pass
            await _fanout_local_participants(code, data_str, exclude_user_id=sender_id)
        return True

    try:
        data_str = json.dumps(message, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WorkshopWS] broadcast_to_others local: serialize failed")
        return False
    await _fanout_local_participants(code, data_str, exclude_user_id=sender_id)
    return True


async def broadcast_to_all(code: str, message: Dict[str, Any]) -> None:
    """Broadcast message to all participants."""
    logger.info(
        "[CollabDebug] broadcast_to_all mode=%s code=%s msg_type=%s"
        " seq=%s version=%s",
        "fanout" if is_ws_fanout_enabled() else "local",
        code, message.get("type"),
        message.get("seq"), message.get("version"),
    )
    if is_ws_fanout_enabled():
        try:
            data_str = json.dumps(message, ensure_ascii=False)
        except (TypeError, ValueError):
            logger.warning("[WorkshopWS] broadcast_to_all: serialize failed")
            try:
                record_ws_broadcast_send_failure()
            except Exception:
                pass
            return
        try:
            await publish_workshop_fanout_async(
                _make_fanout_envelope(code, "all", data_str)
            )
        except Exception as exc:
            logger.warning("[WorkshopWS] broadcast_to_all publish failed: %s", exc)
            try:
                record_ws_broadcast_send_failure()
                record_ws_fanout_publish_failure()
            except Exception:
                pass
            await _fanout_local_participants(code, data_str, exclude_user_id=None)
            return
        return

    try:
        data_str = json.dumps(message, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("[WorkshopWS] broadcast_to_all local: serialize failed")
        return
    await _fanout_local_participants(code, data_str, exclude_user_id=None)


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
            await publish_workshop_fanout_async(
                _make_fanout_envelope(code, "all", data_str)
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "[WorkshopWS] broadcast_workshop_session_closing publish: %s", exc,
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
            await publish_workshop_fanout_async(
                _make_fanout_envelope(code, "all", data_str)
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "[WorkshopWS] broadcast_workshop_session_ended publish: %s", exc
            )
            try:
                record_ws_broadcast_send_failure()
                record_ws_fanout_publish_failure()
            except Exception:
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
            except Exception:
                pass
            return
        try:
            await publish_workshop_fanout_async(
                _make_fanout_envelope(code, "all", data_str)
            )
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.warning(
                "[WorkshopWS] broadcast_workshop_room_idle_shutdown publish: %s",
                exc,
            )
            try:
                record_ws_broadcast_send_failure()
                record_ws_fanout_publish_failure()
            except Exception:
                pass
        return

    await force_disconnect_local_workshop_room_idle(code)
