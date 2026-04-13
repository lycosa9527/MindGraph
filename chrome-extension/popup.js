/**
 * Popup UI — i18n via chrome.i18n (matches browser locale).
 */

const STAGE_I18N = {
  reading: "stageReadingPage",
  sending: "stageSending",
  serverProcessing: "stageServerProcessing",
  receiving: "stageReceiving",
  saving: "stageSaving",
};

const STAGE_WIDTH_PCT = {
  reading: 20,
  sending: 40,
  serverProcessing: 60,
  receiving: 80,
  saving: 100,
};

function t(key, substitutions) {
  const msg = chrome.i18n.getMessage(key, substitutions);
  return msg || key;
}

const VERIFY_TIMEOUT_MS = 60000;

/** Same as background — LLM + Playwright can exceed 60s. */
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

/**
 * Ensure MV3 service worker is running before sendMessage to background.
 * @returns {Promise<void>}
 */
function pingServiceWorker() {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage({ type: "PING" }, (response) => {
      if (chrome.runtime.lastError) {
        reject(new Error(chrome.runtime.lastError.message));
        return;
      }
      if (response && response.ok) {
        resolve(undefined);
        return;
      }
      resolve(undefined);
    });
  });
}

function isTransientConnectionError(text) {
  if (!text || typeof text !== "string") {
    return false;
  }
  const lower = text.toLowerCase();
  return (
    lower.includes("receiving end") ||
    lower.includes("does not exist") ||
    lower.includes("could not establish connection") ||
    lower.includes("message port closed") ||
    lower.includes("before a response was received")
  );
}

/**
 * Best-effort wake before messaging the service worker.
 * @returns {Promise<void>}
 */
async function tryPingServiceWorker() {
  try {
    await pingServiceWorker();
  } catch (e) {
    console.warn("[MindGraph] optional PING failed", e);
  }
}

function normalizeBaseUrl(url) {
  const trimmed = (url || "").trim().replace(/\/+$/, "");
  return trimmed;
}

function sanitizeFilename(title) {
  const base = (title || "mindgraph").replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").slice(0, 80);
  return base.endsWith(".png") ? base : `${base}.png`;
}

/**
 * @param {number} tabId
 * @returns {Promise<{ ok: boolean, payload?: object, error?: string }>}
 */
async function capturePageWithRetry(tabId) {
  for (let attempt = 0; attempt < 2; attempt++) {
    if (attempt > 0) {
      await new Promise((r) => setTimeout(r, 200));
    }
    await tryPingServiceWorker();
    const result = await new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: "CAPTURE_PAGE_FOR_MINDMAP", tabId },
        (response) => {
          if (chrome.runtime.lastError) {
            resolve({
              ok: false,
              error: chrome.runtime.lastError.message,
            });
            return;
          }
          if (response && response.ok) {
            resolve({ ok: true, payload: response.payload });
            return;
          }
          resolve({
            ok: false,
            error: response?.error || t("errFailed"),
          });
        },
      );
    });
    if (result.ok || !isTransientConnectionError(String(result.error))) {
      return result;
    }
  }
  return { ok: false, error: t("errPortDisconnected") };
}

/**
 * Fetch + download run in the popup so the service worker is not tied to a long port.
 * @param {number} tabId
 * @returns {Promise<{ ok: boolean, error?: string }>}
 */
