# Word add-in embed auth

MindGraph for Word (`word-addin/`) opens the live SPA in an Office.js task pane. Session cookies must be set on the **SPA origin**, not on `https://localhost` where the add-in shell runs.

## Flow

1. Settings stores phone + `mgat_` (OfficeRuntime.storage / localStorage) and **probes** `POST /api/auth/embed/probe` on Save (validates credentials only — no Redis handoff). When the shell is hosted at `/word-addin/*`, **Server URL is locked to `location.origin`** (CSP same-origin); stale test/prod defaults are migrated on hydrate.
2. MindGraph / MindMate / Showcase host page `POST /api/auth/embed/handoff` with `Authorization: Bearer mgat_…`, `X-MG-Account`, `X-MG-Client: word-addin`.
3. API stores a one-time Redis code (~60s) and returns `{ "handoff": "…" }`.
4. Host navigates to `GET /api/auth/embed/complete?handoff=…&next=/mindgraph` (top-level `location.replace` — first-party cookies on the SPA origin; response uses `Referrer-Policy: no-referrer`).
5. API consumes the code, issues JWT access + refresh via the same path as login (`set_auth_cookies`), redirects with `?embed=word-addin`.
6. SPA `checkAuth()` succeeds from httpOnly cookies — **no `/auth` login page**. Layout stays **desktop** (`?embed=word-addin` / sessionStorage) — never `/m/*`.
7. **Voice** is a dedicated Office **dialog** (not SPA handoff). It opens `voice.html` and connects `WS /api/ws/voice-notes?token=mgat_…&account=…` (same Fun-ASR bridge as web Voice Notes). Do not put `mgat_` in SPA navigation URLs; the Voice dialog query is the supported client-token path for browser WebSockets (no custom headers).

If handoff fails, the shell stays put and offers an optional guest open (guest is not login-free). `next` must be a same-site path under an allowlist (`/mindgraph`, `/mindmate`, `/canvas`, `/showcase`). `/voice-notes` remains a web SPA route; Word Voice does not use embed handoff.
