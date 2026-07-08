# Backend deploy verification (test / mg)

Run after deploying current MindGraph backend + Alembic migrations to **test.mindspringedu.com** and **mg.mindspringedu.com**.

Replace `BASE`, `ACCOUNT`, and `MGAT` with values from extension Settings.

## 1. Knowledge Space (File Center)

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer MGAT" \
  -H "X-MG-Account: ACCOUNT" \
  -H "X-MG-Client: chrome-extension" \
  "https://BASE/api/knowledge-space/packages"
```

Expected: **200** (not 404).

## 2. MindMate auth + stream endpoint reachability

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer MGAT" \
  -H "X-MG-Account: ACCOUNT" \
  -H "X-MG-Client: chrome-extension" \
  "https://BASE/api/auth/me"
```

Expected: **200**.

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -H "Authorization: Bearer MGAT" \
  -H "X-MG-Account: ACCOUNT" \
  -H "Content-Type: application/json" \
  -H "X-MG-Client: chrome-extension" \
  -d '{"message":"ping","user_id":"test","conversation_id":null}' \
  "https://BASE/api/ai_assistant/stream"
```

Expected: **200** with `text/event-stream` (not 502 from proxy timeout).

**CSRF / session cookies:** The extension uses `credentials: 'omit'` on mgat requests so a prior web login on the same host does not attach `access_token` / `csrf_token` cookies. After backend deploy, mgat POSTs also skip double-submit CSRF when `Authorization: Bearer mgat_…` is present (belt-and-suspenders for OpenClaw / file-reader).

Simulate incidental cookies (should still succeed once backend is updated):

```bash
curl -sS -o /dev/null -w "%{http_code}\n" \
  -b "access_token=fake; csrf_token=fake" \
  -H "Authorization: Bearer MGAT" \
  -H "X-MG-Account: ACCOUNT" \
  -H "Content-Type: application/json" \
  -H "X-MG-Client: chrome-extension" \
  -d '{"message":"ping","user_id":"test","conversation_id":null}' \
  "https://BASE/api/ai_assistant/stream"
```

Expected: **200** (not **403** Invalid or missing CSRF token).

## 3. PNG library header (CORS expose)

Generate a mind map from the extension popup, then in popup DevTools → Network → `web_content_mindmap_png`:

- Response header `X-MG-Diagram-Id` present when library save succeeds
- Or `Content-Disposition: attachment; filename="mindgraph-{uuid}.png"`

Popup should show **View in library** linking to `https://BASE/canvas?diagramId=...`.

## 4. nginx / openresty (MindMate SSE + extension PNG)

On the reverse proxy, set `proxy_read_timeout` / `proxy_send_timeout` ≥ **300s** for `/api` (covers MindMate SSE and extension mind-map PNG; extension client aborts PNG at **180s**).

See [production_security_deploy.md](../docs/architecture/production_security_deploy.md).

## 5. Edge extension client label (optional)

Repeat §2 with `X-MG-Client: edge-extension` — same **200** responses; server logs distinguish Edge from Chrome.

## 6. Per-environment checklist

| Check | test | mg |
|-------|------|-----|
| Migrations applied | | |
| `/api/knowledge-space/packages` → 200 | | |
| Web MindMate chat works (same account) | | |
| Extension preset + token from **same** server | | |
| `proxy_read_timeout` ≥ 300s (or ≥ 180s for PNG only) | | |
| `FEATURE_KNOWLEDGE_SPACE=true` (File Center tab) | | |
| Cert test account: `api_token` + `chrome_extension` tier features | | |
