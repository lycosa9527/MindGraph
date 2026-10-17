# Host Google i18n gap-fill

Reusable module for translating Settings picker locales. Source strings come from `zh`. Keys that still equal English are sent zh-CN → target via Google.

**Live Google calls must run on the Windows host (VPN / system proxy).** WSL cannot reach Google.

## Commands (from `frontend/`)

```bash
# WSL: count gaps only (no Google) — stays in WSL
npm run i18n:gap-fill -- --dry-run --locale=ta

# WSL: live fill — automatically invokes Windows PowerShell + host Node (VPN)
npm run i18n:gap-fill -- --locale=ta
npm run i18n:gap-fill -- --only-ns=canvas --all-enabled

# Do not run `node i18n-google/cli.ts` directly from WSL for live fill.
```

Before gap-fill, sync new keys from `zh` / `en`:

```bash
node scripts/sync-messages-keys-from-reference.ts
```

### Windows host requirements

- Node.js on **Windows** (match `frontend/.nvmrc` when possible) — not WSL Node.
- VPN / Clash (or similar) with system proxy enabled (e.g. `127.0.0.1:7078`).

Manual host run:

```powershell
cd frontend
powershell -NoProfile -ExecutionPolicy Bypass -File i18n-google/run-on-windows-host.ps1 --locale=ta
```

Optional `--proxy=http://127.0.0.1:7078` if the host VPN proxy is not in the registry.

### Linux CI / Cursor Cloud

```bash
MINDGRAPH_I18N_GAP_FILL_DIRECT=1 npm run i18n:gap-fill -- --dry-run
```

Live fill on Linux only when Google is reachable from that environment.

## Adding a picker locale

1. Register the code in `src/i18n/supportedUiLocales.ts` (or Extra) if it is new.
2. Materialize `messages/<code>/` only when that directory does not exist.
3. Add the code to `INTERFACE_LANGUAGE_PICKER_CODES` and the virtual-keyboard map.
4. `node scripts/sync-messages-keys-from-reference.ts`
5. Dry-run on WSL, then `npm run i18n:gap-fill` on the Windows host (via npm wrapper).
6. `npm run i18n:check-banners`, `npm run i18n:check-keys`, `npm run i18n:check-picker-stubs -- --strict`.
