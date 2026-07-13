# Kitty — realtime agent + session infrastructure

One backend package. There is no separate `kitty_voice` module.

## Layout

| Path | Role |
|------|------|
| `services/kitty/ws/` | WebSocket transport (connect, lifecycle, inbound) |
| `services/kitty/omni/` | Qwen Omni realtime loop + tools |
| `services/kitty/session/` | Per-scope session registry, events, cleanup |
| `services/kitty/session/manager/` | **Session Manager** — alignment snapshot, WS pairing leases, action journal, verified-edit gate |
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

## Session Manager (`services/kitty/session/manager/`)

Central control plane for cross-device Kitty identity and pairing (not AgentHub diagram mutations).

| API | Role |
|-----|------|
| `build_kitty_session_snapshot` / `GET /api/kitty/session/{scope}` | Alignment + `ingress_owner` + focus/mobile/owner presence |
| `require_aligned_for_verified_edit` | Gate in `messaging.py` before verified apply / SSE |
| `begin_ingress` / `link_mutation` | Journal ASR/typed `request_id` then correlate `mutation_id` (out + ack) |
| `require_desktop_ingress_allowed` | S14: reject desktop WS `text` when mobile owns same-scope ingress |
| `set_desktop_focus` / `get_desktop_focus` | SoT wrappers for Redis `desktop_focus` (REST PUT/GET) |
| `journal_promote` / REST `…/promote` | Ephemeral → library promote journal (S3) |
| REST `POST …/ingress` | FE-reported `ui_create` / `ingress_rejected` (create-phase) |
| `attach` / `detach` | WS start/end → Redis `mobile_active` / `canvas_owner_presence` + journal |
| Action journal | Hot Redis list `kitty:session_journal:{user}:{scope}` (ingress, mutation_out/ack, align, attach, …) |

**Scenarios (summary):** S1–S12 create/edit/promote; **S13** mobile library A vs desktop B → `scope_divergence` (mobile banner + desktop hint; poll snapshot); **S14** same scope + mobile active → desktop one-sentence edit input locked (`ingress_owner=mobile`; BE rejects desktop WS text).

**Ingress correlation:** WS `text` (typed or ASR-committed) calls `begin_ingress`; verified `diagram_update` journals `mutation_out` with the same `request_id` and stamps it on mobile chat-only replies; `diagram_mutation_ack` journals `mutation_ack`. Non-WS create uses `POST /api/kitty/session/{scope}/ingress` (`ui_create`).

FE facade: `frontend/src/composables/kitty/useKittySessionManager.ts` (`beginKittySessionIngress` → WS; `reportKittySessionIngress` / `reportKittySessionPromote`; desktop + mobile poll snapshot).

## Session scopes (`diagram_session_id`)

The URL path `/ws/kitty/{diagram_session_id}` defines a **scope**:

| Client | Typical scope | Notes |
|--------|----------------|-------|
| Mobile Kitty (`/m/kitty`) with a library diagram loaded | `activeDiagramId` (UUID) | Same Redis keys as desktop editing that file. |
| Mobile Kitty without a library row | Random client UUID | Cold open / focus-cleared only; **create-new** allocates a library draft first. |
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
- `kitty:desktop_actions:{user_id}` — FIFO queue for mobile → desktop navigation (`open_library_diagram` for pick/create; residual `open_canvas` for blank type switch).
- `kitty:canvas_owner_presence:{user_id}:{scope}` — desktop canvas-owner WS lease; verified edits fail closed with `no_owner` when missing (avoids `ack_timeout`).
- `kitty:mobile_active:{user_id}` — JSON `{ scopes, primary_scope, updated_at }` for active mobile-lane Kitty sessions (`services/kitty/infra/desktop/kitty_mobile_active.py`).
- `kitty:desktop_wake:{user_id}` — Redis pub/sub channel; publishes `mobile_active` JSON when phone Kitty connects/disconnects (desktop SSE wake).

Refcount Lua defaults to **EVALSHA** (per-worker script cache). Set **`KITTY_REFCOUNT_USE_EVALSHA=0`** to force **EVAL** if server-side scripts are awkward for your Redis topology.

## Load balancing

Use **sticky sessions** (cookie- or IP-based) to `/ws/kitty` so the same client reconnects the same worker during a session. Preempt and refcount still coordinate across workers, but sticky routing reduces redundant churn. Cross-device **apply** does not depend on sticky WS affinity: Redis ``kitty:desktop_wake:{user_id}`` already reaches the desktop browser SSE. Verified edits and canvas actions fan out on that channel; only the pending mutation **ack** future needs a small Redis control relay when the desktop Kitty WS and mobile ingress sit on different workers. For metrics, `ws_kitty_refcount_meta_drift_total` bumps when `build_desktop_pairing_snapshot` sees sessionmeta and refcount disagree (investigate stale clients or partial failures).

## Cross-device sync contract (mobile ↔ desktop)

Treat Mobile Kitty, desktop canvas, and the one-sentence panel as **one session** when linked on the same library diagram scope.

