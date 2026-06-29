# MindGraph File Reader (Windows)

Desktop helper for **MindGraph Document Summary** (文档总结):

- **Chat history** tab — send **WeChat** or **DingTalk** exports via website pairing
- **SmartEdu** tab — download lesson assets from **basic.smartedu.cn** (PDFs + MP4 via ffmpeg)

## Requirements

- Windows 10/11
- Python 3.13 (development builds)
- MindGraph account with an **API token** (`mgat_…`) — mint in **Settings → API token**
- **ffmpeg essentials** embedded in the onefile exe for SmartEdu video merge (PDFs work without it at runtime)

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
| `smartedu_token.dpapi` | SmartEdu access token (separate DPAPI blob) |

Default server: **test.mindspringedu.com** (dropdown also offers **mg.mindspringedu.com** and **localhost:9527** for local dev)

## Usage — Chat history

1. Run `mindgraph-file-reader.exe` or `python -m file_reader`.
2. Connect with API token and phone.
3. Open Document Summary → Chat history on the website; select the live session card.
4. Browse to a chat export and click **Send to website session**.

## Usage — SmartEdu

1. Connect your MindGraph account.
2. Open the **SmartEdu** tab → **Open SmartEdu login** (WebView2) or **Paste token**.
3. Paste a `classActivity` URL from basic.smartedu.cn.
4. Select assets (video, courseware PDF, lesson plan PDF, task sheet PDF).
5. Optional: upload PDFs to a Document Summary package.
6. Click **Download selected**.

Video uses ffmpeg with `X-ND-AUTH`; DRM merge may fail while PDFs still download.

## Build

```powershell
cd clients\file-reader
.\build_windows.ps1
```

Output: `dist\mindgraph-file-reader.exe` (~80–110 MB onefile with embedded ffmpeg essentials) and `frontend/public/downloads/mindgraph-file-reader.zip`.

## Privacy

- Chat and SmartEdu content is processed locally; only opted-in PDFs upload to MindGraph.
- Tokens are DPAPI-encrypted on this PC only.
