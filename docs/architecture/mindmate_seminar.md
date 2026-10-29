# MindMate seminar

Shared MindMate AI chatroom for teachers: one room, one Dify conversation, all participants see the same user messages and streaming assistant replies.

## Overview

| Layer | Location |
|-------|----------|
| REST | `/api/mindmate/seminar/*` — [`routers/api/mindmate_seminar_routes.py`](../../routers/api/mindmate_seminar_routes.py) |
| WebSocket | `/api/ws/mindmate-seminar/{code}` — [`routers/api/mindmate_seminar_ws.py`](../../routers/api/mindmate_seminar_ws.py) |
| Service | [`services/features/mindmate_seminar/`](../../services/features/mindmate_seminar/) |
| DB | `mindmate_seminar_sessions`, `mindmate_seminar_messages` (Alembic `rev_0076`), `mindmate_seminar_members` (`rev_0146`) |
| Frontend room | `/mindmate/seminar?code=` — `MindmateSeminarPage.vue`, `useMindmateSeminar.ts` |
| Entry UI | `MindmateSeminarPanel.vue` on `/mindmate` toolbar |
| Sidebar | `MindmateSeminarHistory.vue` above personal chat history |

## Feature flag

Set `FEATURE_MINDMATE_SEMINAR=True` in `.env` (default **off**). When disabled, REST/WS routes are not registered at startup, runtime requests to `/api/mindmate/seminar/*` return 404 via the feature gate, and the MindMate toolbar pill / sidebar history are hidden. Admins can toggle via **Admin → Features** (writes `.env` + hot reload). A full process restart is required if the module was never loaded at boot.

Tier gate (when the flag is on): `TIER_FEATURE_ONLINE_COLLAB` (same as diagram collab).

## Visibility (mirrors canvas collab)

| Mode | Discover | Join |
|------|----------|------|
| `organization` | Same-org browse via `GET /organization/sessions`. A closed room is listed only for the host and accepted invitees | Same org, or expert/superadmin/school_admin cross-org, while the room is open. After the host names members, only those teachers |
| `network` | Not listed | Valid 6-char code is not enough. Only invited teachers, after a cross-school teacher agrees |

## Session lifecycle

Redis keys under `mindmate_seminar:*`; fan-out room prefix `mms:{CODE}`.

- **Host rooms:** Starting another seminar does not stop rooms this host already left open. Reopening a saved seminar stops that host's other live rooms. A school can keep 10 live seminars.
- **Idle monitor:** [`idle_monitor.py`](../../services/features/mindmate_seminar/idle_monitor.py) drops orphan Redis scores. A live row older than 30 days is closed (WS close **4010**). Silence and the 1h/10h duration preset do not end the room.
- **Owner stop:** `POST /stop` → **4011**.
- **Messages:** `POST /{session_id}/messages` saves a line. `GET /{session_id}/messages` reads pages. The socket pushes the saved row, AI tokens, and who is online.
- **Resume tokens:** `{u,c,s}` in `joined` frame; subprotocol `mg-resume.{token}`.
- **Dify stream lock:** one AI response per room; a second MindMate line returns `mindmate_responding` on the POST.
- **Dify abort signal:** cooperative cross-worker abort via Redis `dify_abort:{CODE}`; checked each stream chunk; lock released only in stream `finally`.
- **Message retention:** ended sessions and messages are kept indefinitely (history API gated; live rooms only while `ended_at IS NULL`).
- **Seminar history:** ending a room stamps `library_saved_at` in the same write as `ended_at` (host stop, replacement when starting another room, or the 30-day expiry). Everyone who joined (a `mindmate_seminar_members` row, written when the socket connects and when the host starts the room) sees that seminar in the sidebar. Pin, rename, and delete stay with the host. The owner can continue the same room (`POST /reopen`): `ended_at` clears, the invite code and transcript stay, and Redis is published again. Joiners keep the read-only transcript until that room is live. A live room leaves the saved list until it ends again. The sidebar reloads on that event, on room removal, and when the tab becomes visible.
- **Redis teardown:** `touch_activity` does not recreate a purged room hash. The idle monitor drops scores whose session hash is already gone.

