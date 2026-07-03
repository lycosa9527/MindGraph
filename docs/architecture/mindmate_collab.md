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

Operational parity with canvas collab: see [`docs/operations/online-collab-runbook.md`](../operations/online-collab-runbook.md) for Redis/registry/idle patterns (MindMate uses separate key prefix and omits diagram live-spec merge).

## WebSocket frames

Client → server: `join`, `chat`, `ping`.

Server → client: `joined`, `snapshot`, `user_message`, `ai_message_chunk`, `ai_message_end`, `room_idle_warning`, `room_idle_shutdown`, `session_closing`, `session_ended_shutdown`, presence/error frames.

## Social layer in collab room

- **Org contacts:** `OrgContactsPanel` + `useOrgContacts` / `useOrgPresence` (shared with Workshop Chat).
- **DMs:** `MindmateDmDrawer` via existing `/api/chat/dm/*`; org isolation enforced by `access_dm_partner`.

## Deep links

`/mindmate?join_mindmate_collab=ABC-DEF` → strips query, opens collab panel, auto-joins by code.

## Tests

- Backend: `tests/test_mindmate_collab_*.py`
- Frontend: `frontend/tests/useMindmateCollab.spec.ts`, `MindmateCollabPanel.spec.ts`, `MindmateCollabHistory.spec.ts`
