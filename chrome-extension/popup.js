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
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
      "X-MG-Account": account,
    },
  });
  if (res.ok) {
    return { ok: true };
  }
  const detail = await parseHttpErrorDetail(res);
  return { ok: false, error: t("errApi", [String(res.status), detail]) };
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

  let port;
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    if (!tab?.id) {
      setProgressVisible(false);
      setStatus(statusEl, t("errNoTab"), "err");
      return;
    }

    port = chrome.runtime.connect({ name: "mindgraph-generate" });

    const result = await new Promise((resolve) => {
      let settled = false;
      const cleanup = () => {
        port.onMessage.removeListener(onMessage);
        port.onDisconnect.removeListener(onDisconnect);
      };
      const onMessage = (msg) => {
        if (msg?.type === "progress" && msg.stage) {
          setProgressStage(msg.stage);
          return;
        }
        if (msg?.type === "result") {
          if (settled) {
            return;
          }
          settled = true;
          cleanup();
          resolve(msg);
        }
      };
      const onDisconnect = () => {
        if (settled) {
          return;
        }
        settled = true;
        cleanup();
        resolve({ ok: false, error: t("errFailed") });
      };
      port.onMessage.addListener(onMessage);
      port.onDisconnect.addListener(onDisconnect);
      port.postMessage({ type: "GENERATE_MINDMAP_PNG", tabId: tab.id });
    });

    setProgressVisible(false);
    if (result?.ok) {
      setStatus(statusEl, t("statusDownloadStarted"), "ok");
    } else {
      setStatus(statusEl, result?.error || t("errFailed"), "err");
    }
  } catch (e) {
    setProgressVisible(false);
    setStatus(statusEl, e?.message || String(e), "err");
  } finally {
    if (port) {
      try {
        port.disconnect();
      } catch {
        /* ignore */
      }
    }
    btnGenerate.disabled = false;
    btnSettings.disabled = false;
  }
});
