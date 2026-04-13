/**
 * Service worker — MindGraph Chrome extension.
 * Fetches PNG from /api/web_content_mindmap_png with mgat_ + X-MG-Account headers.
 *
 * Prompt output language codes: keep in sync with scripts/build_prompt_language_registry.py (_RAW).
 */

const MAX_CHARS = 32000;

/** Abort fetch if server does not respond (LLM + Playwright can exceed 60s). */
const FETCH_TIMEOUT_MS = 180000;

/**
 * @returns {string}
 */
function newRequestId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `mg-${Date.now()}-${Math.random().toString(36).slice(2, 12)}`;
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

function normalizeBaseUrl(url) {
  const trimmed = (url || "").trim().replace(/\/+$/, "");
  return trimmed;
}

function sanitizeFilename(title) {
  const base = (title || "mindgraph").replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").slice(0, 80);
  return base.endsWith(".png") ? base : `${base}.png`;
}

/**
 * @param {Response} res
 * @returns {Promise<string>}
 */
async function parseErrorDetail(res) {
  const text = await res.text();
  let detail = text || res.statusText;
  if (text) {
    try {
      const errJson = JSON.parse(text);
      if (errJson && (errJson.detail !== undefined || errJson.message !== undefined)) {
        const raw = errJson.detail !== undefined ? errJson.detail : errJson.message;
        detail = typeof raw === "string" ? raw : JSON.stringify(raw);
      }
    } catch {
      detail = text.slice(0, 500);
    }
  }
  return detail;
}

/**
 * @param {string | undefined} url
 * @returns {boolean}
 */
