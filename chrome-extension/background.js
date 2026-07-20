/**
 * Service worker — MindGraph browser extension (Chrome & Edge).
 * Fetches PNG from /api/web_content_mindmap_png with mgat_ + X-MG-Account headers.
 * Page capture uses doc-extract/page-content-capture.js (file-first + shared DOM text).
 *
 * Download href: offscreen-blobs.js (offscreen BLOBS, data URL fallback).
 * Prompt output language codes: keep in sync with scripts/build_prompt_language_registry.py (_RAW).
 */

importScripts("shared-mindgraph.js");
importScripts("extension-storage.js");
importScripts("extension-security.js");
importScripts("extension-jobs.js");
importScripts("offscreen-blobs.js");
importScripts("vendor/jspdf.umd.min.js");
importScripts("vendor/jszip.min.js");
importScripts("doc-extract/smartedu/models.js");
importScripts("doc-extract/smartedu/url-parser.js");
importScripts("doc-extract/smartedu/token.js");
importScripts("doc-extract/smartedu/metadata.js");
importScripts("doc-extract/smartedu/downloader.js");
importScripts("doc-extract/hosts.js");
importScripts("doc-extract/hosts/wenku.js");
importScripts("doc-extract/wenku/preview-notice.js");
importScripts("doc-extract/hosts/docin.js");
importScripts("doc-extract/hosts/smartedu.js");
importScripts("doc-extract/prepare-download.js");
importScripts("doc-extract/engines/canvas-pdf.js");
importScripts("doc-extract/engines/html2canvas-pdf.js");
importScripts("doc-extract/engines/dom-article.js");
importScripts("doc-extract/engines/api-binary.js");
importScripts("doc-extract/user-messages.js");
importScripts("doc-extract/cnki/url-parser.js");
importScripts("doc-extract/engines/cnki.js");
importScripts("doc-extract/extract-core.js");
importScripts("mindmate-capture-debug.js");
importScripts("mindmate-capture-progress.js");
importScripts("doc-extract/extract-to-markdown.js");
importScripts("doc-extract/page-content-capture.js");
importScripts("doc-extract/text/blob-to-text.js");
importScripts("doc-extract/text/markdown-capture-policy.js");
importScripts("doc-extract/text/browser-pdf-fetch.js");
importScripts("doc-extract/text/pdf-extract-offscreen.js");
importScripts("doc-extract/smartedu/markdown-extract.js");
importScripts("mindmate-capture.js");

const MAX_CHARS = MindGraphShared.MAX_PAGE_CHARS;
const FETCH_TIMEOUT_MS = MindGraphShared.FETCH_TIMEOUT_MS;

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
 * @param {string | undefined} error
 * @returns {string}
 */
function resolveNotifyError(error) {
  if (!error) {
    return chrome.i18n.getMessage("errFailed");
  }
  if (error.startsWith("err")) {
    return chrome.i18n.getMessage(error) || error;
  }
  return error;
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
        notifyUser(resolveNotifyError(result.error));
      }
    } else if (fromPopup && !delivered) {
      if (result.ok) {
        notifyUser(chrome.i18n.getMessage("statusDownloadStarted"));
      } else {
        notifyUser(resolveNotifyError(result.error));
      }
    }
  };

  let apiUrl = "";
  const lockOutcome = await MindGraphExtensionJobs.withTabJobLock(tabId, async () => {
  try {
    const settings = await chrome.storage.local.get([
      "baseUrl",
      "baseUrlPresetId",
      "account",
      "token",
      "saveAs",
      "pngWidth",
      "pngHeight",
    ]);
    const resolvedServer = MindGraphShared.resolveMindGraphSettings(settings);
    const baseUrl = resolvedServer.baseUrl;
    const baseUrlPresetId = resolvedServer.presetId;
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
    const captureResult = await MindGraphDocExtract.capturePageContentMarkdown(tabId, MAX_CHARS, {
      suppressMindMateUi: true,
    });
    const payload = MindGraphDocExtract.captureResultToWebContentPayload(captureResult, resolvedLang);
    if (!payload) {
      finish({
        ok: false,
        error: MindGraphDocExtract.localizedCaptureErrorKey(captureResult),
      });
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
    const requestId = MindGraphShared.newRequestId();
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
    let res;
    try {
      res = await fetch(pngApiUrl, MindGraphShared.mgatFetchInit({
        method: "POST",
        signal: controller.signal,
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          "X-MG-Account": account,
          "X-MG-Client": MindGraphShared.mgClientHeader(),
          "X-Request-Id": requestId,
        },
        body: JSON.stringify(body),
      }));
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

    const savedDiagramId = MindGraphShared.parseDiagramIdFromPngResponse(res);
    const saveError = (res.headers.get("X-MG-Save-Error") || "").trim() || null;

    postProgress(progressPort, "receiving");
    const blob = await res.blob();
    let prepared;
    try {
      prepared = await MindGraphOffscreenBlobs.prepareDownloadUrlFromBlob(blob);
    } catch (e) {
      console.error("[MindGraph] prepare download url", e);
      finish({ ok: false, error: chrome.i18n.getMessage("errDownloadPrepare") });
      return;
    }
    const { href: downloadHref, revokeMode } = prepared;
    const filename = sanitizeFilename(payload.page_title || tab.title || "mindmap");
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
    MindGraphOffscreenBlobs.scheduleDownloadUrlRevoke(downloadHref, revokeMode);
    finish({
      ok: true,
      ...(savedDiagramId
        ? {
            diagramId: savedDiagramId,
            baseUrlPresetId,
            diagramUrl: MindGraphShared.buildCanvasDiagramUrl(baseUrl, savedDiagramId),
          }
        : {}),
      ...(saveError ? { saveError } : {}),
    });
  } catch (err) {
    console.error("[MindGraph] runGenerateMindmap", apiUrl || "(before URL)", err);
    finish({ ok: false, error: err?.message || String(err) });
  }
  return { lockComplete: true };
  });

  if (lockOutcome && lockOutcome.ok === false && lockOutcome.error === "errJobAlreadyRunning") {
    finish({ ok: false, error: "errJobAlreadyRunning" });
  }
}

