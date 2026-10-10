# MindGraph — Online Collaboration Architecture

Canvas workshop WebSocket fan-out. Module docs are listed in [README.md](README.md). Implementation: `services/features/ws_redis_fanout_publish.py`, `services/features/ws_pg_notify_fanout.py`, and `services/online_collab/`. Operator steps: [online collab runbook](operations/online-collab-runbook.md).

_Checked against those packages on 2026-10-10. Redis key names are defined in `services/online_collab/`._

---

## Overview

The online collaboration (workshop) module lets teachers collaboratively edit a diagram over WebSocket. Up to 200–500 concurrent users per session are targeted. The stack is:

- **FastAPI** (Uvicorn workers) — WebSocket endpoints
- **Redis 8.6** — session state, live-spec storage, pub/sub broadcast, rate limiting
- **PostgreSQL 18.3** — authoritative diagram storage, session lifecycle

---

## Fanout Topology

```
Client A  ──ws──►  Worker-1  ──SPUBLISH──►  Redis Pub/Sub channel
                                              │
                        ┌─────────────────────┤
                        │                     │
                     Worker-1              Worker-2  …  Worker-N
                   (listener)            (listener)
                        │                     │
                    local sockets         local sockets
                  (ACTIVE_CONNECTIONS)   (ACTIVE_CONNECTIONS)
```

### Delivery chain (per broadcast)

1. **Sender** calls `publish_workshop_fanout_async(envelope)`.
2. `SPUBLISH` (sharded pub/sub, default) or `PUBLISH` (fallback) to the workshop channel.
3. Each worker's `ws_redis_fanout_listener` receives the message and calls `deliver_local_workshop_broadcast`.
4. Payload is pre-encoded to bytes **once**, then fanned out to room shards via `asyncio.TaskGroup + asyncio.Semaphore(50)`.
5. Each shard iterates its `ConnectionHandle` objects, calling `handle.send_queue.put_nowait(payload)`.
6. Each handle's `_writer_loop` (background `asyncio.Task`) dequeues and calls `ws.send_bytes`.

### Fallback chain

```
SPUBLISH  ──fails──►  PUBLISH  ──fails──►  PG LISTEN/NOTIFY  (COLLAB_PG_NOTIFY_FALLBACK=1)
```

When `PUBLISH` raises `RedisError`, a background task publishes to the per-machine PG channel (`collab_{hostname}`). A `asyncio.Task` listener runs `LISTEN` on startup and calls `deliver_local_workshop_broadcast` on notifications.

---

## Per-Connection Writer Architecture

```
incoming ws frame
       │
  handler coroutine
       │
  handle.send_queue.put_nowait(payload)   ← O(1), non-blocking
       │
  _writer_loop (background asyncio.Task)
       │
  ws.send_bytes(payload)
```

- **Bounded queue** (`asyncio.Queue(maxsize=WORKSHOP_WS_QUEUE_SIZE)`).
- **Slow-consumer eviction**: if `put_nowait` raises `QueueFull`, the handle is evicted and the WebSocket is closed with code 4008.
- **Coalescing**: `node_editing` frames within a 50 ms window are merged into a batch frame per peer, reducing queue depth in large rooms.
- **Backpressure policy**: `update` / `node_editing` use `put_nowait` (drop-on-full); `join` / `room_state` / `error` always enqueue.

---

## Participant Storage (Redis 8.6 HASH + HEXPIRE)

```
participants:{code}   (HASH)
  field: str(user_id)
  value: int(join_epoch_seconds)
  per-field TTL: HEXPIRE (Redis 7.4+), fallback: whole-key EXPIRE
```

Operations:
- **Join**: `HSET` + `HEXPIRE` (or `EXPIRE` on older Redis).
- **Heartbeat**: `HEXPIRE` with `GT` flag (only extends, never shortens).
- **Leave**: `HDEL` + `HLEN` (check empty → maybe flush spec to PG).
- **Count**: `HLEN` (replaces `SCARD`).
- **List**: `HKEYS` (replaces `SMEMBERS`).

---

## Live Spec Storage

### Write path

```
WS update → mutate_live_spec_after_ws_update
                │
         json_backend_available?
          Yes ─► _mutate_live_spec_json        (RedisJSON fast path)
                    │                                │
               JSON.MERGE (granular)          JSON.SET (full replace)
                    │                                │
                 on failure ──────────────────►  WATCH/MULTI/EXEC loop
          No  ─► WATCH/MULTI/EXEC loop         (up to 10 retries, exp. backoff)
```

### Partial JSONB flush (PostgreSQL)

`apply_live_update` returns `(doc, version, changed_keys: frozenset)`.

- `__full__` sentinel → full column write: `UPDATE diagrams SET spec = :spec WHERE id = :id`.
- Otherwise → partial write: `UPDATE diagrams SET spec = jsonb_set(jsonb_set(spec, '{nodes}', ...), '{connections}', ...)` for only the changed top-level keys, cutting wire traffic 70–90%.

Changed keys are tracked in Redis set `workshop:live_changed_keys:{code}` and atomically read-and-cleared before each DB flush.

---

## Session Cleanup (PostgreSQL 18 MERGE)

```sql
MERGE INTO diagrams AS t
USING (
    SELECT id, workshop_code
    FROM   diagrams
    WHERE  workshop_code IS NOT NULL
      AND  NOT is_deleted
      AND  workshop_expires_at IS NOT NULL
      AND  workshop_expires_at <= :now
) AS s ON t.id = s.id
WHEN MATCHED THEN
    UPDATE SET workshop_code = NULL, ...
RETURNING t.id, s.workshop_code   -- s.workshop_code = pre-update value
```

