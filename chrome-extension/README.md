# MindGraph Chrome extension (development)

This folder is a **Manifest V3** extension. It captures text from the active tab and calls MindGraph **`POST /api/web_content_mindmap_png`** with your **`mgat_`** token and **`X-MG-Account`** (phone), then downloads the PNG.

## Icons

Toolbar and store icons match the **web app favicon** ([`frontend/public/favicon.svg`](../frontend/public/favicon.svg)): stone-900 rounded square (`#1c1917`) with a white **M**.

PNG sizes are generated for Chrome from that design. Regenerate after changing the SVG:

`python chrome-extension/scripts/generate_icons.py`

## Language (i18n) and mind map output

Locale strings live in **`chrome-extension/_locales/`** (`en`, `zh_CN`, `zh_TW`). The manifest `default_locale` is **`en`**.

- **Settings → Language** — One control (stored as `uiLanguage`: Match browser, English, 简体, 正體). It sets **both** the popup’s effective UI strings (optional override by loading a locale’s `messages.json`) and the **`language`** field sent to **`POST /api/web_content_mindmap_png`**, resolved in the service worker to match the server’s prompt registry ([`scripts/build_prompt_language_registry.py`](../scripts/build_prompt_language_registry.py); the allowed code list is embedded in [`background.js`](background.js) as `PROMPT_OUTPUT_LANGUAGE_CODES`). Page text language and diagram output language are **independent** (e.g. English article + Chinese map labels).

- **Match browser** — Uses `chrome.i18n.getMessage` / UI language to pick copy and, for the API, maps the browser UI language to a registry code in [`shared-mindgraph.js`](shared-mindgraph.js) (`resolvePromptLanguageFromUiMode`).

## Load unpacked (Chrome)

1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked**.
4. Select this **`chrome-extension`** directory (the folder that contains `manifest.json`).
5. After editing files, click **Reload** on the extension card.

## Settings

- **Base URL** — Default **`https://mg.mindspringedu.com`** when nothing is stored; you can change and save any MindGraph `https` (or `http`) origin. No trailing slash required.
- **Account (phone)** — Same value as **`X-MG-Account`** for API tokens.
- **API token** — `mgat_…` from the app (**账户信息** → **API Token**). After save, a line under the token shows **valid-until** from **`GET /api/auth/api-token`** (metadata only; same auth headers as `/me`).

The extension sends **`X-MG-Client: chrome-extension`** on mgat requests so the server can label **`[TokenAudit]`** log lines.

**Save** calls **`GET /api/auth/me`** to verify the token, then persists settings. **Credentials are written to `chrome.storage.local` only after that request succeeds**. Network failures show an error and nothing is saved.

**Advanced**

- **PNG width / height** — Optional; if set, sent on **`POST /api/web_content_mindmap_png`** (server defaults apply when empty).
- **Ask where to save** — Optional save dialog for each download (`chrome.downloads` with `saveAs`).

**Code layout** — [`shared-mindgraph.js`](shared-mindgraph.js) is loaded by the service worker (`importScripts`) and the popup: shared URL helpers, request body, error parsing, and default base URL. The **long `fetch` (PNG) and `downloads.download` run in the service worker** for toolbar, context menu, and keyboard; the **popup** opens a `runtime.connect` port named **`mindmap-generate-<tabId>`** so the worker **starts in `onConnect`** (avoids missing the first control message while idle); the port delivers **progress** and **result** so you can keep working on the page while the popup is closed. If the popup is gone when the job finishes, you still get a **notification** (same as the context menu path when no port is attached).

**Blob download** — Prefer **`URL.createObjectURL` in the service worker** when the browser exposes it; else **`chrome.offscreen` or `browser.offscreen`** with [`offscreen.html`](offscreen.html) and **reason** **`BLOBS`** ([`chrome.offscreen`](https://developer.chrome.com/docs/extensions/reference/api/offscreen)); if neither is available, the worker builds a **data** URL for **`chrome.downloads.download`** via **`FileReader`**.

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

- Credentials are stored in **`chrome.storage.local`** on this device (same as typical extensions). Use only on a machine and profile you trust.
- Broad **`http*://*/*`** host permissions are required so you can point the extension at your own MindGraph deployment. Enter only origins you intend to use.

## Usage

1. Open a normal **http** or **https** web page (internal `chrome://` pages and most non-web URLs are blocked; built-in PDF / `file://` are not supported).
2. Click the extension icon → **Generate**, or right-click the page → **Generate mind map PNG**, or use the optional keyboard shortcut.
3. Optional: select text first; otherwise the extension takes text from a best-effort main-content region (`[itemprop="articleBody"]`, `[role="article"]`, `article`, `main`, else `body`), capped at **32k** characters (same as the API).

The server must be reachable from your machine and Playwright must be able to render the Vue app for PNG export.

### Server-side requirements (operators)

PNG export is a **two-stage** pipeline on the server: the **LLM** produces a mind map JSON spec, then **Playwright** opens the Vue app **`/export-render`** page and screenshots the canvas ([`routers/api/vueflow_screenshot.py`](../routers/api/vueflow_screenshot.py)).

- **`FRONTEND_URL`** — If the API process does not serve the built SPA, set this env var to a base URL where the Vue app (including `/export-render`) is reachable. If unset, the screenshot module falls back to `http://localhost:{PORT}`.
- **Playwright / Chromium** — The backend must have a working headless browser stack (see `BrowserContextManager` in the repo).
- **Latency** — End-to-end time can be **tens of seconds to a few minutes** (LLM + render). The extension aborts the PNG request after **180 seconds** and the settings verify request after **60 seconds**; align reverse proxies and load balancers with timeouts **above** those values.
- **Correlation** — The extension sends **`X-Request-Id`** (UUID) on each PNG and settings verify request; the server logs it under **`[TokenAudit] web_content_mindmap_png`** and passes it into LLM usage metadata as **`http_request_id`**.
