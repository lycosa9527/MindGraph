# MindGraph File Reader (Windows)

Desktop helper for **MindGraph Document Summary** (文档总结):

- **Chat history** tab — send **WeChat**, **DingTalk**, or **WeCom** exports via website pairing
- **国家智慧教育平台** tab — platform browser with auto-detected downloads for SmartEdu, Bilibili, YouTube, Douyin, TikTok, WeChat Channels, and Tencent Meeting cloud recordings

## Requirements

- Windows 10/11
- Python 3.13 (development builds)
- MindGraph account with an **API token** (`mgat_…`) — mint in **Settings → API token**
- **ffmpeg essentials** embedded in the onefile exe for video merge (PDFs work without it at runtime)

Install Python dependencies:

```powershell
cd clients\file-reader
python -m pip install -r requirements.txt
```

Optional embedded WebView2 fallback (not recommended — can hang inside the panel):

```powershell
set MINDGRAPH_BROWSER=webview2
```

Requires **WebView2 Runtime** when using that fallback.

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
| `platform-browser/playwright-edge/` | Playwright Chromium profile (cookies, localStorage) |
| `platform-browser/webview2/` | WebView2 profile (only when `MINDGRAPH_BROWSER=webview2`) |
| `smartedu-browser.log` | Platform browser debug log |

Default server: **test.mindspringedu.com** (dropdown also offers **mg.mindspringedu.com** and **localhost:9527** for local dev)

## Usage — Chat history

1. Run `mindgraph-file-reader.exe` or `python -m file_reader`.
2. Connect with API token and phone.
3. Open Document Summary → Chat history on the website; select the live session card.
4. Browse to a chat export and click **Send to website session**.

## Usage — Platform browser tab

1. Connect your MindGraph account.
2. Open the **国家智慧教育平台** tab — a **separate Chromium window** opens (bundled with the exe; first launch may take ~30s while it unpacks).
3. Sign in and browse in that browser window. The in-panel grey area shows navigation hints; use the **toolbar above** (back, forward, address bar, **前往**, **下载**).
4. Navigate to a lesson page, video page, or cloud recording playback page.
5. When resources are detected, the **下载** button shows a red badge with the count.
6. Click **下载**, choose items, and save to `Downloads/<platform>/`.

**Multi-tab:** If you open several browser tabs, the panel follows **whichever tab you loaded most recently** (toolbar navigation always targets that active tab). Prefer a single tab when detecting downloads.

SmartEdu uses `ND_UC_AUTH` token auto-capture; Bilibili/YouTube/Douyin/TikTok use session cookies via yt-dlp; Tencent Meeting and WeChat Channels use network capture while playing.

Debug log: `%TEMP%\mindgraph-file-reader\smartedu-browser.log`

### Browser backend

| `MINDGRAPH_BROWSER` | Behavior |
|---------------------|----------|
| `playwright` (default) | Bundled Chromium in its own window |
| `webview2` | Legacy embedded WebView2 inside the panel |

## Build

```powershell
cd clients\file-reader
.\build_windows.ps1
```

Bundles the Playwright **driver + Chromium** into the onefile exe (large download, ~300 MB+). Before building, `build_windows.ps1` runs `PLAYWRIGHT_BROWSERS_PATH=0 playwright install chromium`. Output: `dist\mindgraph-file-reader.exe` and `frontend/public/downloads/mindgraph-file-reader.zip`.

## Privacy

- Chat and downloaded content stay local unless you upload to MindGraph.
- Tokens are DPAPI-encrypted on this PC only.