function isRestrictedTabUrl(url) {
  if (!url || typeof url !== "string") {
    return true;
  }
  try {
    const parsed = new URL(url);
    return parsed.protocol !== "http:" && parsed.protocol !== "https:";
  } catch {
    return true;
  }
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
 * @param {{ progressPort?: chrome.runtime.Port, fromContextMenu?: boolean }} options
 */
async function runGenerateMindmap(tabId, options) {
  const { progressPort, fromContextMenu } = options;

  let finished = false;
  const finish = (result) => {
    if (finished) {
      return;
    }
    finished = true;
    if (progressPort) {
      try {
        progressPort.postMessage({ type: "result", ...result });
      } catch {
        /* ignore */
      }
    }
    if (fromContextMenu) {
      if (result.ok) {
        notifyUser(chrome.i18n.getMessage("statusDownloadStarted"));
      } else {
        notifyUser(result.error || chrome.i18n.getMessage("errFailed"));
      }
    }
  };

  let apiUrl = "";
  try {
    const settings = await chrome.storage.local.get(["baseUrl", "account", "token", "saveAs"]);
    const baseUrl = normalizeBaseUrl(settings.baseUrl);
    const account = (settings.account || "").trim();
    const token = (settings.token || "").trim();
    if (!baseUrl || !account || !token) {
      finish({ ok: false, error: chrome.i18n.getMessage("errSettingsIncomplete") });
      return;
    }

    const tab = await chrome.tabs.get(tabId);
    if (isRestrictedTabUrl(tab.url)) {
      console.error("[MindGraph] restricted tab URL", tab.url);
      finish({ ok: false, error: chrome.i18n.getMessage("errRestrictedPage") });
      return;
    }

    postProgress(progressPort, "reading");
    let results;
    try {
      results = await chrome.scripting.executeScript({
        target: { tabId },
        func: capturePageContent,
        args: [MAX_CHARS, PROMPT_OUTPUT_LANGUAGE_CODES],
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

    const url = `${baseUrl}/api/web_content_mindmap_png`;
    apiUrl = url;
    console.info("[MindGraph] POST", url);
    const body = {
      page_content: payload.page_content,
      content_format: payload.content_format || "text/plain",
      page_title: payload.page_title || null,
      page_url: payload.page_url || null,
      language: payload.language || "zh",
    };

    postProgress(progressPort, "sending");
    const requestId = newRequestId();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(url, {
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
        console.error("[MindGraph] fetch timeout", FETCH_TIMEOUT_MS, "ms", url, requestId);
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
      const detail = await parseErrorDetail(res);
      console.error("[MindGraph] API HTTP error", res.status, url, detail);
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

    postProgress(progressPort, "receiving");
    const blob = await res.blob();
    const blobUrl = URL.createObjectURL(blob);
    const filename = sanitizeFilename(payload.page_title);
    const saveAs = Boolean(settings.saveAs);
    postProgress(progressPort, "saving");
    await chrome.downloads.download({
      url: blobUrl,
      filename,
      saveAs,
    });
    setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);

    finish({ ok: true });
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
 * PING: wake MV3 service worker (see popup).
 * CAPTURE_PAGE_FOR_MINDMAP: short executeScript only; long fetch runs in popup to avoid
 * holding a runtime port across multi-minute requests.
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
  if (msg && msg.type === "CAPTURE_PAGE_FOR_MINDMAP" && typeof msg.tabId === "number") {
    void (async () => {
      try {
        const tab = await chrome.tabs.get(msg.tabId);
        if (isRestrictedTabUrl(tab.url)) {
          console.error("[MindGraph] restricted tab URL", tab.url);
          sendResponse({
            ok: false,
            error: chrome.i18n.getMessage("errRestrictedPage"),
          });
          return;
        }
        const results = await chrome.scripting.executeScript({
          target: { tabId: msg.tabId },
          func: capturePageContent,
          args: [MAX_CHARS, PROMPT_OUTPUT_LANGUAGE_CODES],
        });
        const payload = results?.[0]?.result;
        if (!payload || typeof payload.page_content !== "string" || !payload.page_content.trim()) {
          sendResponse({
            ok: false,
            error: chrome.i18n.getMessage("errNoPageText"),
          });
          return;
        }
        sendResponse({ ok: true, payload });
      } catch (e) {
        console.error("[MindGraph] CAPTURE_PAGE_FOR_MINDMAP", e);
        sendResponse({
          ok: false,
          error: e?.message || String(e),
        });
      }
    })();
    return true;
  }
  return false;
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "mindgraph-generate" || !tab?.id) {
    return;
  }
  runGenerateMindmap(tab.id, { fromContextMenu: true });
});

/**
 * Injected into the page — returns serializable capture payload.
 * @param {number} maxChars
 * @param {string[]} allowedCodes
 */
function capturePageContent(maxChars, allowedCodes) {
  const allowedSet = new Set(allowedCodes);

  /**
   * @param {string | undefined} raw
   * @returns {string | null}
   */
  const tryNormalize = (raw) => {
    if (!raw || typeof raw !== "string") {
      return null;
    }
    const s = raw.trim().toLowerCase().replace(/_/g, "-");
    if (!s) {
      return null;
    }
    if (s === "zh-tw" || s === "zh-hk" || s === "zh-hant" || s === "zh-mo") {
      return allowedSet.has("zh-hant") ? "zh-hant" : "zh";
    }
    if (s === "zh-cn" || s === "zh-hans" || s === "zh-sg") {
      return "zh";
    }
    if (allowedSet.has(s)) {
      return s;
    }
    const primary = s.split("-")[0];
    if (allowedSet.has(primary)) {
      return primary;
    }
    if (s.length >= 2) {
      const two = s.slice(0, 2);
      if (allowedSet.has(two)) {
        return two;
      }
    }
    return null;
  };

  const sel = window.getSelection();
  let text = "";
  if (sel && sel.toString().trim()) {
    text = sel.toString();
  } else {
    const article = document.querySelector("article");
    const main = document.querySelector("main,[role='main']");
    const root = article || main || document.body;
    text = root ? root.innerText || "" : "";
  }
  if (text.length > maxChars) {
    text = text.slice(0, maxChars);
  }
  const docLang = document.documentElement.getAttribute("lang") || "";
  const fallbackLang = (docLang || navigator.language || "").toLowerCase().startsWith("en") ? "en" : "zh";
  const language =
    tryNormalize(docLang) || tryNormalize(navigator.language) || fallbackLang;

  return {
    page_content: text,
    content_format: "text/plain",
    page_title: document.title || "",
    page_url: window.location.href || "",
    language,
  };
}