async function generateMindmapPngInPopup(tabId) {
  const settings = await chrome.storage.local.get(["baseUrl", "account", "token", "saveAs"]);
  const baseUrl = normalizeBaseUrl(settings.baseUrl);
  const account = (settings.account || "").trim();
  const token = (settings.token || "").trim();
  if (!baseUrl || !account || !token) {
    return { ok: false, error: t("errSettingsIncomplete") };
  }

  setProgressStage("reading");
  const captureResult = await capturePageWithRetry(tabId);
  if (!captureResult.ok) {
    return {
      ok: false,
      error: captureResult.error || t("errFailed"),
    };
  }

  const payload = captureResult.payload;

  const url = `${baseUrl}/api/web_content_mindmap_png`;
  const body = {
    page_content: payload.page_content,
    content_format: payload.content_format || "text/plain",
    page_title: payload.page_title || null,
    page_url: payload.page_url || null,
    language: payload.language || "zh",
  };

  setProgressStage("sending");
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
      return { ok: false, error: t("errFetchTimeout") };
    }
    return { ok: false, error: fetchErr?.message || String(fetchErr) };
  }
  clearTimeout(timeoutId);

  setProgressStage("serverProcessing");

  if (!res.ok) {
    if (res.status === 429) {
      return { ok: false, error: t("errRateLimit") };
    }
    if (res.status === 503) {
      return { ok: false, error: t("errServiceUnavailable") };
    }
    const detail = await parseHttpErrorDetail(res);
    console.error("[MindGraph] API HTTP error", res.status, url, detail);
    return {
      ok: false,
      error: t("errApi", [String(res.status), detail]),
    };
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
    return { ok: false, error: t("errNotPng") };
  }

  setProgressStage("receiving");
  const blob = await res.blob();
  const blobUrl = URL.createObjectURL(blob);
  const filename = sanitizeFilename(payload.page_title);
  const saveAs = Boolean(settings.saveAs);
  setProgressStage("saving");
  try {
    await chrome.downloads.download({
      url: blobUrl,
      filename,
      saveAs,
    });
  } catch (dlErr) {
    console.error("[MindGraph] downloads.download", dlErr);
    return { ok: false, error: dlErr?.message || String(dlErr) };
  }
  setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);

  return { ok: true };
}

function applyLocaleToDocument() {
  const ui = chrome.i18n.getUILanguage();
  const lower = ui.toLowerCase();
  if (lower === "zh-tw" || lower.startsWith("zh-hant") || lower === "zh_hk") {
    document.documentElement.lang = "zh-TW";
  } else if (lower.startsWith("zh")) {
    document.documentElement.lang = "zh-CN";
  } else {
    document.documentElement.lang = "en";
  }
  document.title = t("appTitle");
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (key) {
      el.textContent = t(key);
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (key) {
      el.placeholder = t(key);
    }
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((el) => {
    const key = el.getAttribute("data-i18n-aria-label");
    if (key) {
      const label = t(key);
      el.setAttribute("aria-label", label);
      el.setAttribute("title", label);
    }
  });
}

function setStatus(el, text, kind) {
  el.textContent = text || "";
  el.classList.remove("ok", "err", "is-loading");
  if (kind === "ok") {
    el.classList.add("ok");
  } else if (kind === "err") {
    el.classList.add("err");
  } else if (kind === "loading") {
    el.classList.add("is-loading");
  }
}

/**
 * @param {Response} res
 * @returns {Promise<string>}
 */
async function parseHttpErrorDetail(res) {
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
 * @param {string} baseUrl
 * @param {string} account
 * @param {string} token
 * @returns {Promise<{ ok: true } | { ok: false, error: string }>}
 */
async function verifyCredentials(baseUrl, account, token) {
  const origin = baseUrl.replace(/\/+$/, "");
  const url = `${origin}/api/auth/me`;
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), VERIFY_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      method: "GET",
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "X-MG-Account": account,
        "X-MG-Client": "chrome-extension",
        "X-Request-Id": newRequestId(),
      },
    });
    clearTimeout(timeoutId);
    if (res.ok) {
      return { ok: true };
    }
    const detail = await parseHttpErrorDetail(res);
    return { ok: false, error: t("errApi", [String(res.status), detail]) };
  } catch (e) {
    clearTimeout(timeoutId);
    if (e && e.name === "AbortError") {
      console.error("[MindGraph] verifyCredentials timeout", VERIFY_TIMEOUT_MS, "ms", url);
      return { ok: false, error: t("errVerifyTimeout") };
    }
    const short = String(e?.message || e).slice(0, 200);
    console.error("[MindGraph] verifyCredentials", short);
    return { ok: false, error: t("errNetworkDetail", [short]) };
  }
}

const mainView = document.getElementById("main-view");
const settingsView = document.getElementById("settings-view");
const btnGenerate = document.getElementById("btn-generate");
const btnSettings = document.getElementById("btn-settings");
const btnSave = document.getElementById("btn-save");
const btnBack = document.getElementById("btn-back");
const statusEl = document.getElementById("status");
const settingsStatus = document.getElementById("settings-status");
const fieldBaseUrl = document.getElementById("field-base-url");
const fieldAccount = document.getElementById("field-account");
const fieldToken = document.getElementById("field-token");
const fieldSaveAs = document.getElementById("field-save-as");
const progressWrap = document.getElementById("progress-wrap");
const progressFill = document.getElementById("progress-fill");
const progressStage = document.getElementById("progress-stage");

applyLocaleToDocument();
applyI18n();

