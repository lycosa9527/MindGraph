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

## Availability

MindMate seminar and MindGraph online collaboration are regular services. They are not behind `FEATURE_*` switches or a school-tier feature. School versions still differ by member seats and diagram storage.

## Visibility (mirrors canvas collab)

| Mode | Discover | Join |
|------|----------|------|
| `organization` | Same-org browse via `GET /organization/sessions`. A closed room is listed only for the host and accepted invitees | Same org, or expert/superadmin/school_admin cross-org, while the room is open. After the host names members, only those teachers. `POST /join` with the live code enrolls a new accepted seat; joining from the school list does not |
| `network` | Not listed | Phone/org multi-select invites need the peer to agree. `POST /join` with the live code enrolls a new accepted seat. Pending phone/org invites still require consent. Status, history, and the socket do not add a seat |

## Session lifecycle

Redis keys under `mindmate_seminar:*`; fan-out room prefix `mms:{CODE}`.

- **Host rooms:** Starting another seminar does not stop rooms this host already left open. Reopening a saved seminar stops that host's other live rooms. A school can keep 10 live seminars.
- **Idle monitor:** [`idle_monitor.py`](../../services/features/mindmate_seminar/idle_monitor.py) drops orphan Redis scores. Silence, an empty roster, room age, and the 1h/10h preset do not end the room. The leader ends it. Lifespan cancels the monitor task on shutdown.
- **Owner stop:** `POST /stop` → **4011**.
- **Messages:** `POST /{session_id}/messages` saves a line. `GET /{session_id}/messages` reads pages. The socket pushes the saved row, AI tokens, and who is online.
- **Resume tokens:** `{u,c,s}` in `joined` frame; subprotocol `mg-resume.{token}`.
- **Dify stream lock:** one AI response per room; a second MindMate line returns `mindmate_responding` on the POST.
- **Dify abort signal:** cooperative cross-worker abort via Redis `dify_abort:{CODE}`; checked each stream chunk; lock released only in stream `finally`.
- **Message retention:** ended sessions and messages are kept indefinitely (history API gated; live rooms only while `ended_at IS NULL`).
- **Seminar history:** ending a room stamps `library_saved_at` in the same write as `ended_at` (host stop, or replacement when the host reopens another saved seminar). Everyone who joined (a `mindmate_seminar_members` row, written when the socket connects and when the host starts the room) sees that seminar in the sidebar. Pin, rename, and delete stay with the host. The owner can continue the same room (`POST /reopen`): `ended_at` clears, the invite code and transcript stay, and Redis is published again. Joiners keep the read-only transcript until that room is live. A live room leaves the saved list until it ends again. The sidebar reloads on that event, on room removal, and when the tab becomes visible.
- **Redis restart and deploy:** the live row, roster, transcript, and Dify conversation id stay in Postgres. Durable changes commit there first, then copy onto the existing Redis hash (title, Dify conversation id, latest message id). A missing hash is not created by that copy; the next socket connect republishes the full row. Open sockets and an in-flight reply drop with the process. Presence and resume tokens drop with Redis.
- **Files and COS:** shared files, chat chips, and artifacts are Postgres rows plus COS bytes (`COS_SEMINAR_PREFIX`). A new upload writes COS before the row is saved. A hourly pass, and the republish after a Redis wipe, upload any copy that is still only on disk, including ended rooms. Office previews stay in COS beside that key. Canvas preview PNGs use the long-lived temp-image URL and are not deleted locally until COS holds them.
- **Redis teardown:** `touch_activity` does not recreate a purged room hash. The idle monitor drops scores whose session hash is already gone. Connect and send republish a live row.

Operational parity with canvas collab: see [`docs/operations/online-collab-runbook.md`](../operations/online-collab-runbook.md) for Redis/registry/idle patterns (MindMate uses separate key prefix and omits diagram live-spec merge).

## Security and identifiers

| Identifier | Scope | Client-visible? | Notes |
|------------|-------|-----------------|-------|
| `session_id` (UUID) | One collab room | Yes — join/browse/history | Unguessable; route-level visibility checks before access |
| `code` (XXX-XXX) | One live room | Yes — invite link, WS path | Addresses one live room. `POST /join` enrolls a code holder who is not already pending; pending phone/org invites still require accept |
| `dify_conversation_id` | One shared AI thread per room | **No** — server-internal only | Stored as `s{server}:{difyId}` so 主服务器 and 备用服务器 stay distinct. Dify user: `{MINDMATE_DIFY_USER_PREFIX}_mindmate_seminar_{orgId}_{sessionId}` |
| `resume_token` | One reconnect | Yes — `joined` frame | Bound to `{user, code, session}`; one-time Redis consume |

**Org join parity (canvas collab):** when the host has no `organization_id`, any authenticated org member may join an `organization`-visible room ([`online_collab_visibility_helpers.py`](../../services/online_collab/lifecycle/online_collab_visibility_helpers.py)).

**Network rooms:** invite-only. Hosts add people by school roster (platform-tier roles may filter other orgs) or by sharing the invite code/link. Org picks stay pending until the peer agrees. `POST /join` with the live code enrolls a new accepted seat. Pending invites still require consent. Reading status or opening the socket does not enroll.

**Cross-org picker:** `GET /api/mindmate/invite-organizations` and `org_id` on `/api/mindmate/org-members` are for superadmin / platform_bd / expert.

**Access layers:** visibility rules → per-route authorization → PostgreSQL RLS on user-scoped reads.


## WebSocket frames

Join is **implicit** on WebSocket connect (after auth and visibility checks). There is no server handler for a client `join` frame.

Client → server: `ping`, `socket_ping`, `read`. A chat line is `POST /api/mindmate/seminar/{session_id}/messages`, not a socket frame.

Server → client: `joined`, `snapshot`, `user_message`, `ai_message_chunk`, `ai_message_end`, `seminar_minutes`, `session_closing`, presence/error frames.

**Shutdown delivery:** the server sends `session_closing` as JSON, then force-closes all sockets with **4011** when the leader stops the room. **4010** is the close code for a system stop (`reason` other than `owner` or `single_host`). The idle monitor does not emit it. The `room_idle_shutdown` / `session_ended_shutdown` frame types are internal fan-out signals and are not delivered as JSON to clients.

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
