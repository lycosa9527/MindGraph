# Identity unification (MindGraph ↔ Dify ↔ DingTalk)

How MindGraph tracks one teacher across web MindMate, Chrome extension, DingTalk MindBot, and diagram library saves.

## Canonical identity

| Layer | Identifier | Purpose |
|-------|------------|---------|
| **MindGraph account** | `users.id` (integer PK) | Diagram ownership, auth, admin analytics |
| **Web MindMate (Dify)** | `mg_user_{pk}` or Bayi UUID in `users.phone` | Dify API `user` for browser/PWA/extension chat |
| **DingTalk MindBot (Dify)** | `mindbot_{org_id}_{dingtalk_staff_id}` | Dify API `user` per bound staff; group chats scope per member |
| **Cross-org DingTalk groups** | `mindbot_{org_id}_unknown` | Shared Dify user for LWCP / cross-org group threads |

OAuth QR login (WeChat/DingTalk) and **MindBot account bind** are separate flows. Both resolve to the same `users.id` once the teacher is logged in and bound.

## Binding table

`dingtalk_staff_links`: one MindGraph user ↔ one DingTalk `senderStaffId` per organization.

- Mint bind/unbind codes on web; MindBot claims via [`dingtalk_bind_service.py`](../../services/auth/dingtalk_bind_service.py).
- On successful bind, historical `mindbot_usage_events.linked_user_id` rows are backfilled for that staff.

## Unified conversation list

[`unified_conversations.py`](../../services/dify/unified_conversations.py) merges:

- Web MindMate threads (`channel: web`)
- Bound MindBot threads (`channel: mindbot`), including historical staff IDs after rebind
- Cross-org group threads supplemented from usage telemetry when Dify list APIs omit them

Each list row carries `dify_user`, `server`, and `mindbot_config_id` for message/delete/rename routing.

**Not included** in per-user inbox: unbound MindBot staff (by design). Org export/admin views use `include_unbound=True`.

## Generation session registry

When MindMate or MindBot opens a Dify chat, MindGraph records in Redis (~`GEN_SESSION_TTL_SECONDS`, default 600):

- `conversation_id` → `{ user_id, dify_user_id, channel, organization_id }`
- `dify_user_id` → same payload

`/api/generate_dingtalk` (Dify HTTP tool, no browser cookies) resolves library save via:

1. JWT / API token (direct callers)
2. `conversation_id` / `mg_conversation_id` / `dify_user_id` / `mg_dify_user` from tool body
3. Session registry lookup
4. DingTalk bind table for `mindbot_*` keys

See [`docs/ops/dify_generate_dingtalk_header.md`](../ops/dify_generate_dingtalk_header.md).

## Diagram provenance

`diagrams` optional columns (nullable for legacy rows):

- `source_channel` — e.g. `mindgraph`, `mindmate`, `dingtalk`, `chrome_extension`
- `conversation_id` — Dify conversation when saved from chat tool flow
- `dify_user_key` — Dify `user` string at save time

Authoritative owner remains `diagrams.user_id`.

## Pinned conversations

`pinned_conversations` stores optional routing metadata (`dify_user`, `channel`, `server`, `mindbot_config_id`) so pinned MindBot threads remain openable when they scroll off the merged list page.

## Chrome extension

Uses the same `mg_user_{pk}` via Bearer auth. Fetches unified history from `GET /api/dify/conversations` and loads messages with Dify routing query params. Continues a selected MindBot thread using that row's `dify_user` for streaming.

## API client source (`X-MG-Client`)

mgat_ clients send `X-MG-Client` (`chrome-extension`, `edge-extension`, `openclaw`, `file-reader`). The server sanitizes the label, binds it on `request.state.mg_client`, emits `[TokenAudit]` lines, and records `client_source` on Redis activity sessions / history (admin realtime). Browser JWT sessions bind as `web`. See [`utils/auth/mg_client.py`](../../utils/auth/mg_client.py).

## Related docs

- [DingTalk account binding](dingtalk_account_binding.md)
- [MindBot tool ingress](mindbot_tool_ingress.md)
- [generate_dingtalk ops](../ops/dify_generate_dingtalk_header.md)
