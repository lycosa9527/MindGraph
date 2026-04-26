/**
 * Service worker — MindGraph Chrome extension.
 * Fetches PNG from /api/web_content_mindmap_png with mgat_ + X-MG-Account headers.
 *
 * Download href: the platform does not expose a usable URL.createObjectURL for Blobs
 * in extension service workers (W3C/Chrome: use offscreen "BLOBS" or data: URLs; see
 * prepareDownloadUrlFromPngBlob). Prompt output language codes: keep in sync with
 * scripts/build_prompt_language_registry.py (_RAW).
 */

importScripts("shared-mindgraph.js");

const MAX_CHARS = MindGraphShared.MAX_PAGE_CHARS;
const FETCH_TIMEOUT_MS = MindGraphShared.FETCH_TIMEOUT_MS;

/**
 * @returns {string}
 */
function newRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `mg-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
}

const OFFSCREEN_BLOB_PAGE = "offscreen.html";
let offscreenBlobReady = false;
/** @type {Promise<void> | null} */
let offscreenBlobBootstrapping = null;

/**
 * @returns {object | null}
 */
function getOffscreenApi() {
  if (typeof chrome !== "undefined" && chrome.offscreen) {
    return chrome.offscreen;
  }
  if (globalThis.browser && globalThis.browser.offscreen) {
    return globalThis.browser.offscreen;
  }
  return null;
}

/**
 * Most Chromium service workers do not expose a working createObjectURL for Blobs; some
 * engines may, so we probe and use try/catch in prepare if the call still fails.
 * @returns {boolean}
 */
function serviceWorkerHasBlobObjectUrl() {
  const U = globalThis.URL;
  return Boolean(
    U && typeof U.createObjectURL === "function" && typeof U.revokeObjectURL === "function",
  );
}

/**
 * @param {object} offApi
 * @returns {Promise<void>}
 */
async function ensureOffscreenDocumentForBlobs(offApi) {
  if (offscreenBlobReady) {
    return;
  }
  if (offscreenBlobBootstrapping) {
    return offscreenBlobBootstrapping;
  }
  const offscreenUrl = chrome.runtime.getURL(OFFSCREEN_BLOB_PAGE);
  offscreenBlobBootstrapping = (async () => {
    if (chrome.runtime.getContexts) {
      const existing = await chrome.runtime.getContexts({
        contextTypes: ["OFFSCREEN_DOCUMENT"],
        documentUrls: [offscreenUrl],
      });
      if (existing && existing.length > 0) {
        offscreenBlobReady = true;
        return;
      }
    }
    try {
      await offApi.createDocument({
        url: OFFSCREEN_BLOB_PAGE,
        reasons: ["BLOBS"],
        justification:
          "Offscreen (reason BLOBS) provides URL.createObjectURL for Blobs in Chrome MV3; this extension uses it when the service worker does not (see prepareDownloadUrlFromPngBlob).",
      });
    } catch (e) {
      if (chrome.runtime.getContexts) {
        throw e;
      }
      const text = (e && e.message) || String(e);
      if (!/only a single|already exists|offscreen|OFFSCREEN|single offscreen/i.test(text)) {
        throw e;
      }
    }
    offscreenBlobReady = true;
  })();
  try {
    await offscreenBlobBootstrapping;
  } finally {
    offscreenBlobBootstrapping = null;
  }
}

/**
 * @param {Blob} blob
 * @returns {Promise<string>}
 */
function blobToDataUrlInServiceWorker(blob) {
  return new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => {
      resolve(String(fr.result));
    };
    fr.onerror = () => {
      reject(fr.error || new Error("FileReader"));
    };
    fr.readAsDataURL(blob);
  });
}

/**
 * 1) Rare: blob: URL in the service worker if the engine exposes a working createObjectURL.
 * 2) Preferred on Chrome: chrome.offscreen / browser.offscreen + offscreen.html (BLOBS).
 * 3) Portable: data: URL via FileReader (e.g. Chromium forks with no `chrome.offscreen`).
 * @param {Blob} blob
 * @returns {Promise<{ href: string, revokeMode: "sw" | "offscreen" | "none" }>}
 */
async function prepareDownloadUrlFromPngBlob(blob) {
  if (serviceWorkerHasBlobObjectUrl()) {
    try {
      return { href: globalThis.URL.createObjectURL(blob), revokeMode: "sw" };
    } catch (e) {
      console.warn("[MindGraph] URL.createObjectURL in service worker failed, using next path", e);
    }
  }
  const offApi = getOffscreenApi();
  if (offApi) {
    await ensureOffscreenDocumentForBlobs(offApi);
    const href = await createBlobObjectUrlInOffscreen(blob);
    return { href: href, revokeMode: "offscreen" };
  }
  return { href: await blobToDataUrlInServiceWorker(blob), revokeMode: "none" };
}

/**
 * chrome.runtime.sendMessage uses JSON serialization, so Blob objects are lost in transit.
 * Convert to base64 first so the payload is JSON-safe; the offscreen document reconstructs
 * the Blob from base64 + mimeType before calling URL.createObjectURL.
 * @param {Blob} blob
 * @returns {Promise<string>}
 */
async function createBlobObjectUrlInOffscreen(blob) {
  const arrayBuffer = await blob.arrayBuffer();
  const bytes = new Uint8Array(arrayBuffer);
  // Process in 8 KB chunks: String.fromCharCode.apply converts a typed-array
  // subarray with a single native call, avoiding O(n²) byte-by-byte concatenation.
  const chunkSize = 8192;
  let binary = "";
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
  }
  const base64 = btoa(binary);
  const mimeType = blob.type || "image/png";
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "MINDGRAPH_BLOB_URL", base64, mimeType }, (response) => {
      const last = chrome.runtime.lastError;
      if (last) {
        reject(new Error(last.message));
        return;
      }
      if (response && response.ok && typeof response.href === "string") {
        resolve(response.href);
        return;
      }
      reject(new Error((response && response.error) || "BLOB_URL_FAILED"));
    });
  });
}

/**
 * @param {string} href
 * @param {"sw" | "offscreen" | "none"} revokeMode
 */
function scheduleDownloadUrlRevoke(href, revokeMode) {
  if (revokeMode === "none") {
    return;
  }
  if (revokeMode === "sw") {
    setTimeout(() => {
      try {
        if (globalThis.URL && globalThis.URL.revokeObjectURL) {
          globalThis.URL.revokeObjectURL(href);
        }
      } catch {
        /* ignore */
      }
    }, 60_000);
    return;
  }
  setTimeout(() => {
    chrome.runtime.sendMessage({ type: "MINDGRAPH_REVOKE_BLOB_URL", href: href }, () => {
      void chrome.runtime.lastError;
    });
  }, 60_000);
}

/** @type {readonly string[]} */
const PROMPT_OUTPUT_LANGUAGE_CODES = Object.freeze([
  "zh",
  "zh-hant",
  "en",
  "fr",
  "es",
  "ar",
  "ru",
  "pt",
  "de",
  "it",
  "nl",
  "da",
  "ga",
  "cy",
  "fi",
  "is",
  "sv",
  "nn",
  "nb",
  "no",
  "ja",
  "ko",
  "vi",
  "th",
  "id",
  "ms",
  "my",
  "tl",
  "km",
  "lo",
  "hi",
  "bn",
  "ur",
  "ne",
  "he",
  "tr",
  "fa",
  "pl",
  "uk",
  "cs",
  "ro",
  "bg",
  "sk",
  "hu",
  "sl",
  "lv",
  "et",
  "lt",
  "be",
  "el",
  "hr",
  "mk",
  "mt",
  "sr",
  "bs",
  "ka",
  "hy",
  "az",
  "kk",
  "uz",
  "tg",
  "sw",
  "af",
  "yue",
  "lb",
  "li",
  "ca",
  "gl",
  "ast",
  "eu",
  "oc",
  "vec",
  "sc",
  "scn",
  "fur",
  "lmo",
  "lij",
  "fo",
  "sq",
  "szl",
  "ba",
  "tt",
  "acm",
  "ars",
  "arz",
  "apc",
  "acq",
  "prs",
  "aeb",
  "ary",
  "kea",
  "tpi",
  "ydd",
  "sd",
  "si",
  "te",
  "pa",
  "ta",
  "gu",
  "ml",
  "mr",
  "mag",
  "or",
  "awa",
  "mai",
  "as",
  "hne",
  "bho",
  "min",
  "ban",
  "jv",
  "bjn",
  "sun",
  "ceb",
  "pag",
  "ilo",
  "war",
  "ht",
  "pap",
  "br",
  "gd",
  "gv",
  "kw",
  "fy",
  "kn",
  "kok",
  "mni",
  "sat",
  "bo",
  "ug",
  "mn",
  "am",
  "so",
  "zu",
  "xh",
  "st",
  "ts",
  "tn",
  "ve",
  "ss",
  "nr",
  "nso",
  "qu",
  "gn",
  "ay",
  "wo",
  "ha",
  "yo",
  "ig",
]);

/**
 * @returns {Promise<string>}
 */
async function getResolvedLanguageForCapture() {
  const { uiLanguage } = await chrome.storage.local.get("uiLanguage");
  return MindGraphShared.resolvePromptLanguageFromUiMode(
    uiLanguage,
    chrome.i18n.getUILanguage(),
    Array.from(PROMPT_OUTPUT_LANGUAGE_CODES),
  );
}

function normalizeBaseUrl(url) {
  return MindGraphShared.normalizeBaseUrl(url);
}

function sanitizeFilename(title) {
  return MindGraphShared.sanitizeFilename(title);
}

/**
 * @param {string} message
 */
function notifyUser(message) {
  chrome.notifications.create({
    type: "basic",
    iconUrl: "icons/icon128.png",
    title: chrome.i18n.getMessage("notificationTitle"),
    message,
  });
}

/**
 * @param {chrome.runtime.Port | undefined} port
 * @param {string} stage
 */
function postProgress(port, stage) {
  if (!port) {
    return;
  }
  try {
    port.postMessage({ type: "progress", stage });
  } catch {
    /* Popup may have closed */
  }
}

/**
 * @param {number} tabId
 * @param {{ progressPort?: chrome.runtime.Port, fromContextMenu?: boolean, fromPopup?: boolean }} options
 */
async function runGenerateMindmap(tabId, options) {
  const { progressPort, fromContextMenu, fromPopup } = options;

  let finished = false;
  const finish = (result) => {
    if (finished) {
      return;
    }
    finished = true;
    let delivered = false;
    if (progressPort) {
      try {
        progressPort.postMessage({ type: "result", ...result });
        delivered = true;
      } catch {
        /* Port may be gone if the popup was closed. */
      }
    }
    if (fromContextMenu) {
      if (result.ok) {
        notifyUser(chrome.i18n.getMessage("statusDownloadStarted"));
      } else {
        notifyUser(result.error || chrome.i18n.getMessage("errFailed"));
      }
    } else if (fromPopup && !delivered) {
      if (result.ok) {
        notifyUser(chrome.i18n.getMessage("statusDownloadStarted"));
      } else {
        notifyUser(result.error || chrome.i18n.getMessage("errFailed"));
      }
    }
  };

  let apiUrl = "";
  try {
    const settings = await chrome.storage.local.get([
      "baseUrl",
      "account",
      "token",
      "saveAs",
      "pngWidth",
      "pngHeight",
    ]);
    const baseUrl = normalizeBaseUrl(
      settings.baseUrl || MindGraphShared.DEFAULT_MINDGRAPH_BASE_URL,
    );
    const account = (settings.account || "").trim();
    const token = (settings.token || "").trim();
    if (!baseUrl || !account || !token) {
      finish({ ok: false, error: chrome.i18n.getMessage("errSettingsIncomplete") });
      return;
    }

    const tab = await chrome.tabs.get(tabId);
    if (MindGraphShared.isRestrictedTabUrl(tab.url)) {
      console.error("[MindGraph] restricted tab URL", tab.url);
      finish({ ok: false, error: chrome.i18n.getMessage("errRestrictedPage") });
      return;
    }

    postProgress(progressPort, "reading");
    const resolvedLang = await getResolvedLanguageForCapture();
    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId },
        func: capturePageContent,
        args: [MAX_CHARS, PROMPT_OUTPUT_LANGUAGE_CODES, resolvedLang],
      });
    } catch (scriptErr) {
      console.error("[MindGraph] executeScript failed", scriptErr);
      finish({
        ok: false,
        error: scriptErr?.message || String(scriptErr),
      });
      return;
    }

    const payload = results?.[0]?.result;
    if (!payload || typeof payload.page_content !== "string" || !payload.page_content.trim()) {
      finish({ ok: false, error: chrome.i18n.getMessage("errNoPageText") });
      return;
    }

    const pngApiUrl = `${baseUrl}/api/web_content_mindmap_png`;
    apiUrl = pngApiUrl;
    console.info("[MindGraph] POST", pngApiUrl);
    const sizeOpts = {
      pngWidth: typeof settings.pngWidth === "number" ? settings.pngWidth : undefined,
      pngHeight: typeof settings.pngHeight === "number" ? settings.pngHeight : undefined,
    };
    const body = MindGraphShared.buildPngRequestBody(payload, sizeOpts);

    postProgress(progressPort, "sending");
    const requestId = newRequestId();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(pngApiUrl, {
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "X-MG-Account": account,
          "X-MG-Client": "chrome-extension",
          "X-Request-Id": requestId,
        },
        body: JSON.stringify(body),
      });
    } catch (fetchErr) {
      clearTimeout(timeoutId);
      if (fetchErr && fetchErr.name === "AbortError") {
        console.error("[MindGraph] fetch timeout", FETCH_TIMEOUT_MS, "ms", pngApiUrl, requestId);
        finish({ ok: false, error: chrome.i18n.getMessage("errFetchTimeout") });
        return;
      }
      throw fetchErr;
    }
    clearTimeout(timeoutId);
    await Promise.resolve();
    postProgress(progressPort, "serverProcessing");

    if (!res.ok) {
      if (res.status === 429) {
        finish({ ok: false, error: chrome.i18n.getMessage("errRateLimit") });
        return;
      }
      if (res.status === 503) {
        finish({ ok: false, error: chrome.i18n.getMessage("errServiceUnavailable") });
        return;
      }
      const detail = await MindGraphShared.parseErrorDetailFromResponse(res);
      console.error("[MindGraph] API HTTP error", res.status, pngApiUrl, detail);
      finish({
        ok: false,
        error: chrome.i18n.getMessage("errApi", [String(res.status), detail]),
      });
      return;
    }

    const contentType = (res.headers.get("Content-Type") || "").toLowerCase();
    if (!contentType.includes("image/png")) {
      let bodyPreview = "";
      try {
        bodyPreview = (await res.text()).slice(0, 500);
      } catch {
        bodyPreview = "";
      }
      console.error("[MindGraph] expected image/png, got", contentType, bodyPreview || "(empty body)");
      finish({ ok: false, error: chrome.i18n.getMessage("errNotPng") });
      return;
    }

    const savedDiagramId = (res.headers.get("X-MG-Diagram-Id") || "").trim() || null;
    const diagramUrl = savedDiagramId
      ? `${baseUrl}/canvas?diagramId=${encodeURIComponent(savedDiagramId)}`
      : null;
    const saveError = (res.headers.get("X-MG-Save-Error") || "").trim() || null;

    postProgress(progressPort, "receiving");
    const blob = await res.blob();
    let prepared;
    try {
      prepared = await prepareDownloadUrlFromPngBlob(blob);
    } catch (e) {
      console.error("[MindGraph] prepare download url", e);
      finish({ ok: false, error: chrome.i18n.getMessage("errDownloadPrepare") });
      return;
    }
    const { href: downloadHref, revokeMode } = prepared;
    const filename = sanitizeFilename(payload.page_title);
    const saveAs = Boolean(settings.saveAs);
    postProgress(progressPort, "saving");
    try {
      await chrome.downloads.download({
        url: downloadHref,
        filename,
        saveAs,
      });
    } catch (dlErr) {
      console.error("[MindGraph] downloads.download", dlErr);
      finish({ ok: false, error: dlErr?.message || String(dlErr) });
      return;
    }
    scheduleDownloadUrlRevoke(downloadHref, revokeMode);
    finish({
      ok: true,
      ...(diagramUrl ? { diagramUrl } : {}),
      ...(saveError ? { saveError } : {}),
    });
  } catch (err) {
    console.error("[MindGraph] runGenerateMindmap", apiUrl || "(before URL)", err);
    finish({ ok: false, error: err?.message || String(err) });
  }
}

function ensureContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "mindgraph-generate",
      title: chrome.i18n.getMessage("contextMenuGenerate"),
      contexts: ["page"],
    });
  });
}

chrome.runtime.onInstalled.addListener(ensureContextMenu);

/**
 * PING: wake MV3 service worker (see popup for optional wake before actions).
 * PNG generation runs in this worker for toolbar, context menu, and keyboard
 * (popup connects with a port for progress; closing the popup does not cancel).
 */
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "PING") {
    setTimeout(() => {
      try {
        sendResponse({ ok: true });
      } catch {
        /* sendResponse may throw if channel already closed */
      }
    }, 0);
    return true;
  }
  return false;
});

/**
 * Toolbar popup: start as soon as the port connects. Encoding tabId in `port.name`
 * avoids a race where the service worker idles or loses the first `postMessage` before
 * `onMessage` runs, which looked like a brief progress flash and no download.
 * @param {chrome.runtime.Port} port
 */
function onMindmapGenerateConnect(port) {
  const base =
    typeof MindGraphShared !== "undefined" && MindGraphShared && MindGraphShared.MINDMAP_GENERATE_PORT
      ? MindGraphShared.MINDMAP_GENERATE_PORT
      : "mindmap-generate";
  const prefix = `${base}-`;
  if (port.name.startsWith(prefix)) {
    const rest = port.name.slice(prefix.length);
    if (!/^\d+$/.test(rest)) {
      return;
    }
    const tabId = parseInt(rest, 10);
    if (tabId < 1) {
      return;
    }
    void runGenerateMindmap(tabId, {
      progressPort: port,
      fromContextMenu: false,
      fromPopup: true,
    });
    return;
  }
  if (port.name !== base) {
    return;
  }
  port.onMessage.addListener((msg) => {
    if (!msg || msg.type !== "start" || typeof msg.tabId !== "number") {
      return;
    }
    void runGenerateMindmap(msg.tabId, {
      progressPort: port,
      fromContextMenu: false,
      fromPopup: true,
    });
  });
}

chrome.runtime.onConnect.addListener(onMindmapGenerateConnect);

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "mindgraph-generate" || !tab?.id) {
    return;
  }
  runGenerateMindmap(tab.id, { fromContextMenu: true });
});

chrome.commands.onCommand.addListener((command) => {
  if (command !== "generate-mindmap") {
    return;
  }
  void chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const tab = tabs[0];
    if (!tab?.id) {
      return;
    }
    runGenerateMindmap(tab.id, { fromContextMenu: true });
  });
});

/**
 * Injected into the page — returns serializable capture payload.
 * Page text only; `language` comes from extension setting (same as UI language).
 * @param {number} maxChars
 * @param {string[]} allowedCodes
 * @param {string} resolvedLanguage
 */
function capturePageContent(maxChars, allowedCodes, resolvedLanguage) {
  const allowedSet = new Set(allowedCodes);
  const language = allowedSet.has(resolvedLanguage) ? resolvedLanguage : "zh";

  const sel = window.getSelection();
  let text = "";
  if (sel && sel.toString().trim()) {
    text = sel.toString();
  } else {
    const itempropBody = document.querySelector('[itemprop="articleBody"]');
    const roleArticle = document.querySelector('[role="article"]');
    const article = document.querySelector("article");
    const main = document.querySelector("main,[role='main']");
    const root = itempropBody || roleArticle || article || main || document.body;
    text = root ? root.innerText || "" : "";
  }
  if (text.length > maxChars) {
    text = text.slice(0, maxChars);
  }

  return {
    page_content: text,
    content_format: "text/plain",
    page_title: document.title || "",
    page_url: window.location.href || "",
    language,
  };
}
