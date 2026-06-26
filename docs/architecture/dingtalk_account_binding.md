# DingTalk account binding (QR)

Universal rules for MindGraph ↔ DingTalk identity. Apply to **all** current and future bind ingress channels.

## Principles

1. **One universal bind pipeline** — Any channel that receives a bind QR (MindBot picture today) must call `services.auth.dingtalk_bind_service.claim_dingtalk_qr_bind` with `(token, bind_code, organization_id, dingtalk_staff_id)`. Do not duplicate token consume / DB upsert logic in channel handlers.

2. **One MindGraph user → one DingTalk staff per org** — A teacher may link at most one `senderStaffId` within their school org. Re-binding a different staff replaces the previous link.

3. **One DingTalk staff → one MindGraph user per org** — A staff id cannot be linked to two MindGraph accounts. Claim returns `MINDBOT_BIND_STAFF_TAKEN`.

4. **QR token is the trust anchor** — User mints token while logged in on the web (`POST /auth/dingtalk-bind/start`). The token encodes `user_id` + `organization_id`. Whatever channel delivers the scanned token only supplies **which DingTalk staff** is claiming it.

5. **Rotating bind code** — The QR URL includes a 6-digit HMAC code (`c=`) that rotates every 30 seconds. Claim verifies `bind_code` before linking.

6. **Consume after commit** — `claim_dingtalk_qr_bind` validates org, payload, and staff availability, commits the DB link, then consumes the Redis token. Recoverable failures (org mismatch, staff taken) must **not** burn the token.

## Data model

Table `dingtalk_staff_links`:

| Column | Meaning |
|--------|---------|
| `organization_id` | School org (MindBot scope) |
| `dingtalk_staff_id` | DingTalk `senderStaffId` |
| `user_id` | MindGraph `users.id` |
| `linked_via` | Ingress label (`qr_bind`, future channels) |

Unique constraints: `(organization_id, dingtalk_staff_id)` and `(organization_id, user_id)`.

## Flow

```
Web (logged in) → mint QR token (Redis, TTL 10 min) + rotating 6-digit code
       ↓
MindBot picture → download image → decode QR (?t=token&c=code)
       ↓
claim_dingtalk_qr_bind(token, bind_code, org_id, staff_id)
       ↓ validate org / staff (no consume yet)
       ↓ DB claim_staff_link + commit
       ↓ consume_bind_token (single-use)
       ↓
dingtalk_staff_links + library save via mindbot_{org}_{staff}
```

## Adding a new ingress channel

1. Decode bind token and `bind_code` from QR (reuse `services.mindbot.bind.qr_decode` or `extract_bind_payload_from_text`).
2. Resolve `organization_id` and `dingtalk_staff_id` from **that channel's** identity (MindBot callback, future OAuth, etc.).
3. Call `claim_dingtalk_qr_bind(..., linked_via="your_channel")`.
4. Map error codes to user-facing copy; do not fork DB rules.

## Related code

| Module | Role |
|--------|------|
| `services/auth/dingtalk_bind_service.py` | Universal claim entry |
| `services/auth/dingtalk_bind_redis.py` | Token mint / consume |
| `routers/auth/dingtalk_bind.py` | Web mint / status / unbind |
| `repositories/dingtalk_staff_link_repo.py` | One-user-one-staff enforcement |
| `services/mindbot/bind/picture_handler.py` | MindBot picture ingress (reference implementation) |
| `utils/dify_user_key.py` | Resolve `mindbot_{org}_{staff}` → `users.id` |
