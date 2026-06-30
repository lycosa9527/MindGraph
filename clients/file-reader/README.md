# MindGraph File Reader (Windows)

Desktop helper for **MindGraph Document Summary** chat history upload:

- Send **WeChat**, **DingTalk**, or **WeCom** chat exports to a live website pairing session

For **SmartEdu**, **Baidu Wenku**, **360doc**, and other document downloads, use the **MindGraph Chrome extension** (Download tab).

## Requirements

- Windows 10/11
- Python 3.13 (development builds)
- MindGraph account with an **API token** (`mgat_…`) — mint in **Settings → API token**

Install Python dependencies:

```powershell
cd clients\file-reader
python -m pip install -r requirements.txt
```

## Authentication

| Header | Value |
|--------|--------|
| `Authorization` | `Bearer mgat_…` |
| `X-MG-Account` | Your MindGraph login phone |
| `X-MG-Client` | `file-reader` |

Stored under `%TEMP%\mindgraph-file-reader\`:

| File | Contents |
|------|----------|
| `settings.json` | Server URL and platform preference |
| `credentials.dpapi` | MindGraph API token + phone (DPAPI) |

Default server: **test.mindspringedu.com** (dropdown also offers **mg.mindspringedu.com** and **localhost:9527** for local dev)

## Usage

1. Run `mindgraph-file-reader.exe` or `python -m file_reader`.
2. Connect with API token and phone.
3. Open Document Summary → Chat history on the website; select the live session card.
4. Browse to a chat export and click **Send to website session**.

## Build

```powershell
cd clients\file-reader
.\build_windows.ps1
```

Output: `dist\mindgraph-file-reader.exe` and `frontend/public/downloads/mindgraph-file-reader.zip`.

## Privacy

Chat exports stay on your PC until you send them to your MindGraph session.