Operational parity with canvas collab: see [`docs/operations/online-collab-runbook.md`](../operations/online-collab-runbook.md) for Redis/registry/idle patterns (MindMate uses separate key prefix and omits diagram live-spec merge).

## Security and identifiers

| Identifier | Scope | Client-visible? | Notes |
|------------|-------|-----------------|-------|
| `session_id` (UUID) | One collab room | Yes — join/browse/history | Unguessable; route-level visibility checks before access |
| `code` (XXX-XXX) | One live room | Yes — invite link, WS path | Network rooms: code-as-secret (~32^6 combinations) + rate limits |
| `dify_conversation_id` | One shared AI thread per room | **No** — server-internal only | Stored as `s{server}:{difyId}` so 主服务器 and 备用服务器 stay distinct. Dify user: `{MINDMATE_DIFY_USER_PREFIX}_mindmate_seminar_{orgId}_{sessionId}` |
| `resume_token` | One reconnect | Yes — `joined` frame | Bound to `{user, code, session}`; one-time Redis consume |

**Org join parity (canvas collab):** when the host has no `organization_id`, any authenticated org member may join an `organization`-visible room ([`online_collab_visibility_helpers.py`](../../services/online_collab/lifecycle/online_collab_visibility_helpers.py)).

**Network rooms:** anyone with `TIER_FEATURE_ONLINE_COLLAB` and a valid code may join and see room history — intentional secret-link model.

**Access layers:** feature flag → school tier → visibility rules → per-route authorization → PostgreSQL RLS on user-scoped reads.


## WebSocket frames

Join is **implicit** on WebSocket connect (after auth, tier, and visibility checks). There is no server handler for a client `join` frame.

Client → server: `ping`, `socket_ping`, `read`. A chat line is `POST /api/mindmate/seminar/{session_id}/messages`, not a socket frame.

Server → client: `joined`, `snapshot`, `user_message`, `ai_message_chunk`, `ai_message_end`, `seminar_minutes`, `session_closing`, presence/error frames.

**Shutdown delivery:** the server sends `session_closing` as JSON, then force-closes all sockets with **4010** (30-day expiry) or **4011** (host stop). The `room_idle_shutdown` / `session_ended_shutdown` frame types are internal fan-out signals and are not delivered as JSON to clients.

**Participant registration:** REST `POST /join` validates permissions only; Redis participant counts increment when the WebSocket connects (`add_participant` inside `ws_managed_session`).

**Duplicate tab:** a second connection for the same user closes the prior socket with **4003**; superseded disconnect cleanup skips participant removal when a newer handle is active ([`ws_disconnect_cleanup.py`](../../services/features/mindmate_seminar/ws_disconnect_cleanup.py)).

## Social layer in collab room

- **Org contacts:** shared `frontend/src/composables/social/` module — `OrgContactsPanel` with `source="mindmate-seminar"` (collab API + notify WS presence; no `FEATURE_WORKSHOP_CHAT` required for roster). Online and offline use the same Redis `po` fan-out as workshop chat, delivered to `/api/ws/mindmate-notify`.
- **Workshop parity:** same panel/composables with `source="workshop"` (workshop store + chat WS presence).
- **Future IM widget:** mount `OrgContactsPanel` or call `useOrgRosterPanel()` from any page.
- **DMs:** `MindmateDmDrawer` via `/api/chat/dm/*` (requires `FEATURE_WORKSHOP_CHAT`); org isolation enforced by `access_dm_partner`.

## Deep links

`/mindmate?join_mindmate_seminar=ABC-DEF` → strips query, opens collab panel, auto-joins by code.

## Tests

- Backend: `tests/test_mindmate_seminar_*.py`
- Frontend: `frontend/tests/useMindmateSeminar.spec.ts`, `mindmateSeminarReconnect.spec.ts`, `MindmateSeminarPanel.spec.ts`, `MindmateSeminarHistory.spec.ts`
