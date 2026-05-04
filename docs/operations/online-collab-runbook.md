# Online Collaboration Runbook

## Scope

This runbook covers the MindGraph online collaboration path:

- FastAPI WebSocket endpoint: `/api/ws/canvas-collab/{code}`
- Redis room state, participant state, live spec, fanout, and idle cleanup keys
- PostgreSQL `diagrams.workshop_code` session fields and persisted diagram spec
- Synthetic probe: `scripts/collab_synthetic_probe.py`

## Required Production Settings

Set these in production before enabling online collaboration:

- `COLLAB_STRICT_PROD_GUARDS=1`
- `COLLAB_WS_ALLOWED_ORIGINS=https://app.example.com`
- `COLLAB_WS_ALLOW_MISSING_ORIGIN=0`
- `COLLAB_FANOUT_ORIGIN_SECRET=<random 32+ byte secret>`
- `COLLAB_JOIN_RL_FAIL_OPEN=false`
- `COLLAB_WS_MAX_PER_USER_ENDPOINT=5`
- `COLLAB_WS_MAX_PER_USER_GLOBAL=20`
- `COLLAB_WS_REDIS_GLOBAL_SOCKET_CAP=1`
- `WORKSHOP_MAX_PARTICIPANTS=500`
- `COLLAB_WS_MAX_TEXT_BYTES=1048576`
- `COLLAB_WS_MAX_JSON_DEPTH=48`
- `WORKSHOP_JOIN_RESUME_TTL_SEC=900`
- `COLLAB_WS_JWT_REVALIDATE_SEC=180`
- `LIVE_SPEC_SHUTDOWN_FLUSH_CONCURRENCY=8`
- `LIVE_SPEC_HEALTH_STALE_SAMPLE=80`

Keep `COLLAB_REDIS_HASH_TAGS=1` unless all Redis keys have expired and every
worker is flipped at the same time. Room-scoped keys are hash-tagged for
same-slot operations; global registry and idle-score keys are cleaned separately
and must still be monitored during Redis Cluster migrations.

## Synthetic Probe

Use a canary workshop code and a service account token with enough permission to
join the room. The probe opens two WebSocket clients and verifies the normal
join, snapshot, ping, update acknowledgement, and clean leave path.

```powershell
$env:COLLAB_PROBE_WS_URL = "wss://app.example.com/api/ws/canvas-collab/ABC-123?token=<jwt>"
$env:COLLAB_PROBE_DIAGRAM_ID = "<diagram-id>"
$env:COLLAB_PROBE_REQUIRE_FULL_CYCLE = "1"
python scripts/collab_synthetic_probe.py
```

Exit codes:

- `0`: both clients completed the configured probe.
- `1`: one or both clients failed the WebSocket protocol check.
- `2`: the probe URL was missing.

Set `COLLAB_PROBE_REQUIRE_FULL_CYCLE=0` only for smoke checks where the canary
cannot safely mutate a diagram. That mode still verifies connect, join, snapshot,
and ping, but it does not prove update persistence.

## Health Checks

Check these when collaboration degrades:

- Redis process health and app Redis startup logs.
- WebSocket origin rejects. A spike usually means a bad frontend origin,
  proxy host rewrite, or unauthorized embedding attempt.
- Join rate-limit rejects. A spike can indicate reconnect loops or token abuse.
- Live-spec flush failures. These are data-loss prevention events; idle cleanup
  should keep room state and retry instead of destroying the session.
- `/health/websocket` `collab_alerts` containing
  `live_spec_db_flush_lag_detected`. This means Redis has accepted edits that
  are older than the configured flush window and not yet reflected in Postgres.
- Slow-consumer evictions and outbound queue drops. These point to network or
  client performance problems.

## Incident Response

### Users Cannot Join

1. Confirm `COLLAB_WS_ALLOWED_ORIGINS` contains the exact browser origin.
2. Confirm the JWT on the WebSocket URL is valid and not expired.
3. Check join rate-limit settings and Redis availability.
4. Verify the workshop code exists in Redis `sessionmeta` and in PostgreSQL
   `diagrams.workshop_code`.

### Edits Stop Syncing

1. Run the synthetic probe against the canary room.
2. Check Redis fanout logs for invalid origin-secret envelopes.
3. Check update rejection logs for version gaps, schema errors, or lock filters.
4. Verify `COLLAB_WS_MAX_TEXT_BYTES` is large enough for full snapshot frames.

### Idle Stop Does Not Clear a Room

An idle room that remains active after the timeout usually means the final
live-spec flush failed. This is intentional: Redis state is retained so the next
cleanup pass can retry without losing edits.

1. Inspect live-spec flush failure logs for DB lock timeout or advisory lock
   contention.
2. Confirm PostgreSQL is healthy and the target diagram row is not locked by a
   long transaction.
3. After the database recovers, let cleanup retry or have the owner stop the
   session again.
4. Do not purge live-spec keys manually unless the persisted `diagrams.spec`
   has been verified.

### Duplicate Workshop Code Migration Fails

The unique active workshop-code migration aborts if duplicate non-deleted rows
already exist.

1. List duplicate active `workshop_code` values in PostgreSQL.
2. Decide which row owns each active session.
3. Clear stale `workshop_code` fields on non-owning rows.
4. Re-run the migration.

## Manual Recovery Notes

- Prefer ending sessions through the owner stop path so live spec flush,
  database clear, broadcast, and Redis destroy stay ordered.
- Avoid deleting Redis live-spec keys before checking the database spec.
- If a worker crashes during shutdown, retained live-spec keys should be flushed
  by the next cleanup or shutdown flush pass.
- When rotating `COLLAB_FANOUT_ORIGIN_SECRET`, deploy all workers together or
  expect cross-worker fanout drops during the rollout.

## Inspecting A Stuck Room

Use the normalized workshop code:

```shell
HGETALL workshop:sessionmeta:{CODE}
HLEN workshop:participants:{CODE}
ZSCORE workshop:idle_scores CODE
GET workshop:code_to_diagram:{CODE}
JSON.GET workshop:live_spec:{CODE} $
```

If hash tags are disabled, remove the braces around `CODE`.

## Synthetic Probe

Use `scripts/collab_synthetic_probe.py` with:

- `COLLAB_PROBE_WS_URL`
- `COLLAB_PROBE_TIMEOUT_S`
- `COLLAB_PROBE_DIAGRAM_ID`
- `COLLAB_PROBE_SEND_UPDATE=1`

The probe validates join, snapshot, ping/pong, and optionally an empty update ack.
