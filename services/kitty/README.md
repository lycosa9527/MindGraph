# Kitty — realtime agent + session infrastructure

One backend package. There is no separate `kitty_voice` module.

## Layout

| Path | Role |
|------|------|
| `services/kitty/ws/` | WebSocket transport (connect, lifecycle, inbound) |
| `services/kitty/omni/` | Qwen Omni realtime loop + tools |
| `services/kitty/session/` | Per-scope session registry, events, cleanup |
| `services/kitty/routing/` | Intent catalog + command router |
| `services/kitty/ack/` | User-facing acknowledgment templates (`text_chunk` + optional Omni) |
| `services/kitty/diagram/` | Diagram mutations via agent hub |
| `services/kitty/context/` | Voice context merge + library refresh |
| `services/kitty/content/` | Paragraph batch apply |
| `services/kitty/http/` | REST handlers + LLMOps manifest |
| `services/kitty/infra/redis/` | Key templates, live_spec, refcount |
| `services/kitty/infra/desktop/` | Mobile/desktop pairing, wake, actions |
| `services/kitty/infra/control/` | Cross-worker pub/sub |
| `services/kitty/infra/scope/` | Scope validation and library access |
| `services/kitty/infra/bootstrap/` | Start-time context hydrate, vocabulary |
| `services/kitty/infra/guards/` | HTTP gates, production checks |
| `routers/features/kitty/` | FastAPI route wiring (`/ws/kitty`, `/api/kitty/*`) |
| `services/agent_hub/` | Authoritative hub mutations (separate on purpose) |

## Acknowledgment templates (`services/kitty/ack/`)

Diagram edits, UI actions, low-confidence clarifications, and **unsupported diagram types**
(e.g. fishbone / 鱼骨图) use a **hybrid** model: templated acks for structured outcomes, Omni LLM for open conversation.

- **`ack_library.py`** — zh/en template keys (`diagram.update_node.success`, `diagram.low_confidence`, `ui.*`, …) and `render_ack()`.
- **`ack_slots.py`** — slot extraction from router commands and diagram_update payloads (implicit confirmation: old/new text, targets).
- **`ack_emit.py`** — `emit_user_ack()` sends `text_chunk` for text clients (一句话 panel) and optional short Omni `create_response` on voice.

The command router calls `emit_user_ack` after successful `execute_diagram_update`; `send_kitty_diagram_update` adds the same text as `user_summary` on the WebSocket payload so canvas and chat stay aligned.

## Session scopes (`diagram_session_id`)

The URL path `/ws/kitty/{diagram_session_id}` defines a **scope**:

| Client | Typical scope | Notes |
|--------|----------------|-------|
| Mobile Kitty (`/m/kitty`) with a library diagram loaded | `activeDiagramId` (UUID) | Same Redis keys as desktop editing that file. |
| Mobile Kitty without a library row | Random client UUID | Desktop `mobile_lane` for a library id stays off until scope matches a saved id + phone sends `start`. |
| Desktop MindGraph canvas | `savedDiagramsStore.activeDiagramId` or ephemeral UUID | Ephemeral when the canvas has no saved diagram yet. |

Validation: `services.kitty.infra.scope.kitty_ws_scope.normalize_kitty_diagram_session_id` — ASCII alphanumeric, `_`, `-`, max 128 chars.

## Product rules

- **Full-diagram context**: Kitty’s agent-facing payload is built from merged client context and, when `diagram_library_id` is set, the authoritative library row (`merge_voice_context_with_library`). Selected nodes stay client-driven; node bodies can be refreshed from the library when the server runs a **library refresh** (see below).
- **Mobile mic = MindGraph voice UI**: The phone microphone drives the same diagram command / event-bus path as the canvas; it is not an isolated chat session.
- **Desktop indicator**: The canvas shows the pairing hint only when `GET /api/kitty/mobile_lane/{library_id}` returns `armed: true`, i.e. Redis `kitty:sessionmeta` exists for that scope and `client_lane` is `mobile` (set when the **phone** sends `client_lane: mobile` in the WebSocket `start` frame). Visiting `/m/kitty` without starting the socket does not arm the indicator.

## `client_lane` and `mobile_lane`