/**
 * Read stored credentials and resolve the API origin.
 * @returns {Promise<{ baseUrl: string, account: string, token: string } | null>}
 */
async function getApiCredentials() {
  const settings = await chrome.storage.local.get(["baseUrl", "baseUrlPresetId", "account", "token"]);
  const resolvedServer = MindGraphShared.resolveMindGraphSettings(settings);
  const baseUrl = resolvedServer.baseUrl;
  const account = (settings.account || "").trim();
  const token = (settings.token || "").trim();
  if (!baseUrl || !account || !token) {
    return null;
  }
  return { baseUrl, account, token };
}

/**
 * @param {{ account: string, token: string }} creds
 * @returns {Record<string, string>}
 */
function buildAuthHeaders(creds) {
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${creds.token}`,
    "X-MG-Account": creds.account,
    "X-MG-Client": MindGraphShared.mgClientHeader(),
    "X-Request-Id": MindGraphShared.newRequestId(),
  };
}

/**
 * List the user's Document Summary packages for the popup picker.
 * @returns {Promise<{ ok: true, packages: Array<object> } | { ok: false, error: string }>}
 */
async function fetchPackages() {
  const creds = await getApiCredentials();
  if (!creds) {
    return { ok: false, error: chrome.i18n.getMessage("errSettingsIncomplete") };
  }
  const url = `${creds.baseUrl}/api/doc-summary/packages`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, MindGraphShared.mgatFetchInit({
      method: "GET",
      signal: controller.signal,
      headers: buildAuthHeaders(creds),
    }));
    clearTimeout(timeoutId);
    if (!res.ok) {
      const detail = await MindGraphShared.parseErrorDetailFromResponse(res);
      return { ok: false, error: chrome.i18n.getMessage("errApi", [String(res.status), detail]) };
    }
    const data = await res.json();
    return { ok: true, packages: Array.isArray(data.packages) ? data.packages : [] };
  } catch (e) {
    clearTimeout(timeoutId);
    return { ok: false, error: e?.message || String(e) };
  }
}

/**
 * Capture the active tab and store extract.md in a Document Summary session (COS).
 * @param {number} tabId
 * @param {number|null|undefined} packageId Optional existing doc_summary package id.
 * @returns {Promise<{ ok: true, document: object, packageId: number } | { ok: false, error: string }>}
 */
async function runSaveToFileCenter(tabId, packageId) {
  const parsedPackageId = MindGraphExtensionSecurity.parsePositiveInt(packageId);
  const creds = await getApiCredentials();
  if (!creds) {
    return { ok: false, error: chrome.i18n.getMessage("errSettingsIncomplete") };
  }

  const tab = await chrome.tabs.get(tabId);
  if (MindGraphShared.isRestrictedTabUrl(tab.url)) {
    return { ok: false, error: chrome.i18n.getMessage("errRestrictedPage") };
  }

  const outcome = await MindGraphExtensionJobs.withTabJobLock(tabId, async () => {
  const resolvedLang = await getResolvedLanguageForCapture();
  const captureResult = await MindGraphDocExtract.capturePageContentMarkdown(tabId, MAX_CHARS, {
    suppressMindMateUi: true,
  });
  const payload = MindGraphDocExtract.captureResultToWebContentPayload(captureResult, resolvedLang);
  if (!payload) {
    return { ok: false, error: MindGraphDocExtract.localizedCaptureErrorKey(captureResult) };
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const sessionRes = await fetch(`${creds.baseUrl}/api/doc-summary/session/start`, MindGraphShared.mgatFetchInit({
      method: "POST",
      signal: controller.signal,
      headers: buildAuthHeaders(creds),
      body: JSON.stringify({
        diagram_title: payload.page_title || undefined,
        package_id: parsedPackageId || undefined,
        create_if_missing: true,
      }),
    }));
    if (!sessionRes.ok) {
      clearTimeout(timeoutId);
      const detail = await MindGraphShared.parseErrorDetailFromResponse(sessionRes);
      return { ok: false, error: chrome.i18n.getMessage("errApi", [String(sessionRes.status), detail]) };
    }
    const sessionPkg = await sessionRes.json();
    const targetPackageId = MindGraphExtensionSecurity.parsePositiveInt(sessionPkg && sessionPkg.id);
    if (!targetPackageId) {
      clearTimeout(timeoutId);
      return { ok: false, error: chrome.i18n.getMessage("errFailed") };
    }

    const ingestUrl = `${creds.baseUrl}/api/doc-summary/packages/${targetPackageId}/documents/ingest-web`;
    const res = await fetch(ingestUrl, MindGraphShared.mgatFetchInit({
      method: "POST",
      signal: controller.signal,
      headers: buildAuthHeaders(creds),
      body: JSON.stringify({
        page_content: payload.page_content,
        page_url: payload.page_url,
        page_title: payload.page_title,
        language: payload.language,
      }),
    }));
    clearTimeout(timeoutId);
    if (!res.ok) {
      const detail = await MindGraphShared.parseErrorDetailFromResponse(res);
      return { ok: false, error: chrome.i18n.getMessage("errApi", [String(res.status), detail]) };
    }
    const document = await res.json();
    return { ok: true, document, packageId: targetPackageId };
  } catch (e) {
    clearTimeout(timeoutId);
    if (e && e.name === "AbortError") {
      return { ok: false, error: chrome.i18n.getMessage("errFetchTimeout") };
    }
    return { ok: false, error: e?.message || String(e) };
  }
  });

  if (outcome && outcome.ok === false && outcome.error === "errJobAlreadyRunning") {
    return { ok: false, error: "errJobAlreadyRunning" };
  }
  return outcome;
}

function ensureContextMenu() {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "mindgraph-generate",
      title: chrome.i18n.getMessage("contextMenuGenerate"),
      contexts: ["page"],
    });
    chrome.contextMenus.create({
      id: "mindgraph-extract-document",
      title: chrome.i18n.getMessage("contextMenuExtractDocument"),
      contexts: ["page"],
    });
  });
}

/**
 * @param {{ progressPort?: chrome.runtime.Port, fromContextMenu?: boolean, smarteduAssets?: Array<object>, smarteduToken?: string }} options
 * @param {number} tabId
 */
async function runExtractDocumentJob(tabId, options) {
  const { progressPort, fromContextMenu, smarteduAssets, smarteduToken } = options;
  const lockOutcome = await MindGraphExtensionJobs.withTabJobLock(tabId, async () => {
  const settings = await chrome.storage.local.get(["saveAs"]);
  const result = await MindGraphDocExtract.runDocumentExtract(tabId, {
    progressPort,
    saveAs: Boolean(settings.saveAs),
    smarteduAssets,
    smarteduToken,
  });
  if (progressPort) {
    try {
      progressPort.postMessage({ type: "extractResult", ...result });
    } catch {
      /* popup closed */
    }
  }
  if (fromContextMenu) {
    if (result.ok) {
      const noticeMsg = result.notice
        ? chrome.i18n.getMessage(result.notice, result.noticeArgs || [])
        : "";
      notifyUser(noticeMsg || chrome.i18n.getMessage("statusExtractDownloadStarted"));
    } else {
      const errKey =
        result.error && result.error.startsWith("err") ? result.error : "errExtractFailed";
      notifyUser(chrome.i18n.getMessage(errKey) || chrome.i18n.getMessage("errFailed"));
    }
  }
  return { lockComplete: true };
  });

  if (lockOutcome && lockOutcome.ok === false && lockOutcome.error === "errJobAlreadyRunning") {
    if (progressPort) {
      try {
        progressPort.postMessage({ type: "extractResult", ok: false, error: "errJobAlreadyRunning" });
      } catch {
        /* popup closed */
      }
    }
  }
}

/**
 * @param {chrome.runtime.Port} port
 */
function onDocExtractConnect(port) {
  const base = MindGraphDocExtract.DOC_EXTRACT_PORT;
  const prefix = `${base}-`;
  if (!port.name.startsWith(prefix)) {
    return;
  }
  const rest = port.name.slice(prefix.length);
  if (!/^\d+$/.test(rest)) {
    return;
  }
  const tabId = parseInt(rest, 10);
  if (tabId < 1) {
    return;
  }
  port.onMessage.addListener((msg) => {
    if (!msg || msg.type !== "start") {
      return;
    }
    void runExtractDocumentJob(tabId, {
      progressPort: port,
      fromContextMenu: false,
      smarteduAssets: Array.isArray(msg.smarteduAssets) ? msg.smarteduAssets : undefined,
      smarteduToken: typeof msg.smarteduToken === "string" ? msg.smarteduToken : undefined,
    });
  });
}

chrome.runtime.onInstalled.addListener(() => {
  ensureContextMenu();
  void MindGraphExtensionStorage.pruneStaleExtensionStorage();
});

/**
 * PING: wake MV3 service worker (see popup for optional wake before actions).
 * PNG generation runs in this worker for toolbar, context menu, and keyboard
 * (popup connects with a port for progress; closing the popup does not cancel).
 */
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (!MindGraphExtensionSecurity.isExtensionSender(sender)) {
    return false;
  }
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
  if (msg && msg.type === "LIST_PACKAGES") {
    fetchPackages().then(sendResponse);
    return true;
  }
  if (msg && msg.type === "SAVE_TO_FILE_CENTER" && typeof msg.tabId === "number") {
    const packageId = MindGraphExtensionSecurity.parsePositiveInt(msg.packageId);
    runSaveToFileCenter(msg.tabId, packageId || null).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "PREVIEW_EXTRACT" && typeof msg.tabId === "number") {
    const pageUrl = typeof msg.pageUrl === "string" ? msg.pageUrl : "";
    MindGraphDocExtract.previewExtractTarget(pageUrl, msg.tabId).then(sendResponse);
    return true;
  }
  if (msg && msg.type === "SAVE_SMARTEDU_TOKEN") {
    const token = MindGraphExtensionSecurity.parseSmartEduToken(msg.token);
    if (!token) {
      sendResponse({ ok: false, error: chrome.i18n.getMessage("errFailed") });
      return true;
    }
    MindGraphDocExtract.persistSmartEduToken(token).then(() => {
      sendResponse({ ok: true });
    });
    return true;
  }
  if (msg && msg.type === "SYNC_SMARTEDU_TOKEN") {
    const tabId = typeof msg.tabId === "number" ? msg.tabId : undefined;
    MindGraphDocExtract.discoverSmartEduToken(tabId).then(async (token) => {
      if (token) {
        await MindGraphDocExtract.persistSmartEduToken(token);
        sendResponse({ ok: true, tokenSet: true });
        return;
      }
      sendResponse({ ok: true, tokenSet: false });
    });
    return true;
  }
  if (msg && msg.type === "CAPTURE_MINDMATE_PAGE" && typeof msg.tabId === "number" && msg.tabId > 0) {
    const maxChars = typeof msg.maxMarkdownChars === "number" ? msg.maxMarkdownChars : undefined;
    MindGraphExtensionJobs.withTabJobLock(msg.tabId, async () => {
      const captureOptions = {};
      if (Array.isArray(msg.smarteduAssets)) {
        captureOptions.smarteduAssets = msg.smarteduAssets;
      }
      const parsedToken = MindGraphExtensionSecurity.parseSmartEduToken(msg.smarteduToken);
      if (parsedToken) {
        captureOptions.smarteduToken = parsedToken;
      }
      return MindGraphMindMate.captureMindMatePageContext(msg.tabId, maxChars, captureOptions);
    }).then((result) => {
      const dbg = MindGraphMindMate.captureDebug;
      if (dbg) {
        dbg.log("panel.request", "CAPTURE_MINDMATE_PAGE completed", {
          ok: Boolean(result && result.ok),
          error: result && result.error,
          source: result && result.source,
          markdownLen: result && result.markdown ? result.markdown.length : 0,
        });
      }
      sendResponse(result);
    });
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
chrome.runtime.onConnect.addListener(onDocExtractConnect);

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab?.id) {
    return;
  }
  if (info.menuItemId === "mindgraph-generate") {
    runGenerateMindmap(tab.id, { fromContextMenu: true });
    return;
  }
  if (info.menuItemId === "mindgraph-extract-document") {
    void runExtractDocumentJob(tab.id, { fromContextMenu: true });
  }
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
