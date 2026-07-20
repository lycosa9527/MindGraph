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

## Diagram mutation contract (`MutationOp`)

Authoritative canvas merges use **exactly two** string ops on `mutation_cmd["op"]` (see
[`scope_lifecycle.py`](scope_lifecycle.py) / `MindGraphAgentHub.apply_diagram_spec_mutation`):

| `op` | Meaning |
|------|---------|
| `replace_context` | Default when omitted or not `patch_context`: replace hub merge input with `mutation_cmd["context"]`. |
| `patch_context` | Shallow-merge top-level keys of `context` and shallow-merge `diagram_data` with the delta. |

**Optional:** `persist_library: true` plus `library_snapshot` (dict) triggers `save_diagram` for the
current `diagram_library_id`. Bridge code under `services/kitty/` MUST NOT invent other op names.

Kitty realtime paths that call the hub today include `context.hub_context.apply_kitty_ws_context_patch`
(`context_update` WS). Verified diagram edits persist via **client** `context_update` after canvas
proof (`diagramEditHubPersist`); legacy non-verified voice edits may still use
`diagram.hub_bridge.try_sync_voice_diagram_to_hub`.

## Kitty WebSocket → hub call sequence (reference)

Typical successful `/ws/kitty/{diagram_session_id}` session matches this order in
[`services/kitty/ws/realtime.py`](../kitty/ws/realtime.py)
(registration under [`routers/features/kitty/kitty_routes.py`](../../routers/features/kitty/kitty_routes.py)):

1. `open_session(..., source_module="kitty_ws")` — allocate `hub_session_id`.
2. `preempt_handshake(diagram_scope, user_id)` — single-active-kitty policy on scope.
3. After client `start` frame: `prepare_kitty_start_context(...)` — library/bootstrap merge.
4. `set_kitty_runtime(..., connected=False)` — register voice and agent session ids before Omni is up.
5. `register_kitty_connection(diagram_scope, user_id)` then `set_kitty_runtime(..., connected=True)`.
6. On each `context_update` message: `apply_kitty_ws_context_patch` → hub `apply_diagram_spec_mutation`.
7. On socket teardown (finally): `set_kitty_runtime(..., connected=False, agent_session_id=None)`,
   `unregister_kitty_connection(...)`, `close_session(hub_session_id, ...)`.

Inbound JSON dispatch for audio/text/control is centralized in
[`services/kitty/ws/inbound.py`](../kitty/ws/inbound.py).
Diagram intents route through [`services/kitty/routing/command_router.py`](../kitty/routing/command_router.py)
and Omni native tool calling.

| Path | Role |
|------|------|
| [`scope_lifecycle.py`](scope_lifecycle.py) | `MindGraphAgentHub`, control dispatch, refcount policy |
| [`snapshot.py`](snapshot.py) | `build_desktop_pairing_snapshot` for mobile introspection |
| [`matrix_bus.py`](matrix_bus.py) | Re-export of `diagram_spine.DiagramCommandBus` |
| [`diagram_spine/`](diagram_spine/) | Bus front door: policy, types, channel origins |

### MindMate integration (stub)

Register at startup: `register_channel_adapter("mindmate")`. Future MindMate diagram edits use the same
`DiagramCommandRequest` envelope with `origin=MINDMATE` and a canvas transport when wired.

**Primitives** (Redis keys, pub/sub publish, Lua refcount helpers) live under [`services/kitty/`](../kitty/).

## Desktop navigation queue (not diagram truth)

Cross-device **pairing and navigation** use Redis helpers that are intentionally **narrow**:

- [`kitty_desktop_focus.py`](../kitty/infra/desktop/kitty_desktop_focus.py) — last library/diagram id the user focused on desktop (mobile aligns `/ws/kitty/{scope}`). **Not** a channel for `diagram_data`.
- [`kitty_desktop_action_queue.py`](../kitty/infra/desktop/kitty_desktop_action_queue.py) — FIFO for `kind: open_canvas` only (slug + seeds). **Not** full specs or hub patches.

Authoritative canvas edits and merged specs remain **`apply_diagram_spec_mutation`**, hub revision, and **`kitty:live_spec`** (including [`GET /api/kitty/live_context/...`](../kitty/http/handlers.py) on desktop). Conversation photo upload uses [`POST /api/kitty/conversation_image`](../kitty/http/conversation_image_handler.py) (vision classify → hand-drawn rebuild + outline extract, or OCR extract).

**Load balancer:** prefer **sticky sessions** to `/ws/kitty` across workers (latency); refcount remains authoritative for correctness.

## Environment

- `KITTY_CONTROL_SHARED_SECRET` — optional override; when unset, auto-generated in Redis (shared across workers).
- `KITTY_WS_REFCOUNT_TTL_SECONDS` — optional; default min(1h, session TTL).
- `KITTY_REFCOUNT_USE_EVALSHA` — default `1` (cached Lua); set `0` for plain `EVAL` if needed.

## Production checklist

- Redis reachable from every API worker; identical `KITTY_CONTROL_*` and channel across processes.
- Invalid control scopes are rejected before dispatch; prefer sticky LB to `/ws/kitty` for lower churn.
- Watch `ws_kitty_*` metrics and Agent Hub **warning** logs for refcount attach/detach failures (Redis outages).

## Structured logging

Kitty control and hub paths pass ``extra=kitty_extra(...)`` from [`services/kitty/infra/control/kitty_observability.py`](../kitty/infra/control/kitty_observability.py). Ship logs to an engine that indexes **custom fields** (e.g. `kitty_event`, `kitty_scope`, `kitty_user_id`, `kitty_reason`, `kitty_error_type`) for dashboards and traces.

## Metrics and RED-style alerting

Counters live in `services/infrastructure/monitoring/ws_metrics.py` (in-process; optionally mirrored to Redis TimeSeries when enabled). Suggested **rate / errors / drift** signals:

| Counter | Suggested use |
|---------|----------------|
| `ws_kitty_control_received_total` vs `ws_kitty_control_cleanup_applied_total` | **Rate:** large sustained gap under active Kitty traffic → messages ignored, no local scope, or auth rejects. |
| `ws_kitty_control_message_ignored_total` | **Errors / noise:** correlate spikes with `kitty_event=control_auth_rejected` in logs. |
| `ws_kitty_refcount_attach_failed_total` / `ws_kitty_refcount_detach_failed_total` | **Errors:** Redis down, Lua errors, or script policy; alert on increase during otherwise healthy traffic. |
| `ws_kitty_control_cleanup_not_configured_total` | **Errors:** wiring bug (`configure_kitty_scope_cleanup` never called); should stay at zero in production. |
| `ws_kitty_control_voice_cleanup_failed_total` | **Errors:** uncaught failures from voice teardown; investigate stack in `kitty_event=voice_cleanup_failed`. |
| `ws_kitty_control_dispatch_exception_total` | **Errors:** unexpected errors escaping dispatch in the pub/sub listener; should be near zero. |
| `ws_kitty_refcount_meta_drift_total` | **Drift:** sessionmeta vs refcount mismatch in pairing snapshot; tune alerts if noisy. |

**Duration** is not centrally tracked for Kitty today; consider spans around `cleanup_voice_by_diagram_session` if you adopt OpenTelemetry.