- On **start**, the client may send `client_lane: "mobile"` (only this value is honored for the indicator). Other values are ignored for meta; the field is omitted for legacy/desktop clients.
- **Sessionmeta** (`kitty:sessionmeta:{scope}`) JSON includes `user_id`, `updated_at`, optional `active_diagram_library_id`, and optional `client_lane: "mobile"`.
- **mobile_lane** uses `kitty_mobile_indicator_armed_for_user(scope, user_id)` — meta exists, user matches, and `client_lane == "mobile"`.

## Single active socket per scope

On **start**, the server holds `diagram_session_voice_lock(scope)`, closes any other WebSocket registered for that scope, runs `cleanup_voice_by_diagram_session`, then attaches the new socket. Opening Kitty on **desktop** while **mobile** holds the same library scope **replaces** the mobile connection (intended handoff).

## Redis

Session keys use TTL `KITTY_SESSION_REDIS_TTL_SECONDS` (default 4h). Hash-tag prefix `{scope}` keeps sessionmeta, live_spec, owner, and refcount in one Cluster slot (`services/kitty/infra/redis/kitty_redis_keys.py`).

Written after a successful `start` and on debounced `context_update`. Teardown uses a **global Redis refcount** incremented when the socket finishes `start` and decremented in the WebSocket `finally` path via `MindGraphAgentHub` (`services/agent_hub/`). When the count reaches zero, Lua removes sessionmeta, live_spec, owner, and the refcount key together.

- `{scope}kitty:sessionmeta` — same JSON as legacy `kitty:sessionmeta:{scope}` (legacy keys are not read by new code; they expire by TTL).
- `{scope}kitty:live_spec` — merged voice context.
- `{scope}kitty:scope_owner` — user id that owns the scope row for safe teardown.
- `{scope}kitty:ws_refcount` — number of active Kitty WS connections across workers.

User-scoped keys (no hash tag):

- `kitty:desktop_focus:{user_id}` — last library diagram id open on desktop (mobile pairs via GET).
- `kitty:desktop_actions:{user_id}` — FIFO queue for mobile → desktop navigation (`open_canvas`).
- `kitty:mobile_active:{user_id}` — JSON `{ scopes, primary_scope, updated_at }` for active mobile-lane Kitty sessions (`services/kitty/infra/desktop/kitty_mobile_active.py`).
- `kitty:desktop_wake:{user_id}` — Redis pub/sub channel; publishes `mobile_active` JSON when phone Kitty connects/disconnects (desktop SSE wake).

Refcount Lua defaults to **EVALSHA** (per-worker script cache). Set **`KITTY_REFCOUNT_USE_EVALSHA=0`** to force **EVAL** if server-side scripts are awkward for your Redis topology.

## Load balancing

Use **sticky sessions** (cookie- or IP-based) to `/ws/kitty` so the same client reconnects the same worker during a session. Preempt and refcount still coordinate across workers, but sticky routing reduces redundant churn. For metrics, `ws_kitty_refcount_meta_drift_total` bumps when `build_desktop_pairing_snapshot` sees sessionmeta and refcount disagree (investigate stale clients or partial failures).

## Desktop action poll (mobile gate)

The desktop SPA (`useKittyDesktopActionPoll` in `App.vue`) **does not** consume the action queue unless:

1. `feature_kitty_agent` is enabled (no Kitty REST traffic when the feature is off).
2. The user is authenticated on a **desktop** surface (not `/m/*`).
3. `GET /api/kitty/mobile_active` reports `active: true` (phone Kitty WebSocket started with `client_lane: mobile`).

Both `GET /api/kitty/desktop_pairing` and legacy `GET /api/kitty/desktop_action/pop` gate **long-poll** BLPOP on ``mobile_active`` (live mobile Kitty WS). **Instant** pop (``wait_sec=0``) runs only after mobile REST enqueue sets a one-shot explicit-drain flag (library diagram pick). Stale queue items are discarded on pop.

While mobile Kitty is **off**, desktop opens **SSE** on `GET /api/kitty/desktop_wake/stream` (EventSource + cookie auth) for instant wake when phone Kitty connects. Redis pub/sub on `kitty:desktop_wake:{user_id}` fires on `mark_kitty_mobile_active` / `clear_kitty_mobile_scope`. A **12s fallback** poll on `GET /api/kitty/desktop_pairing?wait_sec=0` runs only when SSE is disconnected. When mobile connects, the leader tab chains long-poll requests to `GET /api/kitty/desktop_pairing?wait_sec=25` (Redis BLPOP on the action queue) until mobile disconnects. Legacy `GET /api/kitty/desktop_action/pop` remains available with optional `wait_sec`.

