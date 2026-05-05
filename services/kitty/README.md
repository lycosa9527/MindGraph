# Kitty voice / Redis session module

## Session scopes (`diagram_session_id`)

The URL path `/ws/kitty/{diagram_session_id}` defines a **scope**:

| Client | Typical scope | Notes |
|--------|----------------|-------|
| Mobile Kitty (`/m/kitty`) with a library diagram loaded | `activeDiagramId` (UUID) | Same Redis keys as desktop editing that file. |
| Mobile Kitty without a library row | Random client UUID | Desktop `mobile_lane` for a library id stays off until scope matches a saved id + phone sends `start`. |
| Desktop MindGraph canvas | `savedDiagramsStore.activeDiagramId` or ephemeral UUID | Ephemeral when the canvas has no saved diagram yet. |

Validation: `services/kitty/kitty_ws_scope.normalize_kitty_diagram_session_id` — ASCII alphanumeric, `_`, `-`, max 128 chars.

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

Session keys use TTL `KITTY_SESSION_REDIS_TTL_SECONDS` (default 4h). Hash-tag prefix `{scope}` keeps sessionmeta, live_spec, owner, and refcount in one Cluster slot (`services/kitty/kitty_redis_keys.py`).

Written after a successful `start` and on debounced `context_update`. Teardown uses a **global Redis refcount** incremented when the socket finishes `start` and decremented in the WebSocket `finally` path via `MindGraphAgentHub` (`services/agent_hub/`). When the count reaches zero, Lua removes sessionmeta, live_spec, owner, and the refcount key together.

- `{scope}kitty:sessionmeta` — same JSON as legacy `kitty:sessionmeta:{scope}` (legacy keys are not read by new code; they expire by TTL).
- `{scope}kitty:live_spec` — merged voice context.
- `{scope}kitty:scope_owner` — user id that owns the scope row for safe teardown.
- `{scope}kitty:ws_refcount` — number of active Kitty WS connections across workers.

Refcount Lua defaults to **EVALSHA** (per-worker script cache). Set **`KITTY_REFCOUNT_USE_EVALSHA=0`** to force **EVAL** if server-side scripts are awkward for your Redis topology.

## Load balancing

Use **sticky sessions** (cookie- or IP-based) to `/ws/kitty` so the same client reconnects the same worker during a session. Preempt and refcount still coordinate across workers, but sticky routing reduces redundant churn. For metrics, `ws_kitty_refcount_meta_drift_total` bumps when `build_desktop_pairing_snapshot` sees sessionmeta and refcount disagree (investigate stale clients or partial failures).

## Desktop pairing hint (poll)

Canvas polls `GET /api/kitty/mobile_lane/{library_diagram_id}` when a **saved** diagram is open. If `armed: true`, `KittyCanvasAnchor` shows the non-interactive indicator. Leaving canvas with an active **library** scope does **not** POST cleanup (mobile may still be live).

## Desktop focus (`desktop_focus`)

`GET/PUT /api/kitty/desktop_focus` publishes the library id the user last had open on **desktop** MindGraph so mobile Kitty can pair when local Pinia has no `activeDiagramId`. See `services/kitty/kitty_desktop_focus.py`.

## Context parity (desktop-only edits while mobile Kitty is open)

If the phone does not mirror every canvas edit, **`merge_voice_context_with_library`** can still prefer stale node data from the client. The API therefore runs **`throttled_refresh_voice_context_from_library`** (see `routers/features/voice/kitty_library_context_refresh.py`) with `prefer_server_diagram_nodes=True` on throttled **audio** sends and with **`force=True`** at the start of **text command** handling, so library-backed sessions re-read the saved diagram before routing commands. Omni instructions and the LangGraph agent diagram state are updated after each refresh.

## Multi-worker

Refcount + control-plane pub/sub (`KITTY_CONTROL_CHANNEL`) replace the old “delete Redis when local `active_websockets` is empty” behavior. Set **`KITTY_CONTROL_SHARED_SECRET`** in production: when `DEBUG=False`, publishers skip sends and subscribers reject envelopes if the secret is missing, so cross-worker kick/cleanup does not half-work.

Per-process **`diagram_session_voice_lock`** only serializes starts on a single worker; another worker can still be in `start` until a control message arrives—refcount + Redis meta remain the global source of truth.

Control pub/sub is **at-most-once**; a restarting worker can miss a single “kick” message (usually acceptable).

## REST cleanup

`POST /api/kitty/cleanup/{scope}` — publishes a cross-worker close, runs local `cleanup_voice_by_diagram_session` under `diagram_session_voice_lock`, and may call `kitty_scope_force_teardown_redis` only when this process had no local sockets/sessions **and** the global refcount is absent or zero (avoids tearing down another worker’s live connection).

## Trust model

`client_lane` is asserted by the client — sufficient for a **UI indicator**. Stronger binding (e.g. attestation or server-issued tokens) is out of scope unless product requires it.
