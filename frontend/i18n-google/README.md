# Host Google i18n gap-fill

Reusable module for translating Settings picker locales. Source strings come from `zh`. Keys that still equal English are sent zh-CN → target via Google.

**Live Google calls must run on the Windows host.** WSL has no VPN, so Google is unreachable from WSL.

## Commands (from `frontend/`)

```bash
# WSL: count gaps only (no Google)
npm run i18n:gap-fill -- --dry-run --locale=ta

# Windows host (VPN / system proxy)
powershell -NoProfile -ExecutionPolicy Bypass -File i18n-google/run-on-windows-host.ps1 --locale=ta
```

Optional `--proxy=http://127.0.0.1:7078` if the host VPN proxy is not in the registry.

## Adding a picker locale

1. Register the code in `src/i18n/supportedUiLocales.ts` (or Extra) if it is new.
2. Materialize `messages/<code>/` only when that directory does not exist.
3. Add the code to `INTERFACE_LANGUAGE_PICKER_CODES` and the virtual-keyboard map.
4. Dry-run on WSL, then gap-fill on the Windows host.
5. `npm run i18n:check-banners`, `npm run i18n:check-keys`, `npm run i18n:check-picker-stubs -- --strict`.