**Tab leader:** `BroadcastChannel` (`kittyDesktopPollLeader.ts`) elects one desktop tab per browser profile to run the watch/consume loop so multiple open MindGraph tabs do not multiply pairing traffic.

**Mobile `desktop_focus` poll:** `useMobileKittyPairing` polls `GET /api/kitty/desktop_focus` only before the mobile WebSocket connects and only while local scope is still unresolved (no saved diagram id, no bootstrap scope, no bootstrap desktop focus). After connect, polling stops.

Desktop **start** on a scope clears `client_lane: mobile` in sessionmeta (`preserve_mobile_lane=False`) and removes that scope from `kitty:mobile_active:{user_id}` so the pairing indicator does not stay stale after handoff.

## Desktop pairing hint (poll)

Canvas uses the shared **mobile_active** hub (fed by the leader tab's desktop wake SSE). When SSE data is fresh, the canvas **does not** poll REST. Saved and ephemeral scopes both match via ``scopes`` / ``primary_scope`` (``mobile_lane`` polling removed from canvas).

## Desktop focus (`desktop_focus`)

`GET/PUT /api/kitty/desktop_focus` publishes the library id the user last had open on **desktop** MindGraph so mobile Kitty can pair when local Pinia has no `activeDiagramId`. See `services/kitty/infra/desktop/kitty_desktop_focus.py`.

## Context parity (desktop-only edits while mobile Kitty is open)

If the phone does not mirror every canvas edit, **`merge_voice_context_with_library`** can still prefer stale node data from the client. The API therefore runs **`throttled_refresh_voice_context_from_library`** (see `services/kitty/context/library_refresh.py`) with `prefer_server_diagram_nodes=True` on throttled **audio** sends and with **`force=True`** at the start of **text command** handling, so library-backed sessions re-read the saved diagram before routing commands. Omni instructions and the LangGraph agent diagram state are updated after each refresh.

## Multi-worker

Refcount + control-plane pub/sub (`KITTY_CONTROL_CHANNEL`) replace the old “delete Redis when local `active_websockets` is empty” behavior. The control HMAC secret is **auto-generated and stored in Redis** (like `JWT_SECRET_KEY`) with a `data/.kitty_control_secret` backup; optional **`KITTY_CONTROL_SHARED_SECRET`** in `.env` overrides Redis when set explicitly.

Per-process **`diagram_session_voice_lock`** only serializes starts on a single worker; another worker can still be in `start` until a control message arrives—refcount + Redis meta remain the global source of truth.

Control pub/sub is **at-most-once**; a restarting worker can miss a single “kick” message (usually acceptable).

## Production checklist

- **Auth:** all Kitty REST routes use `get_current_user`; SSE wake requires `kitty_http_allowed`.
- **User scoping:** Redis keys/channels are always `:{user_id}` from the authenticated session.
- **Atomic mobile_active:** mark/clear use Redis `WATCH`/`MULTI` (see `kitty_mobile_active.py`).
- **Leader tab:** one `BroadcastChannel` leader per browser profile; resign on tab close for fast failover.
- **SSE cap:** 2 concurrent wake streams per user **per worker** (`kitty_desktop_wake_stream.py`).
- **Stale gate:** SSE heartbeats re-read `mobile_active`; canvas hub fallback polls only when hub is stale (>35s).
- **Metrics:** watch `ws_kitty_refcount_meta_drift_total` if pairing state looks stuck after disconnect.

## REST cleanup

`POST /api/kitty/cleanup/{scope}` — publishes a cross-worker close, runs local `cleanup_voice_by_diagram_session` under `diagram_session_voice_lock`, and may call `kitty_scope_force_teardown_redis` only when this process had no local sockets/sessions **and** the global refcount is absent or zero (avoids tearing down another worker’s live connection).

## Trust model

`client_lane` is asserted by the client — sufficient for a **UI indicator**. Stronger binding (e.g. attestation or server-issued tokens) is out of scope unless product requires it.
