# MindGraph browser extension (Chrome & Edge)

This folder is a **Manifest V3** extension for **Google Chrome** and **Microsoft Edge** (Chromium). Same build — load this directory unpacked in either browser. It captures text from the active tab and calls MindGraph **`POST /api/web_content_mindmap_png`** with your **`mgat_`** token and **`X-MG-Account`** (phone), then downloads the PNG.

## Icons

Toolbar and store icons match the **web app favicon** ([`frontend/public/favicon.svg`](../frontend/public/favicon.svg)): stone-900 rounded square (`#1c1917`) with a white **M**.

PNG sizes are generated for Chrome from that design. Regenerate after changing the SVG:

`python chrome-extension/scripts/generate_icons.py`

Regenerated sizes: 16, 32, 48, 128, and **300** (Edge Add-ons store logo).

## Publish to Microsoft Edge Add-ons (REST API v1.1)

Initial listing is done in [Partner Center](https://partner.microsoft.com/dashboard/microsoftedge/public/login?ref=dd). **Updates** to an existing product can be automated with the [Edge Add-ons Update REST API](https://learn.microsoft.com/en-us/microsoft-edge/extensions/update/api/using-addons-api?tabs=v1-1).

### One-time Partner Center setup

1. Partner Center → **Microsoft Edge** → **Publish API**.
2. Click **Enable** next to “enable the new experience” (API v1.1).
3. **Create API credentials** — save **Client ID** and **API key**.
4. Copy the extension **Product ID** from **Extension overview** (GUID in the URL between `microsoftedge/` and `/packages`).

### Local credentials

Set in repo root `.env` (or `chrome-extension/.env.edge-publish`):

```bash
EDGE_ADDON_CLIENT_ID=...
EDGE_ADDON_API_KEY=...
EDGE_ADDON_PRODUCT_ID=...   # Partner Center → Extension overview → Product ID
```

Never commit API keys. `EDGE_ADDON_API_KEY` values with `$` must be single-quoted in `.env` when using `source`.

### Manual push while under review (recommended now)

Microsoft returns `InProgressSubmission` if you API-publish while a submission is already in review. **Package locally and upload in Partner Center:**

```bash
bash chrome-extension/scripts/manual_push_edge.sh
```

Then Partner Center → your extension → upload `chrome-extension/dist/mindgraph-extension.zip` → submit from the UI.

Same store zip is also served by the backend: `GET /api/downloads/mindgraph-chrome-extension` (or `/api/downloads/mindgraph-extension`).

### Package only (store zip)

Builds `chrome-extension/dist/mindgraph-extension.zip` with `manifest.json` at the archive root (excludes `node_modules/`, tests, dev scripts):

```bash
cd /mnt/d/MindGraph
PYTHONPATH=. python scripts/package_extension.py
```

### Upload + publish via API (after current review completes)

```bash
set -a && source .env && set +a
cd /mnt/d/MindGraph
PYTHONPATH=. python scripts/publish_edge_addon.py \
  --notes-file chrome-extension/scripts/edge_certification_notes.example.txt
```

Use `--upload-only` to refresh the draft package without submitting for review.

Stages:

1. **Package** — zip extension sources (`utils/extension_store_packaging.py`).
2. **Upload** — `POST /v1/products/{productId}/submissions/draft/package` (headers: `Authorization: ApiKey …`, `X-ClientID`, `Content-Type: application/zip`).
3. **Poll** `GET .../draft/package/operations/{operationId}` until `status` is `Succeeded`.
4. **Publish** — `POST /v1/products/{productId}/submissions` with body `{"notes":"..."}` (`Content-Type: application/json`).
5. **Poll** `GET .../submissions/operations/{operationId}` until `Succeeded`.

Per [Microsoft API reference](https://learn.microsoft.com/en-us/microsoft-edge/extensions/update/api/addons-api-reference): initial listing and store metadata (description, logo, screenshots) remain Partner Center only; the REST API updates the **package** and submits the draft for certification.

Useful flags:

- `--package-only` — zip only, no API calls.
- `--upload-only` — upload draft package without submitting for review.
- `--zip path/to/existing.zip` — skip repackaging.

Environment variables: `EDGE_ADDON_CLIENT_ID`, `EDGE_ADDON_API_KEY`, `EDGE_ADDON_PRODUCT_ID`; optional `EDGE_ADDON_API_BASE`, `EDGE_ADDON_RETRY_LIMIT`, `EDGE_ADDON_RETRY_SECONDS`, `EDGE_ADDON_PUBLISH_NOTES`.

Certification notes must be **under 2000 characters**. Edit [`scripts/edge_certification_notes.example.txt`](scripts/edge_certification_notes.example.txt) (test phone/token/contact) before publishing.

This API updates the **package** only. Store metadata (description, screenshots, logo) still requires Partner Center.


Locale strings live in **`chrome-extension/_locales/`** (`en`, `zh_CN`, `zh_TW`). The manifest `default_locale` is **`en`**.

- **Settings → Language** — One control (stored as `uiLanguage`: Match browser, English, 简体, 正體). It sets **both** the popup’s effective UI strings (optional override by loading a locale’s `messages.json`) and the **`language`** field sent to **`POST /api/web_content_mindmap_png`**, resolved in the service worker to match the server’s prompt registry ([`scripts/build_prompt_language_registry.py`](../scripts/build_prompt_language_registry.py); the allowed code list is embedded in [`background.js`](background.js) as `PROMPT_OUTPUT_LANGUAGE_CODES`). Page text language and diagram output language are **independent** (e.g. English article + Chinese map labels).

- **Match browser** — Uses `chrome.i18n.getMessage` / UI language to pick copy and, for the API, maps the browser UI language to a registry code in [`shared-mindgraph.js`](shared-mindgraph.js) (`resolvePromptLanguageFromUiMode`).

## Load unpacked (Chrome or Edge)

**Chrome**

1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked**.
4. Select this **`chrome-extension`** directory (the folder that contains `manifest.json`).
5. After editing files, click **Reload** on the extension card.

**Microsoft Edge** (Chromium, **120+** recommended)

1. Open `edge://extensions`.
2. Turn on **Developer mode** (left sidebar).
3. Click **Load unpacked**.
4. Select the **same** **`chrome-extension`** folder (not a separate copy).
5. Click **Reload** after code changes.

You can install in **both** Chrome and Edge on the same PC — each browser keeps its own extension storage and settings. Use Chrome for one workflow and Edge for another if you prefer; they do not conflict.

**Edge notes (v0.4.3+):**

- Requires **Edge 120+** (`minimum_edge_version` in `manifest.json`).
- Blob downloads use a **single shared offscreen document** (`offscreen-blobs.js`) so mind-map PNG and document extract do not race to create two offscreen pages (a common Edge failure mode).
- On Edge, the extension **skips service-worker `blob:` URLs** and uses offscreen **BLOBS** instead (Edge often exposes `createObjectURL` in the worker but downloads fail).
- Large files are sent to offscreen via **ArrayBuffer** (structured clone), not base64, when the browser supports it — better for multi‑MB PDFs.
- If offscreen is unavailable, downloads fall back to a **data:** URL (works for small files only). Update Edge and reload the extension if downloads fail.

## Settings

- **Server** — Dropdown: **`mg.mindspringedu.com`** (production), **`test.mindspringedu.com`**, or **`localhost:9527`** (local dev). Stored as full `http`/`https` origin after save. Existing custom URLs map to production on load.
- **Account (phone)** — Same value as **`X-MG-Account`** for API tokens.
- **API token** — `mgat_…` from the app (**账户信息** → **API Token**). After save, a line under the token shows **valid-until** from **`GET /api/auth/api-token`** (metadata only; same auth headers as `/me`).

The extension sends **`X-MG-Client: chrome-extension`** or **`X-MG-Client: edge-extension`** (detected automatically) on mgat requests so the server can label **`[TokenAudit]`** log lines and Redis activity tracker entries (`client_source`).

**Save** calls **`GET /api/auth/me`** to verify the token, then persists settings. **Credentials are written to `chrome.storage.local` only after that request succeeds**. Network failures show an error and nothing is saved.

**Advanced**

- **PNG width / height** — Optional; if set, sent on **`POST /api/web_content_mindmap_png`** (server defaults apply when empty).
- **Ask where to save** — Optional save dialog for each download (`chrome.downloads` with `saveAs`).

**Code layout** — [`shared-mindgraph.js`](shared-mindgraph.js) is loaded by the service worker (`importScripts`) and the popup: shared URL helpers, request body, error parsing, and default base URL. The **long `fetch` (PNG) and `downloads.download` run in the service worker** for toolbar, context menu, and keyboard; the **popup** opens a `runtime.connect` port named **`mindmap-generate-<tabId>`** so the worker **starts in `onConnect`** (avoids missing the first control message while idle); the port delivers **progress** and **result** so you can keep working on the page while the popup is closed. If the popup is gone when the job finishes, you still get a **notification** (same as the context menu path when no port is attached).

**Blob download** — Prefer **`URL.createObjectURL` in the service worker** when the browser exposes it (Chrome); on **Edge**, prefer **`chrome.offscreen` / `browser.offscreen`** with [`offscreen.html`](offscreen.html) and **reason** **`BLOBS`** ([`offscreen-blobs.js`](offscreen-blobs.js)); if neither is available, the worker builds a **data** URL for **`chrome.downloads.download`** via **`FileReader`**.

**Generate progress** — The popup shows a short progress bar and stage labels from the service worker. The context menu and keyboard path use a **notification** on completion (no progress bar). The toolbar path uses the same notification if the port could not be reached (e.g. popup was closed after starting).

**Keyboard** — Optional command **`generate-mindmap`** (suggested **Ctrl+Shift+Y** / **⌘Shift+Y**). Override under `chrome://extensions` → **Keyboard shortcuts** for MindGraph.

### Debugging

All extension-side diagnostics use the **`[MindGraph]`** prefix so you can filter the console.

**Popup** (`popup.js`) — Right-click the extension toolbar icon → **Inspect popup** (or open the popup, then right-click inside it → Inspect). You will see **`console.error`** lines when **Save** verification fails, **Generate** fails, or an uncaught exception occurs.

**Service worker** (`background.js`) — Manifest V3 **service workers suspend** when idle; logs from a previous run may disappear.

1. Open `chrome://extensions`, find MindGraph, click **Service worker** (or **Inspect views: service worker**).
2. Enable **Preserve log** if you want history across reloads.
3. With that DevTools window open, trigger generate (**Generate** in the popup, **right-click → Generate mind map PNG**, or the **keyboard** shortcut) so the worker stays running long enough to log the full run.

The **service worker** console is where **`[MindGraph]`** request URLs, HTTP status, and non-PNG body previews appear. **Desktop notifications** (context menu, keyboard, or toolbar when the popup was closed) only carry a **short** success or error line; use DevTools for full detail.

There you will see request URLs, HTTP error details, `executeScript` failures, and non-PNG responses (first ~500 chars of the body for debugging).

Errors from **page** scripts (e.g. news sites) appear in that **page’s** DevTools, not in the extension consoles above.

## Security and privacy

- Privacy policy (web + browser extension): **`/privacy`** or **`/privacy-policy.html`** on your MindGraph server (e.g. `https://test.mindspringedu.com/privacy` after backend deploy, or `https://test.mindspringedu.com/privacy-policy.html` from dist only). Must be **static HTML** for Chrome Web Store (no SPA shell). Extension appendix: `#browser-extension`.
- Credentials (`mgat_` token, phone account, server preset) are stored in **`chrome.storage.local`** on this device (unencrypted, same as typical extensions). Use disk encryption, a trusted browser profile, and **revoke API tokens** on shared machines (MindGraph web app → account → API token).
- **Wireshark / network sniffing:**
  - **mg.mindspringedu.com** and **test.mindspringedu.com** use **HTTPS** — Bearer tokens and request bodies are encrypted in transit.
  - **localhost:9527** uses **HTTP** — tokens and page content sent to the API are **plaintext on the wire**. The Settings server dropdown shows a warning when local is selected; use only on a trusted dev machine.
- **SmartEdu downloads** append `accessToken=` to some CDN URLs (required by SmartEdu). Do not share download links; tokens are cleared from extension storage on 401.
- **Host permissions:** MindGraph API origins are listed explicitly in `manifest.json`. `https://*/*` and `http://*/*` remain for document extract fetches to ~25 third-party document hosts and SmartEdu CDNs (`*.smartedu.cn`, `*.cbern.com.cn`, etc.). Details: [`HOST_PERMISSIONS.md`](HOST_PERMISSIONS.md).
- **Session cookies vs mgat:** MindGraph API calls use **`credentials: 'omit'`** so a web login on the same host (e.g. test.mindspringedu.com) does not attach `access_token` / `csrf_token` to extension requests. Auth is **`Authorization: Bearer mgat_…`** + **`X-MG-Account`** only. Reload the unpacked extension after pulling this change.
- **Backend deploy:** Extension features need a current server build. See [`DEPLOY_VERIFICATION.md`](DEPLOY_VERIFICATION.md) and [`production_security_deploy.md`](../docs/architecture/production_security_deploy.md) (MindMate SSE `proxy_read_timeout` ≥ 300s; mgat CSRF exemption on POST).

## Usage

1. Open a normal **http** or **https** web page (internal `chrome://` pages and most non-web URLs are blocked; built-in PDF / `file://` are not supported).
2. Click the extension icon → **Generate**, or right-click the page → **Generate mind map PNG**, or use the optional keyboard shortcut.
3. Optional: select text first; otherwise the extension takes text from a best-effort main-content region (`[itemprop="articleBody"]`, `[role="article"]`, `article`, `main`, else `body`), capped at **32k** characters (same as the API).

The server must be reachable from your machine and Playwright must be able to render the Vue app for PNG export.

## Extract document (local download)

On supported Chinese education and document sites (~26 hosts — see [`doc-extract/REFERENCES.md`](doc-extract/REFERENCES.md)), the popup shows an **Extract document** section when the active tab matches a known host. You can also right-click the page → **Extract document (MindGraph)**.

**CNKI (知网):** Works on **`kns.cnki.net/reader/flowpdf`** online reader pages, trial-read pages, and **`kcms2` detail** pages. You must be **logged in** with download permission (institutional or personal). If a direct PDF download link is available, the extension uses it; otherwise it captures the flowpdf reader page-by-page into a PDF. Complete any CNKI captcha in the tab before extracting.

## MindMate (popup tab)

- **包含当前网页内容** — On the **first message** of a new chat, when checked, the extension runs the same **doc-extract** pipeline used for PDF download (prep, scroll, site engines), exports **markdown**, and prepends it to your question (API limit **5000** characters total).
- **CNKI / 百度文库 / 道客巴巴 / …** — Supported hosts from doc-extract: tries PDF download → text, embedded PDF.js reader text, then page text layers with auto page-flip. Allow a few seconds for **正在读取页面内容…** before sending.
- **国家智慧教育 SmartEdu** — On a `classActivity` lesson page with **包含当前网页内容**, the extension fetches lesson metadata, **downloads all PDF assets in memory** (课件 / 教学设计 / 学习任务单 — video is skipped), extracts text from each PDF, and merges them into one markdown message. You must be logged in on SmartEdu (token auto-syncs from `*.smartedu.cn` tabs).
- **Selection first** — Highlight text on the page before sending; that selection is used instead of the full document.
- **Normal web pages** — Article/main DOM → markdown (headings, lists, links).
- Reload the extension after pulling updates; open MindMate tab on the page you want to discuss.

### MindMate format coverage (包含当前网页内容)

| Source | Original formats | MindMate extraction | Notes |
|--------|-------------------|---------------------|-------|
| **Browser PDF tab** | PDF (`https://…/file.pdf`, `file:///…`) | Fetch PDF bytes → pdf.js (offscreen) | Enable **Allow access to file URLs** for local PDFs. |
| **SmartEdu** | docx / pptx (CDN serves **PDF** transcodes) | PDF text → markdown sections | Skips video (m3u8). Needs SmartEdu login token. |
| **CNKI** | PDF | PDF download or PDF.js reader text layers | Canvas fallback if no PDF URL. |
| **百度文库** | doc / pdf / ppt (varies) | **PDF API** text when available; else page text | **~8 preview pages** without VIP (capped + notice). Canvas-only preview may have **no text** — select text manually. |
| **道客巴巴 / 豆丁 / 原创力 / …** | canvas-rendered | DOM fallback → page text layers | Download saves **images→PDF**; MindMate needs **text** (partial or empty on pure canvas). |
| **360doc / 知乎 / CSDN / …** | HTML article | DOM `innerText` / markdown | Full text when page exposes copyable DOM. |
| **协作文档** (腾讯/Docs/语雀/飞书) | HTML | DOM article | Depends on page structure. |

**Not supported for automatic text:** video (m3u8), raw **docx/pptx/xlsx** binaries without PDF/text transcode, OCR from canvas images. **Selection always works** when you highlight text on the page.

**Progress stages:** preparing → scrolling (lazy pages) → collecting → assembling → downloading.

**Engines (by site):**

| Engine | Output | Typical sites |
|--------|--------|---------------|
| `canvas-pdf` | Image PDF (or ZIP fallback) | 豆丁网, 道客巴巴, 百度文库, … |
| `html2canvas-pdf` | Image PDF | 得力文库, MBA智库, 人人文库, … |
| `api-binary` | Original PDF / m3u8 URL file | 国家智慧教育 SmartEdu |
| `dom-article` | `.html` / `.txt` | 360doc, 协作文档, generic articles |

**SmartEdu:** Parses `classActivity` URLs, walks lesson `ti_items`, downloads PDFs locally. **Token is automatic** when you are logged in on any `*.smartedu.cn` tab — the extension reads `ND_UC_AUTH` from page storage (same as [tchMaterial-parser](https://github.com/happycola233/tchMaterial-parser)) and saves it to `chrome.storage.local`. A content script syncs on every SmartEdu visit; the Download tab also offers **Sync login from SmartEdu** or manual paste as fallback. Tokens expire (~7 days); log in again or tap Sync.

**Bundled vendors:** [`vendor/jspdf.umd.min.js`](vendor/jspdf.umd.min.js), [`vendor/html2canvas.min.js`](vendor/html2canvas.min.js), [`vendor/jszip.min.js`](vendor/jszip.min.js) (jsPDF 2.5, html2canvas 1.4, JSZip 3.10).

**Tests:** From repo root (requires Node.js):

```bash
cd chrome-extension && npm ci && npm test
```

Fixtures: [`tests/fixtures/doc-extract/`](../tests/fixtures/doc-extract/) (shared with file-reader SmartEdu tests).

### Server-side requirements (operators)

PNG export is a **two-stage** pipeline on the server: the **LLM** produces a mind map JSON spec, then **Playwright** opens the Vue app **`/export-render`** page and screenshots the canvas ([`routers/api/vueflow_screenshot.py`](../routers/api/vueflow_screenshot.py)).

- **`FRONTEND_URL`** — If the API process does not serve the built SPA, set this env var to a base URL where the Vue app (including `/export-render`) is reachable. If unset, the screenshot module falls back to `http://localhost:{PORT}`.
- **Playwright / Chromium** — The backend must have a working headless browser stack (see `BrowserContextManager` in the repo).
- **Latency** — End-to-end time can be **tens of seconds to a few minutes** (LLM + render). The extension aborts the PNG request after **180 seconds** and the settings verify request after **60 seconds**; align reverse proxies and load balancers with timeouts **above** those values.
- **Correlation** — The extension sends **`X-Request-Id`** (UUID) on each PNG and settings verify request; the server logs it under **`[TokenAudit] web_content_mindmap_png`** and passes it into LLM usage metadata as **`http_request_id`**.
