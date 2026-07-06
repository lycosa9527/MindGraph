# MindMate Online Collab

Shared MindMate AI chatroom for teachers: one room, one Dify conversation, all participants see the same user messages and streaming assistant replies.

## Overview

| Layer | Location |
|-------|----------|
| REST | `/api/mindmate/collab/*` — [`routers/api/mindmate_collab_routes.py`](../../routers/api/mindmate_collab_routes.py) |
| WebSocket | `/api/ws/mindmate-collab/{code}` — [`routers/api/mindmate_collab_ws.py`](../../routers/api/mindmate_collab_ws.py) |
| Service | [`services/features/mindmate_collab/`](../../services/features/mindmate_collab/) |
| DB | `mindmate_collab_sessions`, `mindmate_collab_messages` (Alembic `rev_0076`) |
| Frontend room | `/mindmate/collab?code=` — `MindmateCollabPage.vue`, `useMindmateCollab.ts` |
| Entry UI | `MindmateCollabPanel.vue` on `/mindmate` toolbar |
| Sidebar | `MindmateCollabHistory.vue` above personal chat history |

## Feature flag

Set `FEATURE_MINDMATE_COLLAB=True` in `.env` (default **off**). When disabled, REST/WS routes are not registered at startup, runtime requests to `/api/mindmate/collab/*` return 404 via the feature gate, and the MindMate toolbar pill / sidebar history are hidden. Admins can toggle via **Admin → Features** (writes `.env` + hot reload). A full process restart is required if the module was never loaded at boot.

Tier gate (when the flag is on): `TIER_FEATURE_ONLINE_COLLAB` (same as diagram collab).

## Visibility (mirrors canvas collab)

| Mode | Discover | Join |
|------|----------|------|
| `organization` | Same-org browse via `GET /organization/sessions` | Same org, or expert/superadmin/school_admin cross-org |
| `network` | Not listed | Valid 6-char code + `online_collab` tier |

## Session lifecycle

Redis keys under `mindmate_collab:*`; fan-out room prefix `mmc:{CODE}`.

- **Single host:** starting a new room stops prior hosted sessions for that user.
- **Idle monitor:** [`idle_monitor.py`](../../services/features/mindmate_collab/idle_monitor.py) — warning then teardown (WS close **4010**).
- **Owner stop:** `POST /stop` → **4011**.
- **Resume tokens:** `{u,c,s}` in `joined` frame; subprotocol `mg-resume.{token}`.
- **Dify stream lock:** one AI response per room; concurrent `chat` → `mindmate_responding` error.
- **Dify abort signal:** cooperative cross-worker abort via Redis `dify_abort:{CODE}`; checked each stream chunk; lock released only in stream `finally`.
- **Message retention:** ended sessions and messages are kept indefinitely (history API gated; live rooms only while `ended_at IS NULL`).

Operational parity with canvas collab: see [`docs/operations/online-collab-runbook.md`](../operations/online-collab-runbook.md) for Redis/registry/idle patterns (MindMate uses separate key prefix and omits diagram live-spec merge).

## Security and identifiers

| Identifier | Scope | Client-visible? | Notes |
|------------|-------|-----------------|-------|
| `session_id` (UUID) | One collab room | Yes — join/browse/history | Unguessable; route-level visibility checks before access |
| `code` (XXX-XXX) | One live room | Yes — invite link, WS path | Network rooms: code-as-secret (~32^6 combinations) + rate limits |
| `dify_conversation_id` | One shared AI thread per room | **No** — server-internal only | Stable Dify user: `mindmate_collab_{orgId}_{sessionId}` |
| `resume_token` | One reconnect | Yes — `joined` frame | Bound to `{user, code, session}`; one-time Redis consume |

**Org join parity (canvas collab):** when the host has no `organization_id`, any authenticated org member may join an `organization`-visible room ([`online_collab_visibility_helpers.py`](../../services/online_collab/lifecycle/online_collab_visibility_helpers.py)).

**Network rooms:** anyone with `TIER_FEATURE_ONLINE_COLLAB` and a valid code may join and see room history — intentional secret-link model.

**Access layers:** feature flag → school tier → visibility rules → per-route authorization → PostgreSQL RLS on user-scoped reads.


## WebSocket frames

Join is **implicit** on WebSocket connect (after auth, tier, and visibility checks). There is no server handler for a client `join` frame.

Client → server: `chat`, `ping`.

Server → client: `joined`, `snapshot`, `user_message`, `ai_message_chunk`, `ai_message_end`, `room_idle_warning`, `session_closing`, presence/error frames.

**Shutdown delivery:** the server sends `session_closing` as JSON, then force-closes all sockets with **4010** (idle) or **4011** (host stop). The `room_idle_shutdown` / `session_ended_shutdown` frame types are internal fan-out signals and are not delivered as JSON to clients.

**Participant registration:** REST `POST /join` validates permissions only; Redis participant counts increment when the WebSocket connects (`add_participant` inside `ws_managed_session`).

**Duplicate tab:** a second connection for the same user closes the prior socket with **4003**; superseded disconnect cleanup skips participant removal when a newer handle is active ([`ws_disconnect_cleanup.py`](../../services/features/mindmate_collab/ws_disconnect_cleanup.py)).

## Social layer in collab room

- **Org contacts:** shared `frontend/src/composables/social/` module — `OrgContactsPanel` with `source="mindmate-collab"` (collab API + notify WS presence; no `FEATURE_WORKSHOP_CHAT` required for roster).
- **Workshop parity:** same panel/composables with `source="workshop"` (workshop store + chat WS presence).
- **Future IM widget:** mount `OrgContactsPanel` or call `useOrgRosterPanel()` from any page.
- **DMs:** `MindmateDmDrawer` via `/api/chat/dm/*` (requires `FEATURE_WORKSHOP_CHAT`); org isolation enforced by `access_dm_partner`.

## Deep links

`/mindmate?join_mindmate_collab=ABC-DEF` → strips query, opens collab panel, auto-joins by code.

## Tests

- Backend: `tests/test_mindmate_collab_*.py`
- Frontend: `frontend/tests/useMindmateCollab.spec.ts`, `mindmateCollabReconnect.spec.ts`, `MindmateCollabPanel.spec.ts`, `MindmateCollabHistory.spec.ts`