`RETURNING s.workshop_code` (not `t.workshop_code`) gives the original code so Redis keys can be purged. Each cleanup run is gated by a 15-minute NX lock with a 5-minute heartbeat.

---

## Rate Limiting

Join rate limiting (per user + per IP) is performed by a single atomic Lua script executed via `EVALSHA` (preloaded at startup via `SCRIPT LOAD`). A single Redis round-trip atomically checks and increments both counters, preventing race conditions between separate checks.

---

## Redis Key Namespace

| Key pattern | Type | Purpose |
|-------------|------|---------|
| `workshop:session:{code}` | HASH | Session metadata (diagram_id, org_id, visibility, expires_at) |
| `workshop:session_meta:{code}` | HASH | Lightweight meta cache (used by CLIENT TRACKING) |
| `workshop:registry:{code}` | HASH | Code→diagram mapping |
| `participants:{code}` | HASH | Participant user_ids with per-field TTL |
| `workshop:live_spec:{code}` | String/JSON | Live diagram spec (RedisJSON or plain string) |
| `workshop:live_changed_keys:{code}` | SET | Top-level spec keys changed since last DB flush |
| `workshop:live_flush_pending:{code}` | String | Debounce key for DB flush scheduling |
| `workshop:live_last_db_flush:{code}` | String | Timestamp of last successful DB flush |
| `workshop:idle_scores` | ZSET | code → last_activity_epoch (for idle monitoring) |
| `workshop:idle_kick_lock:{code}` | String | NX lock for idle kick (one worker) |
| `workshop:idle_warning_sent:{code}` | String | Flag: idle warning already sent to room |
| `workshop:mutation_idle:{code}` | String | Last mutation timestamp (for empty-room flush trigger) |
| `workshop:editors:{code}` | HASH | Node → user_id active editor lock |
| `workshop:rate_limit:join:user:{uid}` | String | User join rate limit counter |
| `workshop:rate_limit:join:ip:{ip}` | String | IP join rate limit counter |

---

## Environment Variable Reference

| Variable | Default | Purpose |
|---|---|---|
| `COLLAB_REDIS_JSON_LIVE_SPEC` | `1` | RedisJSON for live-spec storage (0 = WATCH loop only) |
| `COLLAB_REDIS_SPUBLISH` | `1` | SPUBLISH (sharded pub/sub) for broadcast |
| `COLLAB_REDIS_STREAMS_AUDIT` | `0` | XADD audit log after each publish |
| `COLLAB_REDIS_WAIT_DURABILITY` | `0` | WAIT 1 200 after create/destroy session pipeline |
| `COLLAB_REDIS_HASH_TAGS` | `0` | Redis hash tags for cluster key co-location |
| `COLLAB_PG_NOTIFY_FALLBACK` | `0` | PG LISTEN/NOTIFY fallback when Redis publish fails |
| `COLLAB_IDLE_MONITOR_CONCURRENCY` | `20` | Max concurrent stale-code evaluations per cycle |
| `COLLAB_JSON_THREAD_OFFLOAD_BYTES` | `65536` | Payload size threshold for thread-pool JSON offloading |
| `WORKSHOP_FANOUT_SHARD_CONCURRENCY` | `50` | Max concurrent shard tasks in fanout delivery |
| `WORKSHOP_SLOW_CONSUMER_EVICT` | `1` | Evict slow consumers on queue full |
| `DATABASE_POOL_HARD_ASSERT` | `0` | Abort startup when worker_count × pool_size > max_connections |
| `DATABASE_QUERY_CACHE_SIZE` | `1200` | SQLAlchemy compiled-statement LRU size |

---

## Observability Counters (`ws_metrics.py`)

| Counter | Description |
|---------|-------------|
| `ws_watcherror_retry_total` | WATCH/MULTI/EXEC retries (live-spec contention) |
| `ws_hexpire_downgrade_total` | HEXPIRE → EXPIRE downgrades (Redis < 7.4) |
| `ws_redisjson_fallback_total` | RedisJSON failures → WATCH loop fallback |
| `ws_fanout_publish_success_total` | Successful Redis pub/sub publishes |
| `ws_fanout_publish_failure_total` | Failed Redis pub/sub publishes |
| `ws_idle_monitor_cycle_total` | Idle-monitor cycles with stale codes found |
| `ws_cleanup_partition_size_total` | Expired sessions purged across cleanup runs |
| `ws_broadcast_latency_samples_total` | Broadcast latency samples (T-Digest p50/p95/p99 when `COLLAB_REDIS_TIMESERIES=1`) |
| `ws_slow_consumer_total` | Slow-consumer evictions |
| `ws_coalesce_hit_total` | Messages merged by the coalesce buffer |
| `ws_partial_jsonb_flush_total` | Partial JSONB flushes (only changed keys) |
| `ws_full_jsonb_flush_total` | Full-spec JSONB flushes (structural rewrites) |

When `COLLAB_REDIS_TIMESERIES=1`, all counters are also forwarded to Redis TimeSeries (`TS.ADD workshop:ts:{key} * delta`) for cross-worker aggregation without per-worker scraping.

---

## PostgreSQL 18 Deployment Notes

```ini
# postgresql.conf recommended settings for MindGraph online collab
io_method = worker          # async worker I/O (default in PG18)
# io_method = io_uring      # on Linux 5.1+ with io_uring support

max_connections = 150       # must exceed worker_count × async_pool_size
effective_cache_size = 12GB # 75% of RAM on a dedicated PG host
checkpoint_completion_target = 0.9
max_wal_size = 4GB
```

MindGraph defaults: 4 workers × 25 connections = 100; `max_connections = 150` leaves headroom for admin/monitoring sessions.
