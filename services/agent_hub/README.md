# MindGraph Agent Hub

Orchestration for **multiple agent surfaces** (mobile Kitty, MindMate, workshop, future DingTalk). **`P0`** owns **Kitty / voice scope** lifecycle: global Redis refcount, preempt/cleanup ordering, pairing snapshot.

## Hub session contract (Kitty-first)

`MindGraphAgentHub` is the top-level session owner. Kitty runtime state is a child of a hub session.

- `open_session(user_id, client_lane, source_module)` creates a hub session id.
- `bind_scope(...)` and `switch_scope(...)` keep diagram scope binding and revision in one place.
- `get_diagram_context(...)` is the unified mobile bootstrap read path.
- `prepare_kitty_start_context(...)` is the unified WS-start hydrate path.
- `apply_diagram_spec_mutation(...)` enforces expected revision, idempotency replay, and ordered persistence:
  1. optional library snapshot write
  2. Redis `live_spec` upsert
- `close_session(...)` terminates the hub session lifecycle.

| Path | Role |
|------|------|
| [`scope_lifecycle.py`](scope_lifecycle.py) | `MindGraphAgentHub`, control dispatch, refcount policy |
| [`snapshot.py`](snapshot.py) | `build_desktop_pairing_snapshot` for mobile introspection |
| [`matrix_bus.py`](matrix_bus.py) | Stub `DiagramCommandBus` for `P3` channel spine |

**Primitives** (Redis keys, pub/sub publish, Lua refcount helpers) live under [`services/kitty/`](../kitty/).

**Load balancer:** prefer **sticky sessions** to `/ws/kitty` across workers (latency); refcount remains authoritative for correctness.

## Environment

- `KITTY_CONTROL_SHARED_SECRET` — set when `DEBUG=False` so publishers and subscribers accept the same signed control payloads.
- `KITTY_WS_REFCOUNT_TTL_SECONDS` — optional; default min(1h, session TTL).
- `KITTY_REFCOUNT_USE_EVALSHA` — default `1` (cached Lua); set `0` for plain `EVAL` if needed.

## Production checklist

- Redis reachable from every API worker; identical `KITTY_CONTROL_*` and channel across processes.
- Invalid control scopes are rejected before dispatch; prefer sticky LB to `/ws/kitty` for lower churn.
- Watch `ws_kitty_*` metrics and Agent Hub **warning** logs for refcount attach/detach failures (Redis outages).

## Structured logging

Kitty control and hub paths pass ``extra=kitty_extra(...)`` from [`services/kitty/kitty_observability.py`](../kitty/kitty_observability.py). Ship logs to an engine that indexes **custom fields** (e.g. `kitty_event`, `kitty_scope`, `kitty_user_id`, `kitty_reason`, `kitty_error_type`) for dashboards and traces.

## Metrics and RED-style alerting

Counters live in `services/infrastructure/monitoring/ws_metrics.py` (in-process; optionally mirrored to Redis TimeSeries when enabled). Suggested **rate / errors / drift** signals:

| Counter | Suggested use |
|---------|----------------|
| `ws_kitty_control_received_total` vs `ws_kitty_control_cleanup_applied_total` | **Rate:** large sustained gap under active Kitty traffic → messages ignored, no local scope, or auth rejects. |
| `ws_kitty_control_message_ignored_total` | **Errors / noise:** correlate spikes with `kitty_event=control_auth_rejected` in logs. |
| `ws_kitty_refcount_attach_failed_total` / `ws_kitty_refcount_detach_failed_total` | **Errors:** Redis down, Lua errors, or script policy; alert on increase during otherwise healthy traffic. |
| `ws_kitty_control_cleanup_not_configured_total` | **Errors:** wiring bug (`configure_kitty_voice_cleanup` never called); should stay at zero in production. |
| `ws_kitty_control_voice_cleanup_failed_total` | **Errors:** uncaught failures from voice teardown; investigate stack in `kitty_event=voice_cleanup_failed`. |
| `ws_kitty_control_dispatch_exception_total` | **Errors:** unexpected errors escaping dispatch in the pub/sub listener; should be near zero. |
| `ws_kitty_refcount_meta_drift_total` | **Drift:** sessionmeta vs refcount mismatch in pairing snapshot; tune alerts if noisy. |

**Duration** is not centrally tracked for Kitty today; consider spans around `cleanup_voice_by_diagram_session` if you adopt OpenTelemetry.