function closePopup() {
  window.close();
}

document.getElementById("btn-close-main")?.addEventListener("click", closePopup);
document.getElementById("btn-close-settings")?.addEventListener("click", closePopup);

/**
 * @param {boolean} visible
 */
function setProgressVisible(visible) {
  progressWrap.hidden = !visible;
  if (!visible && progressFill) {
    progressFill.style.width = "0%";
    progressFill.classList.remove("is-active");
  }
}

/**
 * @param {string} stage
 */
function setProgressStage(stage) {
  const key = STAGE_I18N[stage];
  const pct = STAGE_WIDTH_PCT[stage];
  if (key && progressStage) {
    progressStage.textContent = t(key);
  }
  if (typeof pct === "number" && progressFill) {
    progressFill.style.width = `${pct}%`;
    progressFill.classList.add("is-active");
  }
}

btnSettings.addEventListener("click", () => {
  mainView.hidden = true;
  settingsView.hidden = false;
  setStatus(settingsStatus, "");
  chrome.storage.local.get(["baseUrl", "account", "token", "saveAs"], (data) => {
    fieldBaseUrl.value = data.baseUrl || "";
    fieldAccount.value = data.account || "";
    fieldToken.value = data.token || "";
    fieldSaveAs.checked = Boolean(data.saveAs);
  });
});

btnBack.addEventListener("click", () => {
  settingsView.hidden = true;
  mainView.hidden = false;
});

btnSave.addEventListener("click", async () => {
  const baseUrl = fieldBaseUrl.value.trim().replace(/\/+$/, "");
  const account = fieldAccount.value.trim();
  const token = fieldToken.value.trim();
  if (!baseUrl || !account || !token) {
    setStatus(settingsStatus, t("errFillAll"), "err");
    return;
  }

  setStatus(settingsStatus, t("statusVerifying"), "loading");
  btnSave.disabled = true;
  btnBack.disabled = true;
  try {
    const verified = await verifyCredentials(baseUrl, account, token);
    if (!verified.ok) {
      console.error("[MindGraph] settings verify failed", verified.error);
      setStatus(settingsStatus, verified.error, "err");
      return;
    }

    const payload = {
      baseUrl,
      account,
      token,
      saveAs: fieldSaveAs.checked,
    };

    await new Promise((resolve, reject) => {
      chrome.storage.local.set(payload, () => {
        const err = chrome.runtime.lastError;
        if (err) {
          reject(new Error(err.message));
          return;
        }
        chrome.storage.local.remove(["pngWidth", "pngHeight"], () => {
          const e2 = chrome.runtime.lastError;
          if (e2) {
            reject(new Error(e2.message));
          } else {
            resolve(undefined);
          }
        });
      });
    });
    setStatus(settingsStatus, t("statusSaved"), "ok");
  } catch (e) {
    console.error("[MindGraph] settings save error", e);
    setStatus(settingsStatus, t("errNetwork"), "err");
  } finally {
    btnSave.disabled = false;
    btnBack.disabled = false;
  }
});

btnGenerate.addEventListener("click", async () => {
  setStatus(statusEl, "");
  setProgressVisible(true);
  if (progressFill) {
    progressFill.style.width = "0%";
    progressFill.classList.add("is-active");
  }
  if (progressStage) {
    progressStage.textContent = t("statusWorking");
  }
  btnGenerate.disabled = true;
  btnSettings.disabled = true;

  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      setProgressVisible(false);
      setStatus(statusEl, t("errNoTab"), "err");
      return;
    }

    let result;
    try {
      result = await generateMindmapPngInPopup(tab.id);
    } catch (genErr) {
      setProgressVisible(false);
      console.error("[MindGraph] generate threw", genErr);
      setStatus(
        statusEl,
        `${t("errPortDisconnected")} (${genErr?.message || String(genErr)})`,
        "err",
      );
      return;
    }

    setProgressVisible(false);
    if (result?.ok) {
      setStatus(statusEl, t("statusDownloadStarted"), "ok");
    } else {
      console.error("[MindGraph] generate failed", result?.error || result);
      setStatus(statusEl, result?.error || t("errFailed"), "err");
    }
  } catch (e) {
    setProgressVisible(false);
    console.error("[MindGraph] generate exception", e);
    setStatus(statusEl, e?.message || String(e), "err");
  } finally {
    btnGenerate.disabled = false;
    btnSettings.disabled = false;
  }
});
