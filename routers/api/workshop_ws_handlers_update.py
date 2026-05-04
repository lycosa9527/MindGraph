"""
`update` message handler for the canvas collaboration WebSocket.

Extracted from workshop_ws_handlers.py to keep that file under 800 LOC.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import OrderedDict
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from services.features.workshop_ws_connection_state import (
    ACTIVE_EDITORS as active_editors,
    enqueue,
)
from services.features.ws_redis_fanout_config import is_ws_fanout_enabled

from services.infrastructure.monitoring.ws_metrics import (
    record_ws_collab_granular_lock_reject,
    record_ws_collab_partial_filter_notify,
    record_ws_collab_update_schema_reject,
    record_ws_live_spec_merge_failure,
    record_ws_load_editors_latency_ms,
    record_ws_read_live_spec_latency_ms,
    record_ws_update_latency,
    record_ws_update_semaphore_wait_ms,
)
from services.redis.redis_async_client import get_async_redis
from services.online_collab.core.online_collab_manager import get_online_collab_manager
from services.online_collab.lifecycle.online_collab_redis_ttl import (
    get_online_collab_redis_ttl_seconds,
)
from services.online_collab.participant.canvas_collab_locks import (
    build_connection_endpoints_map,
    build_locked_by_others_node_ids,
    filter_deleted_connection_ids_for_locks,
    filter_deleted_node_ids_for_locks,
    filter_granular_connections_for_locks,
    filter_granular_nodes_for_locks,
)
from services.online_collab.redis.online_collab_redis_locks import (
    acquire_room_write_lock,
    release_room_write_lock,
)
from services.online_collab.participant.online_collab_ws_editor_redis import (
    load_editors,
)
from services.online_collab.redis.redis8_features import (
    topk_record_room_activity,
    topk_record_user_activity,
)
from services.online_collab.lifecycle.online_collab_session_closing import (
    workshop_session_is_closing,
)
from services.online_collab.spec.online_collab_live_flush import (
    schedule_live_spec_db_flush,
)
from services.online_collab.redis.online_collab_redis_keys import client_op_dedupe_key
from services.online_collab.spec.online_collab_live_spec import read_live_spec
from services.online_collab.spec.online_collab_live_spec_ops import (
    mutate_live_spec_after_ws_update,
)
from services.online_collab.common.online_collab_constants import (
    DEFAULT_DB_HOT_PATH_TIMEOUT_SEC,
    DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC,
)
from routers.api.workshop_ws_broadcast import broadcast_to_others
from routers.api.workshop_ws_update_schema import collab_update_schema_error

logger = logging.getLogger(__name__)

# Process-wide backstop: prevents a single process from being saturated by
# too many concurrent merges regardless of room distribution.  Set high enough
# that per-room caps are the binding constraint in normal operation.
_UPDATE_SEMAPHORE = asyncio.Semaphore(
    int(os.environ.get("COLLAB_UPDATE_GLOBAL_SEM_CAP", "500"))
)

_ROOM_MERGE_MAX_REGISTRY = 1024
_ROOM_MERGE_SEMAPHORES: "OrderedDict[str, asyncio.Semaphore]" = OrderedDict()
_ROOM_SEM_LOCK = asyncio.Lock()

# Per-room merge cap: a single hot room is bound by this value so it cannot
# starve all other rooms in the same process.  Default 50 is chosen for
# classrooms of 200-500 participants: at 50 concurrent × ~10 ms/merge the
# effective throughput exceeds 5,000 merges/s per room — well above any
# realistic burst.  Read once at module load for stable lifetime value.
_PER_ROOM_SEM_CAP: int = max(
    1, int(os.environ.get("COLLAB_ROOM_MERGE_SEM_CAP", "50"))
)


def _collab_update_acquire_timeout_sec() -> float:
    raw = os.environ.get("COLLAB_WS_UPDATE_SEMAPHORE_ACQUIRE_SEC", "45")
    try:
        parsed = float(raw)
    except (TypeError, ValueError):
        return 45.0
    return parsed if parsed > 0 else 45.0


async def _room_merge_semaphore(code: str) -> asyncio.Semaphore:
    async with _ROOM_SEM_LOCK:
        existing = _ROOM_MERGE_SEMAPHORES.get(code)
        if existing is not None:
            _ROOM_MERGE_SEMAPHORES.move_to_end(code)
            return existing
        if len(_ROOM_MERGE_SEMAPHORES) >= _ROOM_MERGE_MAX_REGISTRY:
            _ROOM_MERGE_SEMAPHORES.popitem(last=False)
        sem = asyncio.Semaphore(_PER_ROOM_SEM_CAP)
        _ROOM_MERGE_SEMAPHORES[code] = sem
        return sem


async def _send(ctx: Any, payload: dict, msg_type: str = "error") -> None:
    """Route an outbound frame through handle.enqueue or ws.send_json fallback."""
    if ctx.handle is not None:
        await enqueue(ctx.handle, payload, msg_type)
    else:
        await ctx.websocket.send_json(payload)


_MAX_COLLAB_UPDATE_NODES = 100
_MAX_COLLAB_UPDATE_CONNECTIONS = 200
_MAX_COLLAB_DELETED_NODE_IDS = 200
_MAX_COLLAB_DELETED_CONNECTION_IDS = 200
_MAX_COLLAB_ID_LENGTH = 200
_MAX_CLIENT_OP_ID_LENGTH = 128
_FULL_SPEC_MAX_NODES = 512
_FULL_SPEC_MAX_CONNECTIONS = 1024
_FULL_SPEC_MAX_UTF8_BYTES = 786432


def _full_spec_validation_error(spec: Any) -> Optional[str]:
    """Bounds for full-document replacement updates (beyond raw WS frame limits)."""
    if spec is None:
        return None
    if not isinstance(spec, dict):
        return "spec must be an object"
    nodes = spec.get("nodes")
    connections = spec.get("connections")
    if nodes is not None and not isinstance(nodes, list):
        return "spec.nodes must be an array"
    if connections is not None and not isinstance(connections, list):
        return "spec.connections must be an array"
    if nodes is not None and len(nodes) > _FULL_SPEC_MAX_NODES:
        return f"spec.nodes exceeds max length ({_FULL_SPEC_MAX_NODES})"
    if connections is not None and len(connections) > _FULL_SPEC_MAX_CONNECTIONS:
        return f"spec.connections exceeds max length ({_FULL_SPEC_MAX_CONNECTIONS})"
    try:
        serialised_len = len(json.dumps(spec, ensure_ascii=False).encode("utf-8"))
        if serialised_len > _FULL_SPEC_MAX_UTF8_BYTES:
            return f"spec JSON exceeds {_FULL_SPEC_MAX_UTF8_BYTES // 1024} KiB"
    except (TypeError, ValueError):
        return "spec is not serialisable"
    return None


def _diagram_update_validation_error(
    diagram_id: str,
    message: Dict[str, Any],
) -> Optional[str]:
    """Return an error string for invalid updates, else ``None``."""
    errors: List[str] = []
    if message.get("diagram_id") != diagram_id:
        errors.append("Diagram ID mismatch")
    spec = message.get("spec")
    nodes = message.get("nodes")
    connections = message.get("connections")
    deleted_node_ids_raw = message.get("deleted_node_ids")
    deleted_connection_ids_raw = message.get("deleted_connection_ids")
    has_deletions = bool(deleted_node_ids_raw) or bool(deleted_connection_ids_raw)

    if not spec and not nodes and not connections and not has_deletions:
        errors.append("Missing spec, nodes, connections, or deletions in update")
    if nodes is not None:
        if not isinstance(nodes, list):
            errors.append("Invalid nodes format (must be array)")
        elif len(nodes) > _MAX_COLLAB_UPDATE_NODES:
            errors.append(f"Too many nodes in update (max {_MAX_COLLAB_UPDATE_NODES})")
    if connections is not None:
        if not isinstance(connections, list):
            errors.append("Invalid connections format (must be array)")
        elif len(connections) > _MAX_COLLAB_UPDATE_CONNECTIONS:
            errors.append(
                "Too many connections in update "
                f"(max {_MAX_COLLAB_UPDATE_CONNECTIONS})"
            )
    if deleted_node_ids_raw is not None:
        if not isinstance(deleted_node_ids_raw, list):
            errors.append("Invalid deleted_node_ids format (must be array)")
        elif len(deleted_node_ids_raw) > _MAX_COLLAB_DELETED_NODE_IDS:
            errors.append(
                "Too many deleted_node_ids in update "
                f"(max {_MAX_COLLAB_DELETED_NODE_IDS})"
            )
        elif any(
            not isinstance(i, str) or len(i) > _MAX_COLLAB_ID_LENGTH
            for i in deleted_node_ids_raw
            if i is not None
        ):
            errors.append(
                "Invalid deleted_node_ids entry (must be string, "
                f"max {_MAX_COLLAB_ID_LENGTH} chars)"
            )
    if deleted_connection_ids_raw is not None:
        if not isinstance(deleted_connection_ids_raw, list):
            errors.append("Invalid deleted_connection_ids format (must be array)")
        elif len(deleted_connection_ids_raw) > _MAX_COLLAB_DELETED_CONNECTION_IDS:
            errors.append(
                "Too many deleted_connection_ids in update "
                f"(max {_MAX_COLLAB_DELETED_CONNECTION_IDS})"
            )
        elif any(
            not isinstance(i, str) or len(i) > _MAX_COLLAB_ID_LENGTH
            for i in deleted_connection_ids_raw
            if i is not None
        ):
            errors.append(
                "Invalid deleted_connection_ids entry (must be string, "
                f"max {_MAX_COLLAB_ID_LENGTH} chars)"
            )

    granular = nodes is not None or connections is not None
    if spec is not None and not granular:
        fs_err = _full_spec_validation_error(spec)
        if fs_err:
            errors.append(fs_err)
    cop_raw = message.get("client_op_id")
    if cop_raw is not None:
        if not isinstance(cop_raw, str):
            errors.append("client_op_id must be a string")
        elif len(cop_raw) > _MAX_CLIENT_OP_ID_LENGTH:
            errors.append(
                f"client_op_id exceeds max length ({_MAX_CLIENT_OP_ID_LENGTH})"
            )
    return errors[0] if errors else None


async def handle_update(ctx: Any, message: Dict[str, Any]) -> None:
    """Process an `update` message from a collaborator."""
    verr = _diagram_update_validation_error(ctx.diagram_id, message)
    if verr:
        logger.info(
            "[CollabDebug] update validation rejected user=%s diagram=%s code=%s reason=%s",
            ctx.user.id, ctx.diagram_id, ctx.code, verr,
        )
        await _send(ctx, {"type": "error", "message": verr})
        return

    schema_err = collab_update_schema_error(message)
    if schema_err:
        try:
            record_ws_collab_update_schema_reject()
        except Exception:
            pass
        await _send(
            ctx,
            {
                "type": "error",
                "code": "update_invalid",
                "message": schema_err,
            },
        )
        return

    if await workshop_session_is_closing(ctx.code):
        await _send(
            ctx,
            {
                "type": "error",
                "message": (
                    "Workshop is shutting down — updates are no longer accepted. "
                    "Wait for the session to end and reconnect."
                ),
            },
        )
        return

    spec = message.get("spec")
    raw_nodes = message.get("nodes")
    raw_connections = message.get("connections")
    raw_deleted_node_ids = message.get("deleted_node_ids")
    raw_deleted_connection_ids = message.get("deleted_connection_ids")

    nodes = raw_nodes if isinstance(raw_nodes, list) else None
    connections = raw_connections if isinstance(raw_connections, list) else None
    deleted_node_ids: List[str] = (
        [str(i) for i in raw_deleted_node_ids if i]
        if isinstance(raw_deleted_node_ids, list)
        else []
    )
    deleted_connection_ids: List[str] = (
        [str(i) for i in raw_deleted_connection_ids if i]
        if isinstance(raw_deleted_connection_ids, list)
        else []
    )

    is_granular_early = (
        nodes is not None
        or connections is not None
        or bool(deleted_node_ids)
        or bool(deleted_connection_ids)
    )
    logger.info(
        "[CollabDebug] handle_update user=%s diagram=%s code=%s"
        " is_granular=%s nodes=%d conns=%d del_nodes=%d del_conns=%d",
        ctx.user.id, ctx.diagram_id, ctx.code, is_granular_early,
        len(nodes or []), len(connections or []),
        len(deleted_node_ids), len(deleted_connection_ids),
    )
    if nodes:
        node_ids_preview = [
            str(n.get("id") or n.get("node_id") or "?")
            for n in nodes[:10]
        ]
        logger.debug(
            "[CollabDebug] update_node_ids user=%s code=%s node_ids=%s%s",
            ctx.user.id, ctx.code, node_ids_preview,
            " (truncated)" if len(nodes) > 10 else "",
        )

    await get_online_collab_manager().refresh_participant_ttl(ctx.code, ctx.user.id)

    client_op_id: Optional[str] = None
    raw_client_op = message.get("client_op_id")
    if isinstance(raw_client_op, str):
        cop_stripped = raw_client_op.strip()
        if cop_stripped:
            client_op_id = cop_stripped[:_MAX_CLIENT_OP_ID_LENGTH]

    redis = get_async_redis()
    if not redis:
        await _send(
            ctx,
            {
                "type": "error",
                "message": (
                    "Live diagram sync unavailable - Redis is not reachable. "
                    "Reconnect or use resync if the problem persists."
                ),
            },
        )
        return

    if is_ws_fanout_enabled():
        _le_start = time.monotonic()
        try:
            async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
                editors_redis = await load_editors(ctx.code)
        except asyncio.TimeoutError:
            logger.warning(
                "[WorkshopTimeout] load_editors exceeded %.2fs — using empty map",
                DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC,
            )
            editors_redis = {}
        finally:
            try:
                record_ws_load_editors_latency_ms(
                    (time.monotonic() - _le_start) * 1000,
                )
            except Exception:
                pass
    else:
        editors_redis = None

    is_granular = (
        nodes is not None
        or connections is not None
        or bool(deleted_node_ids)
        or bool(deleted_connection_ids)
    )

    filtered_nodes: Optional[List[Any]] = None
    filtered_connections: Optional[List[Any]] = None

    if is_granular:
        in_node_ids = [n.get("id") for n in (nodes or []) if isinstance(n, dict)]
        in_conn_ids = [c.get("id") for c in (connections or []) if isinstance(c, dict)]
        in_del_node_ids = list(deleted_node_ids)
        in_del_conn_ids = list(deleted_connection_ids)

        if nodes is not None:
            filtered_nodes = filter_granular_nodes_for_locks(
                ctx.code, ctx.user.id, nodes, active_editors, editors_redis,
            )
        if connections is not None:
            filtered_connections = filter_granular_connections_for_locks(
                ctx.code, ctx.user.id, connections, active_editors, editors_redis,
            )
        if deleted_node_ids:
            deleted_node_ids = filter_deleted_node_ids_for_locks(
                ctx.code, ctx.user.id, deleted_node_ids, active_editors, editors_redis,
            )
        if deleted_connection_ids:
            endpoints_map = build_connection_endpoints_map(connections)
            needs_spec_lookup = any(
                cid not in endpoints_map for cid in deleted_connection_ids
            )
            if needs_spec_lookup:
                live_doc = None
                _rs_start = time.monotonic()
                try:
                    try:
                        async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
                            live_doc = await read_live_spec(redis, ctx.code)
                    except (asyncio.TimeoutError, Exception) as exc:
                        logger.debug("read_live_spec for deleted-conn filter failed: %s", exc)
                        live_doc = None
                finally:
                    try:
                        record_ws_read_live_spec_latency_ms(
                            (time.monotonic() - _rs_start) * 1000,
                        )
                    except Exception:
                        pass
                if isinstance(live_doc, dict):
                    spec_conns = live_doc.get("connections")
                    endpoints_map.update(build_connection_endpoints_map(spec_conns))
            deleted_connection_ids = filter_deleted_connection_ids_for_locks(
                ctx.code, ctx.user.id, deleted_connection_ids,
                endpoints_map, active_editors, editors_redis,
            )

        out_node_ids = [n.get("id") for n in (filtered_nodes or []) if isinstance(n, dict)]
        out_conn_ids = [c.get("id") for c in (filtered_connections or []) if isinstance(c, dict)]

        has_payload = (
            bool(filtered_nodes)
            or bool(filtered_connections)
            or bool(deleted_node_ids)
            or bool(deleted_connection_ids)
        )
        if not has_payload:
            logger.info(
                "[CollabDebug] update_rejected (all ops locked) user=%s code=%s"
                " in_nodes=%s out_nodes=%s in_conns=%s out_conns=%s"
                " in_del_nodes=%s out_del_nodes=%s in_del_conns=%s out_del_conns=%s",
                ctx.user.id, ctx.code,
                in_node_ids, out_node_ids,
                in_conn_ids, out_conn_ids,
                in_del_node_ids, deleted_node_ids,
                in_del_conn_ids, deleted_connection_ids,
            )
            try:
                record_ws_collab_granular_lock_reject()
            except Exception as exc:
                logger.debug("lock reject metric skipped: %s", exc)
            await _send(
                ctx,
                {
                    "type": "error",
                    "code": "update_rejected",
                    "message": (
                        "Update rejected: another collaborator is editing "
                        "a conflicting node."
                    ),
                },
            )
            return

        # Partial filter: some node ops were dropped by lock filters but the rest
        # can proceed.  Notify the sender so the UI can indicate the conflict without
        # silently discarding work.
        out_node_ids_set = set(out_node_ids)
        dropped_node_ids = [
            nid for nid in in_node_ids if nid is not None and nid not in out_node_ids_set
        ]
        if dropped_node_ids:
            logger.debug(
                "[CollabDebug] update_partial_filtered user=%s code=%s dropped_nodes=%s",
                ctx.user.id, ctx.code, dropped_node_ids,
            )
            try:
                record_ws_collab_partial_filter_notify()
            except Exception:
                pass
            await _send(
                ctx,
                {
                    "type": "error",
                    "code": "update_partial_filtered",
                    "message": (
                        "Some node edits were filtered because another "
                        "collaborator is editing those nodes."
                    ),
                    "filtered_node_ids": dropped_node_ids,
                },
            )
    else:
        if spec is not None and isinstance(spec, dict):
            spec_nodes = spec.get("nodes")
            if isinstance(spec_nodes, list):
                locked_by_others = build_locked_by_others_node_ids(
                    ctx.code, ctx.user.id, active_editors, editors_redis,
                )
                locked_ids = {
                    str(n.get("id"))
                    for n in spec_nodes
                    if isinstance(n, dict) and n.get("id")
                    and str(n.get("id")) in locked_by_others
                }
                if locked_ids:
                    await _send(
                        ctx,
                        {
                            "type": "error",
                            "code": "update_rejected",
                            "message": (
                                "Full spec update rejected: another collaborator "
                                "is editing one or more nodes in your update."
                            ),
                        },
                    )
                    return

    merged_doc: Optional[Dict[str, Any]] = None
    live_merge_failed = False
    skip_broadcast = False
    write_lock_token: Optional[str] = None
    _sem_wait_mark = time.monotonic()
    acquire_timeout = _collab_update_acquire_timeout_sec()
    room_sem = await _room_merge_semaphore(ctx.code)

    try:
        await asyncio.wait_for(_UPDATE_SEMAPHORE.acquire(), timeout=acquire_timeout)
    except asyncio.TimeoutError:
        try:
            record_ws_update_semaphore_wait_ms(
                (time.monotonic() - _sem_wait_mark) * 1000,
            )
        except Exception:
            pass
        await _send(
            ctx,
            {
                "type": "error",
                "message": (
                    "Server is busy applying other updates. Retry in a moment."
                ),
            },
        )
        return

    try:
        try:
            await asyncio.wait_for(room_sem.acquire(), timeout=acquire_timeout)
        except asyncio.TimeoutError:
            try:
                record_ws_update_semaphore_wait_ms(
                    (time.monotonic() - _sem_wait_mark) * 1000,
                )
            except Exception:
                pass
            await _send(
                ctx,
                {
                    "type": "error",
                    "message": (
                        "This room has too many concurrent edits. Retry shortly."
                    ),
                },
            )
            return

        try:
            try:
                record_ws_update_semaphore_wait_ms(
                    (time.monotonic() - _sem_wait_mark) * 1000,
                )
            except Exception:
                pass
            _merge_start = time.monotonic()
            skip_merge_duplicate = False
            if client_op_id:
                try:
                    async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
                        dedupe_was_new = await redis.set(
                            client_op_dedupe_key(
                                ctx.code, int(ctx.user.id), client_op_id,
                            ),
                            "1",
                            nx=True,
                            ex=120,
                        )
                    if not dedupe_was_new:
                        skip_merge_duplicate = True
                except (asyncio.TimeoutError, OSError, RuntimeError, TypeError,
                        ValueError) as exc:
                    logger.debug(
                        "[CollabDebug] client_op dedupe SET failed code=%s: %s",
                        ctx.code, exc,
                    )
            if skip_merge_duplicate:
                try:
                    async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
                        merged_doc = await read_live_spec(redis, ctx.code)
                except (asyncio.TimeoutError, Exception) as exc:
                    logger.debug(
                        "[CollabDebug] read_live_spec duplicate path failed: %s",
                        exc,
                    )
                    merged_doc = None
                skip_broadcast = True
            else:
                async with asyncio.timeout(DEFAULT_DB_HOT_PATH_TIMEOUT_SEC):
                    ttl_sec = await get_online_collab_redis_ttl_seconds(
                        ctx.diagram_id, code=ctx.code,
                    )
                try:
                    async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
                        write_lock_token = await acquire_room_write_lock(
                            redis, ctx.code, int(ctx.user.id),
                        )
                except (asyncio.TimeoutError, Exception) as _wl_exc:
                    logger.debug(
                        "[CollabDebug] write-lock acquire failed code=%s: %s",
                        ctx.code, _wl_exc,
                    )
                if write_lock_token:
                    await broadcast_to_others(
                        ctx.code,
                        ctx.user.id,
                        {"type": "write_locked", "user_id": ctx.user.id, "locked": True},
                    )
                async with asyncio.timeout(DEFAULT_REDIS_HOT_PATH_TIMEOUT_SEC):
                    merged_doc = await mutate_live_spec_after_ws_update(
                        redis, ctx.code, ctx.diagram_id, ttl_sec, spec,
                        filtered_nodes if is_granular else nodes,
                        filtered_connections if is_granular else connections,
                        deleted_node_ids=deleted_node_ids,
                        deleted_connection_ids=deleted_connection_ids,
                    )
            try:
                record_ws_update_latency((time.monotonic() - _merge_start) * 1000)
            except Exception:
                pass
            if merged_doc is not None:
                await schedule_live_spec_db_flush(ctx.code, ctx.diagram_id)
        except asyncio.TimeoutError:
            live_merge_failed = True
            logger.warning("[LiveSpec] merge/flush hit timeout code=%s", ctx.code)
        except Exception as exc:
            live_merge_failed = True
            logger.warning(
                "[LiveSpec] merge or flush schedule failed: %s", exc, exc_info=True,
            )
        finally:
            if write_lock_token:
                try:
                    await release_room_write_lock(redis, ctx.code, write_lock_token)
                except Exception as _rl_exc:
                    logger.debug(
                        "[CollabDebug] write-lock release failed code=%s: %s",
                        ctx.code, _rl_exc,
                    )
                await broadcast_to_others(
                    ctx.code,
                    ctx.user.id,
                    {"type": "write_locked", "user_id": ctx.user.id, "locked": False},
                )
            room_sem.release()
    finally:
        _UPDATE_SEMAPHORE.release()

    if merged_doc is None:
        live_merge_failed = True

    if live_merge_failed:
        try:
            record_ws_live_spec_merge_failure()
        except Exception as exc:
            logger.debug("merge failure metric skipped: %s", exc)
        await _send(
            ctx,
            {
                "type": "error",
                "message": (
                    "Live diagram sync unavailable. Reconnect or use resync "
                    "if the problem persists."
                ),
            },
        )
        return

    update_message: Dict[str, Any] = {
        "type": "update",
        "diagram_id": ctx.diagram_id,
        "user_id": ctx.user.id,
        "timestamp": message.get("timestamp") or datetime.now(UTC).isoformat(),
        "ws_msg_id": str(uuid.uuid4()),
    }
    if merged_doc is not None:
        live_ver = merged_doc.get("v")
        if isinstance(live_ver, int):
            update_message["version"] = live_ver
        seq_from_merge = merged_doc.pop("__seq__", None)
        if isinstance(seq_from_merge, int):
            update_message["seq"] = seq_from_merge

    if is_granular:
        if filtered_nodes:
            update_message["nodes"] = filtered_nodes
        if filtered_connections:
            update_message["connections"] = filtered_connections
        if deleted_node_ids:
            update_message["deleted_node_ids"] = deleted_node_ids
        if deleted_connection_ids:
            update_message["deleted_connection_ids"] = deleted_connection_ids
    else:
        update_message["spec"] = spec

    broadcast_ok = True
    if not skip_broadcast:
        logger.debug(
            "[CollabDebug] update_broadcast user=%s code=%s seq=%s version=%s ws_msg_id=%s",
            ctx.user.id, ctx.code,
            update_message.get("seq"), update_message.get("version"),
            update_message.get("ws_msg_id"),
        )
        broadcast_ok = await broadcast_to_others(ctx.code, ctx.user.id, update_message)
    else:
        logger.debug(
            "[CollabDebug] update_broadcast_skipped user=%s code=%s reason=duplicate_client_op"
            " seq=%s version=%s",
            ctx.user.id, ctx.code,
            update_message.get("seq"), update_message.get("version"),
        )

    if not broadcast_ok:
        logger.warning(
            "[WorkshopWS] broadcast failed for update — sending error to sender user=%s code=%s",
            ctx.user.id, ctx.code,
        )
        await _send(
            ctx,
            {
                "type": "error",
                "code": "broadcast_failed",
                "message": "Update could not be delivered. Please resync.",
            },
            "error",
        )
        return

    # Send the server-assigned version back to the sender (the "update_ack"
    # pattern used by ShareDB and Google Docs).  Without this the sender's
    # lastSequentialLiveVersion never advances past its own snapshot version,
    # so the next peer broadcast arrives as a false version gap and triggers a
    # costly pendingResync round-trip that silently drops intervening edits.
    ack_message: Dict[str, Any] = {
        "type": "update_ack",
        "ws_msg_id": update_message.get("ws_msg_id"),
    }
    if isinstance(update_message.get("version"), int):
        ack_message["version"] = update_message["version"]
    if isinstance(update_message.get("seq"), int):
        ack_message["seq"] = update_message["seq"]
    if client_op_id:
        ack_message["client_op_id"] = client_op_id
    await _send(ctx, ack_message, msg_type="update_ack")

    await get_online_collab_manager().touch_activity(ctx.code)
    await topk_record_room_activity(ctx.code)
    await topk_record_user_activity(int(ctx.user.id))

    logger.info(
        "[CollabDebug] merge_ok user=%s diagram=%s code=%s version=%s seq=%s"
        " broadcast_nodes=%d broadcast_conns=%d broadcast_del_nodes=%d broadcast_del_conns=%d",
        ctx.user.id, ctx.diagram_id, ctx.code,
        update_message.get("version"), update_message.get("seq"),
        len(update_message.get("nodes") or []),
        len(update_message.get("connections") or []),
        len(update_message.get("deleted_node_ids") or []),
        len(update_message.get("deleted_connection_ids") or []),
    )
