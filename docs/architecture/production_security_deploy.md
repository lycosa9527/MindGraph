# Production security deploy checklist

Use this when rolling hardened MindGraph to **mg.mindspringedu.com** (or any TLS-terminated reverse-proxy deployment).

## Pre-deploy: server `.env`

`enforce_production_security_guards()` aborts startup in non-debug when secrets are missing, weak, or placeholder values (`CHANGE-ME`, etc.).

| Variable | When required |
|----------|----------------|
| `PUBLIC_DASHBOARD_PASSKEY` | Only when the public stats dashboard is enabled (non-empty passkey) |
| `BAYI_PASSKEY`, `BAYI_DECRYPTION_KEY` | `AUTH_MODE=bayi` |
| `DEVICE_REGISTRATION_SECRET` | `FEATURE_SMART_RESPONSE=True` |
| `GEWE_WEBHOOK_SECRET` | `FEATURE_GEWE=True` |
| `ENTERPRISE_MODE_PUBLIC_ACK=I_UNDERSTAND_PUBLIC_EXPOSURE_RISK` | `AUTH_MODE=enterprise` |

Generate strong random passkeys; do **not** copy `CHANGE-ME-before-production` from `env.example`.

## Pre-deploy: reverse proxy (openresty / nginx)

TLS usually terminates at the edge. The Python app must see HTTPS semantics for **Secure cookies**, **HSTS**, and **CSRF** consistency.

1. Forward protocol to the app:

```nginx
proxy_set_header X-Forwarded-Proto $scheme;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header Host $host;
```

2. Set MindGraph env on the app host:

```bash
TRUSTED_PROXY_IPS=127.0.0.1,<openresty-peer-ip>
FORCE_SECURE_COOKIES=true
```

`TRUSTED_PROXY_IPS` accepts exact IPs, CIDR ranges, and the keywords `private`
(loopback + all RFC1918 / Docker / LAN ranges) and `loopback`. Behind a reverse
proxy the app must trust the proxy peer so `X-Forwarded-For` is honored —
otherwise every client looks like the proxy IP and per-IP rate limits plus
AbuseIPDB / CrowdSec IP-reputation blocking key off the wrong address.

### Nginx Proxy Manager (Docker)

NPM runs in a container, so its peer IP (a Docker bridge address like
`172.x.x.x`) changes when the container is recreated. Set once and forget:

```bash
TRUSTED_PROXY_IPS=private
```

This is safe **only when port 9527 is not directly reachable by untrusted hosts**
(i.e. the firewall exposes 80/443 via NPM and the app port is internal). NPM
already forwards `X-Forwarded-For`, `X-Real-IP`, and `X-Forwarded-Proto` by
default, so Secure cookies + HSTS work without extra config. To pin an exact
peer instead, run a request and read `grep "Request:" logs/app.log` — the
`from <IP>` value (until the proxy is trusted) is the peer to whitelist.

3. Optional defense-in-depth at the edge:

```nginx
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains" always;
```

## Deploy order (same maintenance window)

Deploy **backend and frontend build together**. CSRF double-submit is enforced once the `csrf_token` cookie exists; the SPA must send `X-CSRF-Token` on mutations (global fetch interceptor in `frontend/src/utils/installCsrfFetchInterceptor.ts`).

1. Apply `.env` + proxy headers.
2. Deploy backend (Python).
3. Deploy frontend production build (includes `/pwa-install-early.js`, CSRF interceptor, CSP meta without `unsafe-eval`).
4. Run post-deploy verification (below).

## Post-deploy verification

```bash
# Response headers (no unsafe-eval; HSTS should appear)
curl -sI https://mg.mindspringedu.com/ | grep -iE 'strict-transport|content-security'

# External PWA bootstrap (must not 404)
curl -sI https://mg.mindspringedu.com/pwa-install-early.js | head -5

# Backend smoke (from app host / CI)
python -m pytest tests/test_csrf_protection.py tests/test_security_production_hardening.py -q
python -c "from main import app; assert app.title"
```

Manual in browser: login → idle refresh or wait → perform a mutation (rename conversation) → logout. Confirm no `403 Invalid or missing CSRF token` and `csrf_token` cookie is present after login.

Monitor logs for `[Security] CSRF_BOOTSTRAP` events; they should taper off after users receive new cookies.

## ESP32 / Smart Response

`GET /api/devices/{watch_id}/status` requires header `X-Device-Registration-Secret` when `FEATURE_SMART_RESPONSE=True`. The public response omits `student_name`.

**Before enabling the feature on production:**

1. Flash firmware that sends `X-Device-Registration-Secret: <DEVICE_REGISTRATION_SECRET>` on status polls.
2. Set `DEVICE_REGISTRATION_SECRET` in server `.env`.
3. Enable `FEATURE_SMART_RESPONSE=True` and restart.

## JWT secret rotation (operations)

Use the CLI after Redis is reachable:

```bash
conda activate python313
cd /mnt/d/MindGraph
python scripts/ops/rotate_jwt_secret.py
```

This moves the current secret to `jwt:secret:previous` and generates a new active secret. In-flight access tokens signed with the previous secret remain valid until expiry.

## Follow-up after stable rollout

- Reduce CSRF bootstrap allow-once path once `[Security] CSRF_BOOTSTRAP` logs are near zero.
- Migrate legacy pickle embedding blobs to JSON in Knowledge Space.
- Record security release notes in `CHANGELOG.md`.
