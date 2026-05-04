"""
Lightweight counters for WebSocket operations.

Multi-worker semantics
----------------------
Counters in the ``_local`` dict are **process-local**: each Uvicorn worker has
its own copy and the values returned by :func:`snapshot` are only meaningful
for that worker. When deployed behind multiple workers, the exposed values
under-count real system activity because each worker reports only the
fraction of traffic that landed on it.

The single global metric that is aggregated across workers is
``ws_active_total_redis``: it is stored as a Redis INCRBY counter and therefore
sums all workers' connection increments/decrements.

For Prometheus-style cross-worker aggregation of the other counters, consumers
should either:
  * scrape each worker individually and sum at the monitoring layer, or
  * opt into the TimeSeries-backed aggregation path (see
    ``p1-redis-timeseries-metrics`` in the collab plan) where per-sample
    ``TS.ADD`` calls are pushed to Redis so downstream queries can aggregate
    across workers without per-worker scraping.

The in-process counters are retained as a low-overhead observability channel
(no Redis round-trip on the hot path) and because CPython's GIL makes
single-key dict updates effectively atomic within an asyncio worker.

Copyright 2024-2025 北京思源智教科技有限公司 (Beijing Siyuan Zhijiao Technology Co., Ltd.)
All Rights Reserved
Proprietary License
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict

from services.redis.redis_async_client import get_async_redis
from services.online_collab.redis.redis8_features import (
    timeseries_enabled,
    ts_record_counter,
)

logger = logging.getLogger(__name__)

_local: Dict[str, int | float] = {
    # Per-endpoint active connection counters (all five endpoint types)
    "ws_chat_connections": 0,
    "ws_workshop_connections": 0,
    "ws_asr_connections": 0,
    "ws_translate_connections": 0,
    "ws_voice_connections": 0,
    # Fan-out throughput
    "ws_fanout_chat_published": 0,
    "ws_fanout_chat_received": 0,
    "ws_fanout_workshop_published": 0,
    "ws_fanout_workshop_received": 0,
    # Auth / rate-limit rejections
    "ws_auth_failures": 0,
    "ws_rate_limit_hits": 0,
    "ws_broadcast_send_failures": 0,
    "ws_live_spec_merge_failures": 0,
    "ws_collab_granular_lock_rejects": 0,
    "ws_canvas_collab_join_rate_limited": 0,
    # Phase-0 writer / fanout metrics
    "ws_slow_consumer_total": 0,
    "ws_coalesce_hit_total": 0,
    "ws_batch_frames_emitted_total": 0,
    "ws_writer_task_failed_total": 0,
    "ws_broadcast_shards_total": 0,
    "ws_partial_jsonb_flush_total": 0,
    "ws_full_jsonb_flush_total": 0,
    "ws_hexpire_downgrade_total": 0,
    "ws_redisjson_failure_total": 0,
    "ws_watcherror_retry_total": 0,
    "ws_fanout_publish_success_total": 0,
    "ws_fanout_publish_failure_total": 0,
    "ws_fanout_delivery_queue_drop_total": 0,
    "ws_idle_monitor_cycle_total": 0,
    "ws_cleanup_partition_size_total": 0,
    "ws_broadcast_latency_samples_total": 0,
    "ws_update_latency_samples_total": 0,
    # Sum accumulators for computing average latency in-process (no TDigest).
    "ws_update_latency_sum_ms": 0,
    "ws_broadcast_latency_sum_ms": 0,
    "ws_update_semaphore_wait_samples_total": 0,
    "ws_update_semaphore_wait_sum_ms": 0,
    "ws_load_editors_latency_samples_total": 0,
    "ws_read_live_spec_latency_samples_total": 0,
    # Phase-8 role-split metrics
    "ws_editor_connections": 0,
    "ws_viewer_connections": 0,
    "ws_viewer_snapshot_hits_total": 0,
    "ws_viewer_resync_total": 0,
    "ws_role_promotion_total": 0,
    "ws_role_demotion_total": 0,
    "ws_collab_snapshot_oversize_total": 0,
    "ws_collab_origin_reject_total": 0,
    "ws_collab_resync_total": 0,
    "ws_collab_update_schema_reject_total": 0,
    "ws_collab_partial_filter_notify_total": 0,
    "ws_resync_rl_check_failure_total": 0,
}

# Map registry endpoint labels → metric counter keys
_ENDPOINT_COUNTER: Dict[str, str] = {
    "chat": "ws_chat_connections",
    "collab": "ws_workshop_connections",
    "asr": "ws_asr_connections",
    "translate": "ws_translate_connections",
    "voice": "ws_voice_connections",
}


def _bump(key: str, delta: int = 1) -> None:
    """Increment a named in-process counter.

    CPython's GIL makes simple dict integer updates atomic; no lock required
    in a single-threaded asyncio process. When the Redis TimeSeries backend
    is enabled (``COLLAB_REDIS_TIMESERIES=1``), the increment is also
    fire-and-forget scheduled into ``TS.ADD workshop:ts:{key} * delta`` so
    downstream monitoring can aggregate across workers without per-worker
    scraping. Scheduling never awaits; failures are swallowed and logged at
    debug level inside ``redis8_features``.
    """
    _local[key] = _local.get(key, 0) + delta
    if not timeseries_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if loop.is_running():
        loop.create_task(ts_record_counter(key, float(delta)))


def record_ws_connection_delta(endpoint: str, delta: int) -> None:
    """
    Adjust the per-process connection counter for the given endpoint label.

    Used by ws_context.ws_managed_session for all five endpoint types.
    Unknown endpoint labels are silently ignored (future-proof).
    """
    key = _ENDPOINT_COUNTER.get(endpoint)
    if key:
        _bump(key, delta)


def record_ws_fanout_chat_published() -> None:
    """Count a chat message published to Redis fan-out."""
    _bump("ws_fanout_chat_published")


def record_ws_fanout_chat_received() -> None:
    """Count a chat fan-out message received from Redis on this worker."""
    _bump("ws_fanout_chat_received")


def record_ws_fanout_workshop_published() -> None:
    """Count a workshop message published to Redis fan-out."""
    _bump("ws_fanout_workshop_published")


def record_ws_fanout_workshop_received() -> None:
    """Count a workshop fan-out message received from Redis on this worker."""
    _bump("ws_fanout_workshop_received")


def record_ws_auth_failure() -> None:
    """Count a WebSocket authentication rejection."""
    _bump("ws_auth_failures")


def record_ws_rate_limit_hit() -> None:
    """Count a WebSocket per-connection rate limit hit."""
    _bump("ws_rate_limit_hits")


def record_ws_broadcast_send_failure() -> None:
    """Count a failed local workshop WebSocket send or fan-out publish/deliver."""
    _bump("ws_broadcast_send_failures")


def record_ws_live_spec_merge_failure() -> None:
    """Count failed Redis live-spec merge on collab ``update`` (Redis present)."""
    _bump("ws_live_spec_merge_failures")


def record_ws_collab_granular_lock_reject() -> None:
    """Count granular collab patches dropped entirely by lock filtering."""
    _bump("ws_collab_granular_lock_rejects")


def record_ws_canvas_collab_join_rate_limited() -> None:
    """Count canvas-collab WebSocket joins blocked by join rate limits."""
    _bump("ws_canvas_collab_join_rate_limited")


def record_ws_slow_consumer(reason: str = "") -> None:
    """Count slow-consumer evictions (queue full / send timeout)."""
    _bump("ws_slow_consumer_total")
    if reason:
        logger.debug("[WSMetrics] slow consumer evicted reason=%s", reason)


def record_ws_coalesce_hit(msg_type: str = "") -> None:
    """Count messages routed through the coalesce buffer instead of the queue."""
    _bump("ws_coalesce_hit_total")
    if msg_type:
        logger.debug("[WSMetrics] coalesce hit msg_type=%s", msg_type)


def record_ws_batch_frames_emitted() -> None:
    """Count node_editing_batch_ws frames emitted by the flush task."""
    _bump("ws_batch_frames_emitted_total")


def record_ws_writer_task_failed() -> None:
    """Count writer task exits due to send error (not clean shutdown)."""
    _bump("ws_writer_task_failed_total")


def record_ws_broadcast_shards(count: int) -> None:
    """Record number of shards used for a single room broadcast."""
    _bump("ws_broadcast_shards_total", count)


def record_ws_partial_jsonb_flush() -> None:
    """Count partial-JSONB flush (only changed keys written to PG)."""
    _bump("ws_partial_jsonb_flush_total")


def record_ws_full_jsonb_flush() -> None:
    """Count full-spec JSONB flush (structural rewrite to PG)."""
    _bump("ws_full_jsonb_flush_total")


def record_ws_hexpire_downgrade() -> None:
    """Count Redis HEXPIRE fallbacks (Redis version < 7.4)."""
    _bump("ws_hexpire_downgrade_total")


def record_ws_redisjson_failure_total() -> None:
    """Count RedisJSON live-spec command failures (no string fallback path)."""
    _bump("ws_redisjson_failure_total")


def record_ws_watcherror_retry() -> None:
    """Count WATCH/MULTI/EXEC retries due to concurrent writes."""
    _bump("ws_watcherror_retry_total")


def record_ws_fanout_publish_success() -> None:
    """Count successful Redis pub/sub publish operations."""
    _bump("ws_fanout_publish_success_total")


def record_ws_fanout_publish_failure() -> None:
    """Count failed Redis pub/sub publish operations."""
    _bump("ws_fanout_publish_failure_total")


def record_ws_fanout_delivery_queue_drop() -> None:
    """Count fan-out messages dropped when the local delivery queue is full."""
    _bump("ws_fanout_delivery_queue_drop_total")


def record_ws_idle_monitor_cycle() -> None:
    """Count idle-monitor loop cycles (one per configured interval)."""
    _bump("ws_idle_monitor_cycle_total")


def record_ws_cleanup_partition_size(row_count: int) -> None:
    """Accumulate the number of expired sessions purged in each cleanup run."""
    if row_count > 0:
        _bump("ws_cleanup_partition_size_total", row_count)


def record_ws_broadcast_latency(latency_ms: float) -> None:
    """
    Record a single broadcast latency sample (ms, end-to-end from enqueue to
    last-byte sent for a shard).

    The value is tracked in-process as a sample count; when Redis TimeSeries
    is enabled the raw value is forwarded to ``tdigest_record_latency`` so
    per-percentile queries (p50/p95/p99) can be derived from the T-Digest
    stored in Redis.
    """
    _bump("ws_broadcast_latency_samples_total")
    _local["ws_broadcast_latency_sum_ms"] = (
        _local.get("ws_broadcast_latency_sum_ms", 0) + latency_ms
    )
    if not timeseries_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if loop.is_running():
        from services.online_collab.redis.redis8_features import (  # pylint: disable=import-outside-toplevel
            tdigest_record_latency,
        )
        loop.create_task(tdigest_record_latency("broadcast_latency_ms", latency_ms))


def record_ws_update_latency(latency_ms: float) -> None:
    """
    Record the end-to-end latency (ms) of a single ``update`` message merge
    (from handler entry to after ``mutate_live_spec_after_ws_update`` returns).

    When Redis TimeSeries is enabled the raw value is forwarded to
    ``tdigest_record_latency`` so p50/p95/p99 percentiles can be queried
    cross-worker via the T-Digest stored in Redis.
    """
    _bump("ws_update_latency_samples_total")
    _local["ws_update_latency_sum_ms"] = (
        _local.get("ws_update_latency_sum_ms", 0) + latency_ms
    )
    if not timeseries_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if loop.is_running():
        from services.online_collab.redis.redis8_features import (  # pylint: disable=import-outside-toplevel
            tdigest_record_latency,
        )
        loop.create_task(tdigest_record_latency("update_latency_ms", latency_ms))


def record_ws_update_semaphore_wait_ms(wait_ms: float) -> None:
    """
    Record time spent waiting to acquire the per-process ``update`` merge
    semaphore (milliseconds).
    """
    _bump("ws_update_semaphore_wait_samples_total")
    _local["ws_update_semaphore_wait_sum_ms"] = (
        _local.get("ws_update_semaphore_wait_sum_ms", 0) + wait_ms
    )
    if not timeseries_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if loop.is_running():
        from services.online_collab.redis.redis8_features import (  # pylint: disable=import-outside-toplevel
            tdigest_record_latency,
        )
        loop.create_task(tdigest_record_latency("update_semaphore_wait_ms", wait_ms))


def record_ws_load_editors_latency_ms(latency_ms: float) -> None:
    """Record Redis HASH/JSON load_editors hot-path latency (ms)."""
    _bump("ws_load_editors_latency_samples_total")
    if not timeseries_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if loop.is_running():
        from services.online_collab.redis.redis8_features import (  # pylint: disable=import-outside-toplevel
            tdigest_record_latency,
        )
        loop.create_task(tdigest_record_latency("load_editors_ms", latency_ms))


def record_ws_read_live_spec_latency_ms(latency_ms: float) -> None:
    """Record read_live_spec hot-path latency (ms)."""
    _bump("ws_read_live_spec_latency_samples_total")
    if not timeseries_enabled():
        return
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        return
    if loop.is_running():
        from services.online_collab.redis.redis8_features import (  # pylint: disable=import-outside-toplevel
            tdigest_record_latency,
        )
        loop.create_task(tdigest_record_latency("read_live_spec_ms", latency_ms))


def record_ws_editor_connection_delta(delta: int) -> None:
    """Adjust in-process editor connection count (±1 on connect/disconnect)."""
    _bump("ws_editor_connections", delta)


def record_ws_viewer_connection_delta(delta: int) -> None:
    """Adjust in-process viewer connection count (±1 on connect/disconnect)."""
    _bump("ws_viewer_connections", delta)


def record_ws_viewer_snapshot_hit() -> None:
    """Count viewers that joined via the cached snapshot (not live spec)."""
    _bump("ws_viewer_snapshot_hits_total")


def record_ws_viewer_resync() -> None:
    """Count viewer resync requests (gap detected in seq)."""
    _bump("ws_viewer_resync_total")


def record_ws_role_promotion() -> None:
    """Count viewer → editor in-place promotions."""
    _bump("ws_role_promotion_total")


def record_ws_role_demotion() -> None:
    """Count editor → viewer in-place demotions."""
    _bump("ws_role_demotion_total")


def record_ws_collab_snapshot_oversize() -> None:
    """Count outbound collab snapshots dropped for exceeding size limit."""
    _bump("ws_collab_snapshot_oversize_total")


def record_ws_collab_origin_reject() -> None:
    """Count canvas-collab WebSocket upgrades rejected by Origin policy."""
    _bump("ws_collab_origin_reject_total")


def record_ws_collab_resync() -> None:
    """Count ``resync`` frames (snapshot pull) from editors and viewers."""
    _bump("ws_collab_resync_total")


def record_ws_resync_rate_limit_check_failure() -> None:
    """Redis error prevented the resync rate-limit check; resync was allowed."""
    _bump("ws_resync_rl_check_failure_total")


def record_ws_collab_update_schema_reject() -> None:
    """Structural / Pydantic rejection for granular ``update`` frames."""
    _bump("ws_collab_update_schema_reject_total")


def record_ws_collab_partial_filter_notify() -> None:
    """Notify path hit for partial lock filter (sender gets ``update_partial_filtered``)."""
    _bump("ws_collab_partial_filter_notify_total")


async def get_ws_metrics_snapshot() -> Dict[str, Any]:
    """Return a copy of in-process WebSocket counters plus optional Redis gauge."""
    snap: Dict[str, Any] = dict(_local)
    snap["timestamp"] = time.time()
    try:
        r = get_async_redis()
        if r:
            raw = await r.get("mg:ws:metrics:active_total")
            if raw is not None:
                snap["ws_active_total_redis"] = int(raw)
    except (ValueError, TypeError) as exc:
        logger.debug("[WSMetrics] Redis gauge parse failed: %s", exc)
    except (OSError, RuntimeError, AttributeError) as exc:
        logger.debug("[WSMetrics] Redis gauge read failed: %s", exc)

    # Room-size gauge: snapshot from in-process ACTIVE_CONNECTIONS.
    try:
        from services.features.workshop_ws_connection_state import (  # pylint: disable=import-outside-toplevel
            ACTIVE_CONNECTIONS,
        )
        snap["ws_room_sizes"] = {
            code: len(handles) for code, handles in ACTIVE_CONNECTIONS.items()
        }
        snap["ws_rooms_total"] = len(ACTIVE_CONNECTIONS)
        snap["ws_total_connections_local"] = sum(
            len(h) for h in ACTIVE_CONNECTIONS.values()
        )
    except Exception:  # pylint: disable=broad-except
        pass

    return snap


def ws_metrics_prometheus_text(snap: Dict[str, Any]) -> str:
    """Render selected WebSocket/collab counters in Prometheus text format."""
    lines = [
        "# HELP collab_active_sockets Active canvas collaboration sockets.",
        "# TYPE collab_active_sockets gauge",
        f"collab_active_sockets {int(snap.get('ws_workshop_connections', 0) or 0)}",
        "# HELP collab_active_rooms Active canvas collaboration rooms on this worker.",
        "# TYPE collab_active_rooms gauge",
        f"collab_active_rooms {int(snap.get('ws_rooms_total', 0) or 0)}",
    ]
    counter_map = {
        "collab_join_rate_limited_total": "ws_canvas_collab_join_rate_limited",
        "collab_auth_failures_total": "ws_auth_failures",
        "collab_disconnect_slow_consumer_total": "ws_slow_consumer_total",
        "collab_fanout_dropped_total": "ws_fanout_delivery_queue_drop_total",
        "collab_update_schema_reject_total": "ws_collab_update_schema_reject_total",
        "collab_snapshot_oversize_total": "ws_collab_snapshot_oversize_total",
        "collab_origin_reject_total": "ws_collab_origin_reject_total",
        "collab_resync_total": "ws_collab_resync_total",
    }
    for metric_name, snap_key in counter_map.items():
        lines.append(f"# TYPE {metric_name} counter")
        lines.append(f"{metric_name} {int(snap.get(snap_key, 0) or 0)}")
    return "\n".join(lines) + "\n"


def collab_ws_metrics_alerts(snap: Dict[str, Any]) -> list[str]:
    """
    Return human-readable alert tokens when counters cross operational thresholds.

    Intended for log-based monitoring when Prometheus is not deployed: callers
    attach the list to ``/health/websocket`` JSON and may scrape logs for these
    tokens.
    """
    alerts: list[str] = []

    def _int(key: str, default: int = 0) -> int:
        try:
            return int(snap.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    if _int("ws_live_spec_merge_failures") > 0:
        alerts.append("ws_live_spec_merge_failures_nonzero")
    if _int("ws_writer_task_failed_total") > 0:
        alerts.append("ws_writer_task_failed_nonzero")
    if _int("ws_watcherror_retry_total") > 200:
        alerts.append("ws_watcherror_retry_high")
    if _int("ws_slow_consumer_total") > 0:
        alerts.append("ws_slow_consumer_nonzero")
    if _int("ws_broadcast_send_failures") > 0:
        alerts.append("ws_broadcast_send_failures_nonzero")
    if _int("ws_collab_snapshot_oversize_total") > 0:
        alerts.append("ws_collab_snapshot_oversize_nonzero")
    if _int("ws_fanout_publish_failure_total") > 0:
        alerts.append("ws_fanout_publish_failure_nonzero")
    if _int("ws_redisjson_failure_total") > 0:
        alerts.append("ws_redisjson_failure_nonzero")
    return alerts


async def redis_increment_active_total(delta: int) -> None:
    """Best-effort global active WebSocket count in Redis (all workers)."""
    try:
        r = get_async_redis()
        if not r:
            return
        key = "mg:ws:metrics:active_total"
        async with r.pipeline() as pipe:
            pipe.incrby(key, delta)
            pipe.expire(key, 86400)
            await pipe.execute()
    except (OSError, RuntimeError, AttributeError, TypeError) as exc:
        logger.debug("[WSMetrics] Redis increment failed: %s", exc)