| Domain | Direction | Channel | Notes |
|--------|-----------|---------|-------|
| Scope / pairing | Desktop → Mobile | Redis ``desktop_focus`` + WS ``desktop_focus_update`` (+ slow REST recovery) | Stale focus ignored (≤180s); empty → ephemeral |
| Open diagram | Mobile → Desktop | Redis action queue + SSE ``desktop_action_pending`` → instant LPOP | Library pick / durable create-new → ``open_library_diagram`` |
| Diagram mutations (voice/Kitty) | Mobile → Desktop | Redis ``desktop_wake`` SSE ``diagram_update`` (+ local owner WS when same worker) | Verified ``mutation_id`` applied by canvas owner tab; observers skip |
| Canvas actions (auto_complete…) | Mobile → Desktop | Redis ``desktop_wake`` SSE ``canvas_action`` (+ local owner WS when same worker) | Browser executes; no cross-worker WS lookup required |
| Verified mutation ack | Desktop → Mobile worker | Kitty WS ack + Redis ``mutation_ack`` control relay | Completes pending future when WS landed on another worker |
| Manual desktop canvas edits | Desktop → Mobile | Hub/`live_spec` + mobile `live_context` poll | Phone chips stay honest after desktop edits |
| Selection | **Bidirectional** | Mobile `context_update` → SSE; desktop `PUT /api/kitty/selection/{scope}` → mobile WS | Chips ↔ canvas highlight |
| LLM model | **Bidirectional** | `PUT /api/kitty/llm_model/{scope}` + WS/SSE | Both sides update pills |
| Voice phase FAB | Mobile → Desktop | SSE `voice_phase_update` | Listening / speaking glow |
| Mobile active indicator | Mobile → Desktop | SSE `mobile_active` | Canvas FAB / lock one-sentence |
| Chat turns | Shared store | REST `one_sentence/turns` | Hydrate on scope change / reopen (not live stream) |

**Not bidirectional (by design):** desktop mic voice phase → mobile; collab blocks remote Kitty apply; ephemeral mobile has no canvas chrome (no chips / LLM).

**Create-new SoT (durable library draft):** Mobile dropdown create and voice ``open_desktop_canvas`` both **POST a library draft first**, bind that UUID as Kitty scope, journal ``ui_create``, then enqueue ``open_library_diagram``. Desktop opens the same id; verified edits use the library path (canvas-owner present after load). There is **no** ephemeral UUID + ``journal_promote`` on this path.

**Unlinked residual ephemeral** (cold open / ``desktop_focus`` cleared): mobile is chat + large mascot only. If desktop later auto-saves an old ephemeral canvas, mobile may still **promote** via fresh ``desktop_focus`` (library id, hydrate, dropdown refresh, scope reconnect) — that path is legacy recovery, not create-new.

## Desktop action poll (mobile gate)

The desktop SPA (`useKittyDesktopActionPoll` in `App.vue`) **does not** consume the action queue unless:

1. `feature_kitty_agent` is enabled (no Kitty REST traffic when the feature is off).
2. The user is authenticated on a **desktop** surface (not `/m/*`).
3. `GET /api/kitty/mobile_active` reports `active: true` (phone Kitty WebSocket started with `client_lane: mobile`).

Both `GET /api/kitty/desktop_pairing` and legacy `GET /api/kitty/desktop_action/pop` gate **long-poll** BLPOP on ``mobile_active`` (live mobile Kitty WS) for API compatibility. The **desktop SPA** no longer chains ``wait_sec=25``: Redis queue stays shared across workers; enqueue publishes SSE ``desktop_action_pending`` on ``kitty:desktop_wake:{user_id}``, and the leader tab drains with instant ``desktop_pairing?wait_sec=0`` (LPOP). Stale queue items are discarded on pop. Instant pop while mobile is inactive still requires the one-shot explicit-drain flag (library diagram pick).

While mobile Kitty is **off**, desktop opens **SSE** on `GET /api/kitty/desktop_wake/stream` (EventSource + cookie auth) for instant wake when phone Kitty connects. Redis pub/sub on `kitty:desktop_wake:{user_id}` fires on `mark_kitty_mobile_active` / `clear_kitty_mobile_scope`. A **12s fallback** poll on `GET /api/kitty/desktop_pairing?wait_sec=0` runs only when SSE is disconnected. On SSE reconnect the leader also drains any queued actions.

**Tab leader:** `BroadcastChannel` (`kittyDesktopPollLeader.ts`) elects one desktop tab per browser profile to run the watch/SSE loop so multiple open MindGraph tabs do not multiply pairing traffic.

**Mobile `desktop_focus`:** Desktop `PUT /api/kitty/desktop_focus` writes Redis and pushes ``desktop_focus_update`` to mobile Kitty WS on this worker, plus Redis control ``desktop_focus`` so other workers can push to their local mobile sockets. Mobile keeps a slow REST recovery poll while WS is connected (fast poll only pre-WS). Focus is trusted only when recently refreshed (desktop canvas heartbeat). After focus clear, mobile resets to an ephemeral session.

Desktop **start** on a scope clears `client_lane: mobile` in sessionmeta (`preserve_mobile_lane=False`) and removes that scope from `kitty:mobile_active:{user_id}` so the pairing indicator does not stay stale after handoff.

## Desktop pairing hint (poll)

Canvas uses the shared **mobile_active** hub (fed by the leader tab's desktop wake SSE). When SSE data is fresh, the canvas **does not** poll REST. Saved and ephemeral scopes both match via ``scopes`` / ``primary_scope`` (``mobile_lane`` polling removed from canvas).

## Desktop focus (`desktop_focus`)

`GET/PUT /api/kitty/desktop_focus` publishes the library id the user last had open on **desktop** MindGraph. PUT also notifies mobile Kitty via WS + cross-worker Redis control (see `kitty_desktop_focus_push.py`). Mobile may still GET for recovery / pre-WS pairing.

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
