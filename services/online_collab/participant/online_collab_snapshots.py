"""Send live Redis workshop spec snapshots to canvas-collab WebSocket clients."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Mapping, Optional

from redis.exceptions import RedisError

from services.features.workshop_ws_connection_state import (
    AnyHandle,
    ViewerHandle,
    enqueue,
)
from services.redis.redis_async_client import get_async_redis
from services.online_collab.spec.online_collab_live_spec import spec_for_snapshot
from services.online_collab.spec.online_collab_live_spec_ops import ensure_live_spec_seeded
from services.online_collab.spec.online_collab_viewer_snapshot import (
    ensure_snapshot_task,
    read_viewer_snapshot,
)
from services.online_collab.lifecycle.online_collab_redis_ttl import (
    get_online_collab_redis_ttl_seconds,
)
from services.online_collab.redis.online_collab_redis_keys import (
    live_spec_key,
    snapshot_seq_key,
)
from services.online_collab.spec.online_collab_live_spec_json import parse_json_get_bulk

logger = logging.getLogger(__name__)

_LIVE_SPEC_AND_SEQ_LUA = """
local blob = redis.call('JSON.GET', KEYS[1], '$')
local seq_raw = redis.call('GET', KEYS[2])
return {blob, seq_raw}
"""

_SNAPSHOT_UNAVAILABLE_MSG = (
    "Diagram state temporarily unavailable. Please reconnect or use resync."
)
_SNAPSHOT_OVERSIZE_MSG = (
    "Diagram snapshot is too large to send over this connection. "
    "Try reconnecting; if the problem persists, reduce diagram size or contact support."
)


def _collab_snapshot_max_bytes() -> int:
    raw = os.environ.get("COLLAB_WS_SNAPSHOT_MAX_BYTES")
    default = 4_194_304
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _snapshot_json_byte_length(payload: Mapping[str, Any]) -> int:
    return len(
        json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8"),
    )


def _decode_lua_bulk_string(val: Any) -> Optional[str]:
    if val is None:
        return None
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    if isinstance(val, str):
        return val if val else None
    return str(val)


def _parse_seq_from_lua(val: Any) -> Optional[int]:
    text = _decode_lua_bulk_string(val)
    if text is None or not text.strip():
        return None
    try:
        return int(text.strip())
    except ValueError:
        return None


async def _enqueue_snapshot_or_oversize(
    handle: AnyHandle,
    diagram_id: str,
    spec: Mapping[str, Any],
    version: int,
    seq: Optional[int] = None,
) -> None:
    body: Dict[str, Any] = {
        "type": "snapshot",
        "diagram_id": diagram_id,
        "spec": dict(spec) if not isinstance(spec, dict) else spec,
        "version": version,
    }
    if seq is not None:
        body["seq"] = seq
    limit = _collab_snapshot_max_bytes()
    if _snapshot_json_byte_length(body) > limit:
        try:
            from services.infrastructure.monitoring.ws_metrics import (
                record_ws_collab_snapshot_oversize,
            )
            record_ws_collab_snapshot_oversize()
        except Exception:
            pass
        logger.warning(
            "[CollabSnapshot] oversize diagram_id=%s bytes>%s",
            diagram_id,
            limit,
        )
        await enqueue(
            handle,
            {
                "type": "error",
                "message": _SNAPSHOT_OVERSIZE_MSG,
                "snapshot_oversize": True,
                "diagram_id": diagram_id,
            },
            "error",
        )
        return
    await enqueue(handle, body, "snapshot")


async def websocket_send_live_spec_snapshot(
    handle: Optional[AnyHandle],
    code: str,
    diagram_id: str,
) -> None:
    """
    Push authoritative diagram JSON (join-time snapshot).

    Viewers: read from the cached snapshot key (workshop:snapshot:{code}) to
    avoid hitting the hot live_spec key during reconnect storms.  Falls back
    to the live spec path if the snapshot is not yet available.
    Editors/host: read live spec directly (no caching layer needed).
    """
    if handle is None:
        return

    if isinstance(handle, ViewerHandle):
        ensure_snapshot_task(code)
        cached = await read_viewer_snapshot(code)
        if cached is not None:
            try:
                from services.infrastructure.monitoring.ws_metrics import (
                    record_ws_viewer_snapshot_hit,
                )
                record_ws_viewer_snapshot_hit()
            except Exception:
                pass
            raw_seq = cached.get("seq")
            viewer_seq: Optional[int] = (
                int(raw_seq)
                if isinstance(raw_seq, (int, float)) and raw_seq > 0
                else None
            )
            logger.debug(
                "[CollabSnapshot] viewer_cache_hit code=%s diagram_id=%s seq=%s version=%s",
                code, diagram_id, viewer_seq, cached.get("version"),
            )
            await _enqueue_snapshot_or_oversize(
                handle,
                diagram_id,
                cached.get("spec", {}),
                int(cached.get("version", 1)),
                seq=viewer_seq,
            )
            return
        logger.debug(
            "[CollabSnapshot] viewer_cache_miss code=%s diagram_id=%s — falling back to live spec",
            code, diagram_id,
        )

    redis_client = get_async_redis()
    if not redis_client:
        logger.warning(
            "[CollabSnapshot] no Redis client — snapshot unavailable code=%s user=%s",
            code, getattr(handle, "user_id", "?"),
        )
        await enqueue(
            handle,
            {"type": "error", "message": _SNAPSHOT_UNAVAILABLE_MSG},
            "error",
        )
        return
    try:
        ttl_sec = await get_online_collab_redis_ttl_seconds(diagram_id, code=code)
        doc: Optional[Dict[str, Any]] = None
        snapshot_seq_val: Optional[int] = None
        try:
            pair = await redis_client.eval(
                _LIVE_SPEC_AND_SEQ_LUA,
                2,
                live_spec_key(code),
                snapshot_seq_key(code),
            )
            if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                raw_spec, raw_seq = pair[0], pair[1]
                blob = _decode_lua_bulk_string(raw_spec)
                if blob:
                    doc = parse_json_get_bulk(blob)
                snapshot_seq_val = _parse_seq_from_lua(raw_seq)
        except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
            logger.debug(
                "[CollabSnapshot] atomic spec+seq read failed code=%s: %s",
                code, exc,
            )
        if not doc:
            doc = await ensure_live_spec_seeded(
                redis_client,
                code,
                diagram_id,
                ttl_sec,
            )
            if doc:
                snapshot_seq_val = _parse_seq_from_lua(
                    await redis_client.get(snapshot_seq_key(code)),
                )
        snap = spec_for_snapshot(doc) if doc else {}
        ver = int(doc.get("v", 1)) if doc else 1
        logger.debug(
            "[CollabSnapshot] snapshot_sent code=%s diagram_id=%s user=%s ver=%s seq=%s",
            code, diagram_id, getattr(handle, "user_id", "?"), ver, snapshot_seq_val,
        )
        await _enqueue_snapshot_or_oversize(
            handle, diagram_id, snap, ver, seq=snapshot_seq_val,
        )
    except (RedisError, OSError, RuntimeError, TypeError, ValueError) as exc:
        logger.warning("Failed to send live spec snapshot: %s", exc)
