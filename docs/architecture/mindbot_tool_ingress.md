# MindBot tool ingress

Pre-Dify handlers for admin/user tools that must **not** go through the LLM (pair codes, future slash commands).

## Pipeline placement

```
DingTalk callback → validate → try_handle_mindbot_tools() → Dify (if None)
```

Registered in `services/mindbot/tools/handlers/__init__.py` on import. The pipeline calls `services.mindbot/tools/dispatch.py`.

## Adding a tool

1. Implement `MindbotToolHandler` (`services/mindbot/tools/registry.py`):
   - `priority` — lower runs first (default pair code uses `10`)
   - `matches(ctx)` — **cheap** check (regex, prefix); no Redis/DB
   - `handle(ctx)` — return `(200, headers)` when handled, else `None`
2. Register in `services/mindbot/tools/handlers/__init__.py`
3. Add user-facing copy in the appropriate messages module
4. Add web/API mint endpoints if the tool uses rotating pair codes

## Pair-code tools (Bluetooth-style)

Shared pattern for bind, unbind, and future account actions:

| Layer | Module |
|-------|--------|
| Web mint + room code | `routers/auth/dingtalk_bind.py` |
| Redis session + org index | `services/auth/dingtalk_bind_redis.py` |
| Claim (bind/unbind) | `services/auth/dingtalk_bind_service.py` |
| MindBot intercept | `services/mindbot/tools/handlers/pair_code.py` |
| 6-digit parse | `services/mindbot/bind/code_parse.py` |
| UI | `frontend/src/components/auth/DingTalkPairModal.vue` |

Session payload includes `pair_purpose`: `bind` | `unbind`. The same 6-digit message shape is used; purpose is resolved from the pending Redis session for that org + HMAC code.

## Performance

Normal chat: one `matches()` regex per registered handler (microseconds). Pair-code messages: small Redis lookup; still skips Dify entirely.

## Audit logging

Admin-tool traffic uses **distinct log prefixes** so it is easy to filter away from normal `[MindBot]` Dify chat logs:

| Prefix | Source | Example |
|--------|--------|---------|
| `[MindBotTool]` | MindBot pre-Dify ingress | `intercepted tool=pair_code skip_dify=1` |
| `[MindBotTool]` | Pair-code handler | `attempt tool=pair_code purpose=bind` |
| `[MindBotTool]` | Pair-code handler | `outcome tool=pair_code ok=1 purpose=bind outcome=bind_ok` |
| `[DingtalkBind:web]` | Web mint/cancel API | `mint_ok user_id=42 org_id=5 purpose=bind token=…abc` |
| `[DingtalkBind:claim]` | DB claim service | `ok action=bind user_id=42 org_id=5 staff=…` |

Modules: `services/mindbot/tools/audit_log.py`, `services/auth/dingtalk_bind_audit_log.py`.

Future admin tools should set `tool_name` on the handler and use `[MindBotTool]` helpers from `audit_log.py`.

### Client (browser)

| Prefix | Source | Example |
|--------|--------|---------|
| `[DingtalkPair:client]` | Pair modal / account entry | `modal_open purpose=bind generation=1` |
| `[DingtalkPair:client]` | Mint + poll lifecycle | `mint_ok token=…abc ttl_seconds=600` → `pairing_completed linked=1` |

Module: `frontend/src/utils/dingtalkPairAuditLog.ts`. Key lifecycle events are also POSTed to `/api/frontend_log` with `source=dingtalk_pair` in production so server-side log aggregation can correlate with `[DingtalkBind:web]` and `[MindBotTool]`.
