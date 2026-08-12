# MindGraph for Word

Microsoft Word **Office.js** add-in: ribbon tab **MindGraph** with MindMate, MindGraph studio, Voice Notes, Showcase, Manual, and Settings.

- Task panes use **Edge WebView2** (document stays below the ribbon).
- Default API: `https://test.mindspringedu.com`
- Client header: `X-MG-Client: word-addin`
- With phone + `mgat_` in Settings (verified on Save), MindGraph / Showcase / MindMate open **login-free** via `/api/auth/embed/handoff` → `/complete` (httpOnly session cookies on the SPA origin) and **desktop** UI (`?embed=word-addin`). Handoff failure stays on the shell (optional guest) — it does not dump into the web login page.
- **MindMate** opens a medium **separate dialog window** (Office Dialog API) so it can run beside the MindGraph task pane.

## Requirements

- Desktop **Microsoft Word** (Windows or Mac) with a Microsoft 365 / Office license that supports sideloaded add-ins
- Node.js 18+ (20+ recommended) on the **Windows/Mac** machine that runs Word
- HTTPS localhost certs (`npm run signin` once on that machine)

Dev dependencies are intentionally lean (`vite` + `office-addin-dev-certs` only). Sideload uses a small PowerShell registry helper instead of `office-addin-debugging` (that package pulls a deprecated Microsoft Teams toolkit tree).

**Certificate:** Word blocks untrusted HTTPS. On Windows, run `npm run signin` once (accept the CA install prompt). Vite serves with those same certs — do not use a random self-signed cert.

## Important (WSL + Windows Word)

Do **not** run `npm install` / `npm run signin` / `npm start` from PowerShell on a `\\wsl$\...` path. Windows npm cannot handle Linux `node_modules/.bin` symlinks (`EISDIR`).

| Where | What |
|-------|------|
| WSL | Edit sources; optional `npm install` for validate; sync to NTFS |
| Windows (NTFS copy) | `npm install`, `npm run signin`, `npm run dev`, `npm start` |

### Sync to Windows, then sideload

In WSL:

```bash
cd ~/src/MindGraph/word-addin
./scripts/sync-to-windows.sh
# default: /mnt/c/Users/<you>/src/MindGraph/word-addin
```

In **Windows PowerShell** (native path, not `\\wsl$\`):

```powershell
cd $env:USERPROFILE\src\MindGraph\word-addin
npm install
npm run signin    # once — trusts office-addin-dev-certs

# terminal 1
npm run dev

# terminal 2
npm start
```

`npm start` registers the manifest under Office **WEF Developer** and opens Word. Then: **Insert → Add-ins → Developer Add-ins → MindGraph**.

1. Open **Settings** → set server, phone, `mgat_…` → Save  
2. Click **MindGraph** → desktop studio, signed in when token is saved  

Stop / unregister:

```powershell
npm stop
```

Re-sync after source edits in WSL (`./scripts/sync-to-windows.sh`), then restart `npm run dev` on Windows if needed. Re-run `npm install` only when `package.json` changed.

### Mac

```bash
cd word-addin
npm install
npm run signin
npm run dev
```

Sideload the `manifest.xml` via Word for Mac’s developer / sideload flow (Insert → Add-ins). `npm start` / `npm stop` are Windows-only (PowerShell registry).

## Validate manifest

```bash
cd word-addin
npm install
npm run validate
```

## Notes

- Sideload is for development. AppSource / org catalog publish is out of scope for v1.
- Live MindMate SPA embed is still a stub chat; MindGraph uses the live web studio.
- If you already broke `node_modules` via `\\wsl$\`, delete it in WSL (`rm -rf node_modules && npm install`) and use the NTFS copy for Word.
- Old WPS add-in Windows tree (if any): delete `%USERPROFILE%\src\MindGraph\wps-addin`
