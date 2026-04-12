# MindGraph Chrome extension (development)

This folder is a **Manifest V3** extension. It captures text from the active tab and calls MindGraph **`POST /api/web_content_mindmap_png`** with your **`mgat_`** token and **`X-MG-Account`** (phone), then downloads the PNG.

## Icons

Toolbar and store icons match the **web app favicon** ([`frontend/public/favicon.svg`](../frontend/public/favicon.svg)): stone-900 rounded square (`#1c1917`) with a white **M**.

PNG sizes are generated for Chrome from that design. Regenerate after changing the SVG:

`python chrome-extension/scripts/generate_icons.py`

## Language (i18n)

Chrome picks the locale from **`chrome-extension/_locales/`**:

- **`en`** — default (`default_locale` in `manifest.json`).
- **`zh_CN`** — Simplified Chinese.
- **`zh_TW`** — Traditional Chinese.

The popup and toolbar use the same language as the browser UI when a matching locale exists. Strings live in **`messages.json`** per locale; manifest name and description use `__MSG_*__` keys.

Page language sent to the API is derived from the document `lang` attribute and `navigator.language`, normalized to codes supported by the same registry as the server ([`scripts/build_prompt_language_registry.py`](../scripts/build_prompt_language_registry.py)). The extension embeds that code list in **`background.js`** (`PROMPT_OUTPUT_LANGUAGE_CODES`); if you add languages in the script, update the array to match.

## Load unpacked (Chrome)

1. Open `chrome://extensions`.
2. Turn on **Developer mode** (top right).
3. Click **Load unpacked**.
4. Select this **`chrome-extension`** directory (the folder that contains `manifest.json`).
5. After editing files, click **Reload** on the extension card.

## Settings

- **Base URL** — MindGraph origin only, e.g. `https://test.mindspringedu.com` (no trailing slash required). Use a host you trust; the extension can call any `http`/`https` origin you configure.
- **Account (phone)** — Same value as **`X-MG-Account`** for API tokens.
- **API token** — `mgat_…` from the app (**账户信息** → **API Token**).

**Save** first calls **`GET /api/auth/me`** with `Authorization: Bearer <token>` and **`X-MG-Account`** (same headers as the web app). The server resolves the user via `get_current_user`, which validates `mgat_` tokens. Only if that succeeds are credentials written to `chrome.storage.local`.

**Advanced**

- **Ask where to save** — Uses the browser save dialog for each download (`chrome.downloads` with `saveAs`).

**Generate progress** — The popup opens a long-lived port to the service worker and shows a short progress bar plus stage labels (read page → generate → save download). The context menu path does not use the popup, so it only shows a desktop notification on completion.

## Security and privacy

- Credentials are stored in **`chrome.storage.local`** on this device (same as typical extensions). Use only on a machine and profile you trust.
- Broad **`http*://*/*`** host permissions are required so you can point the extension at your own MindGraph deployment. Enter only origins you intend to use.

## Usage

1. Open a normal **http** or **https** web page (internal `chrome://` pages and most non-web URLs are blocked).
2. Click the extension icon → **Generate**, or right-click the page → **Generate mind map PNG**.
3. Optional: select text first; otherwise the extension uses the main article / `body` text (capped at 32k characters).

The server must be reachable from your machine and Playwright must be able to render the Vue app for PNG export.
