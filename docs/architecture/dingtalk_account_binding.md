# DingTalk account binding (rotating pair code)

Universal rules for MindGraph ↔ DingTalk identity. Apply to **all** current and future bind ingress channels.

See also: [`mindbot_tool_ingress.md`](mindbot_tool_ingress.md) for the MindBot pre-Dify tool framework.

## Principles

1. **One universal bind pipeline** — Any channel that receives a pair code (MindBot text today) must call `services.auth.dingtalk_bind_service.claim_dingtalk_qr_bind` or `claim_dingtalk_unbind_pair` with `(token, bind_code, organization_id, dingtalk_staff_id)`.

2. **One MindGraph user → one DingTalk staff per org** — A teacher may link at most one `senderStaffId` within their school org.

3. **One DingTalk staff → one MindGraph user per org** — Claim returns `MINDBOT_BIND_STAFF_TAKEN` when staff is taken.

4. **Pair session token is the trust anchor** — User mints while logged in on the web. MindBot only supplies **which DingTalk staff** confirmed the code.

5. **Rotating 6-digit HMAC code** — Displayed as `000-000` on web; refreshes every 30s. Guess-rate limits per staff/token (30 staff / 40 token per 10-minute window).

6. **Consume after commit** — Token consumed only after successful DB commit.

7. **Claim lock** — Redis `NX` lock per token prevents concurrent double-claims (TOCTOU) before DB commit.

8. **Unbind requires MindBot confirmation** — `POST /dingtalk-bind/unbind` returns `410 Gone`; only the pair-code flow via `/unbind/start` is supported.

9. **Org+code index** — Redis indexes `(org, time-step, code) → token` on mint and room-code refresh for fast MindBot resolution during bulk bind events.

## Pair purposes

| `pair_purpose` | Web endpoint | MindBot message | Claim function |
|----------------|--------------|-----------------|----------------|
| `bind` | `POST /dingtalk-bind/start` | bare `123456` or `123-456` | `claim_dingtalk_qr_bind` |
| `unbind` | `POST /dingtalk-bind/unbind/start` | same shape from **linked** staff | `claim_dingtalk_unbind_pair` |

## Flow (bind)

```
Web → mint bind session → show rotating code (DingTalkPairModal, pulsing “waiting”)
       ↓
MindBot text → PairCodeToolHandler → resolve org + code → claim → reply
       ↓
Web poll status → linked
```

## Related code

| Module | Role |
|--------|------|
| `services/mindbot/tools/handlers/pair_code.py` | MindBot intercept |
| `services/auth/dingtalk_bind_service.py` | Bind/unbind claim |
| `frontend/src/components/auth/DingTalkPairModal.vue` | Bluetooth-style UI |
