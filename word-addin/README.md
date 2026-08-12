# MindGraph for Word

Microsoft Word **Office.js** add-in: ribbon tab **MindGraph** with MindMate (separate dialog), MindGraph studio, Voice Notes, Showcase, Manual, and Settings.

## Production install (what users / IT should do)

The add-in **shell is hosted on the MindGraph server** at `/word-addin/`. Users do **not** install Node.js and do **not** run `npm`.

### 1. Download the deploy package

Signed-in user with the Chrome-extension school tier:

**Account** → **插件** → **Word 加载项** → `mindgraph-word-addin.zip`

### 2. Teachers (own Word / no school M365 admin)

Unzip layout:

```
mindgraph-word-addin/
├── README.md
├── manifest.xml
├── windows/          ← Windows 10 / 11 → Install.cmd
└── mac/              ← macOS → Install.command
```

- **Windows 10 / 11:** double-click `windows\Install.cmd` (copies to `%LOCALAPPDATA%\MindGraph\WordAddin\`; unzip can be deleted)
- **macOS:** double-click `mac/Install.command` (copies into Word `wef`; unzip can be deleted)
- Then: **MindGraph** ribbon → **Settings** (server, phone, `mgat_`)

Remove: `windows\Uninstall.cmd` or `mac/Uninstall.command`.

### 3. Optional — school M365 admin

Upload root `manifest.xml` via **Integrated apps** (Centralized Deployment).

### Requirements

- Desktop Word on **Windows 10**, **Windows 11**, or **macOS** (Microsoft 365 / Office 2016+)
- MindGraph site on **HTTPS** (Office requires it for non-localhost hosts)

---

## Developer sideload (localhost only)

For coding the shell itself. Manifest in git still uses `https://localhost:3000`.

Do **not** run npm on a `\\wsl$\...` path from Windows PowerShell.

| Where | What |
|-------|------|
| WSL | Edit sources; `./scripts/sync-to-windows.sh` |
| Windows NTFS copy | `npm install`, `npm run signin`, `npm run dev`, `npm start` |

```powershell
cd $env:USERPROFILE\src\MindGraph\word-addin
npm install
npm run signin
npm run dev    # terminal 1
npm start      # terminal 2
```

---

## Notes

- MindMate / Voice / Sign-in = Office **dialogs**; MindGraph / Showcase / Manual = **task panes**.
- Voice is a dedicated recorder window (mic → `WS /api/ws/voice-notes` with saved `mgat_` → Fun-ASR), not the SPA.
- AppSource public store listing is out of scope for v1.
