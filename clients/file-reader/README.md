# MindGraph File Reader (Windows)

Desktop helper that sends **WeChat** or **DingTalk** chat exports to **MindGraph Document Summary** (文档总结).

## Requirements

- Windows 10/11
- Python 3.13 (development builds)
- MindGraph account with an **API token** (`mgat_…`) — mint in **Settings → API token**
- At least one **Document Summary** package on your account

## Authentication

The reader sends:

| Header | Value |
|--------|--------|
| `Authorization` | `Bearer mgat_…` |
| `X-MG-Account` | Your MindGraph login phone |
| `X-MG-Client` | `file-reader` |

Credentials are saved under `%TEMP%\mindgraph-file-reader\`:

| File | Contents |
|------|----------|
| `settings.json` | Server URL and platform preference only (no secrets) |
| `credentials.dpapi` | API token + phone encrypted with **Windows DPAPI** (current user) |

Legacy plaintext files under `%TEMP%` or `~/.mindgraph/` are migrated on first launch and then deleted.

Only **https://** servers on `*.mindspringedu.com` are accepted (`http://localhost` / `127.0.0.1` allowed for local dev). Use **Clear saved credentials** in the app to remove stored tokens from this PC.

Default server: `https://test.mindspringedu.com`

## Usage

1. Run `mindgraph-file-reader.exe` (or `python -m file_reader` from this directory).
2. Enter server URL, API token, and phone → **Connect & save**.
3. Pick a **Document Summary package** card (loaded from Knowledge Space).
4. Export chats to `.txt` (WeChat) or `.json`/`.txt` (DingTalk), browse to the folder, select a file.
5. Click **Send to selected package** — pairing is handled automatically.

## Privacy

- Chat text is read **locally** from files you select; only the chosen export is uploaded.
- Pairing codes come from the website session you select; they expire after **10 minutes**.
- We do not upload WeChat/DingTalk database files.
- API tokens are **DPAPI-encrypted** on disk; use **Clear saved credentials** when done on a shared PC.

## Build (Windows)

```powershell
cd clients\file-reader
.\build_windows.ps1
```

Output: `dist\mindgraph-file-reader.exe` and `frontend/public/downloads/mindgraph-file-reader.zip`.

### SmartScreen

Unsigned executables may trigger SmartScreen. For production, sign the binary with your code-signing certificate.
