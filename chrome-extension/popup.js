/**
 * Popup UI — i18n via chrome.i18n with optional override from _locales.
 * The Language setting also drives mind map generation language (via the service worker).
 */

/* global MindGraphShared */

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

/** @type {Record<string, string> | null} */
let i18nOverride = null;
/** @type {"auto" | "en" | "zh_CN" | "zh_TW"} */
let i18nMode = "auto";

const VERIFY_TIMEOUT_MS = MindGraphShared.VERIFY_TIMEOUT_MS;

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
 * @param {string} key
 * @param {string[] | undefined} substitutions
 * @returns {string}
 */
function t(key, substitutions) {
  if (i18nOverride && i18nOverride[key] != null) {
    let raw = i18nOverride[key];
    if (substitutions && Array.isArray(substitutions) && substitutions.length) {
      for (let i = 0; i < substitutions.length; i += 1) {
        raw = String(raw).split(`$${i + 1}`).join(String(substitutions[i]));
      }
    }
    return raw;
  }
  return chrome.i18n.getMessage(key, substitutions) || key;
}

/**
 * Progress bar + label; used by the SW progress port while generating.
 * @param {string} stage
 */
function setProgressStage(stage) {
  const key = STAGE_I18N[stage];
  const pct = STAGE_WIDTH_PCT[stage];
  const elStage = document.getElementById("progress-stage");
  const elFill = document.getElementById("progress-fill");
  if (key && elStage) {
    elStage.textContent = t(key);
  }
  if (typeof pct === "number" && elFill) {
    elFill.style.width = `${pct}%`;
    elFill.classList.add("is-active");
  }
}

/**
 * @returns {Promise<void>}
 */
async function initI18n() {
  const { uiLanguage } = await chrome.storage.local.get("uiLanguage");
  const raw = (uiLanguage || "auto").toString();
  if (raw === "auto" || (raw !== "en" && raw !== "zh_CN" && raw !== "zh_TW")) {
    i18nOverride = null;
    i18nMode = "auto";
  } else {
    i18nMode = raw;
    const url = chrome.runtime.getURL(`_locales/${raw}/messages.json`);
    const r = await fetch(url);
    const data = await r.json();
    i18nOverride = {};
    Object.keys(data).forEach((k) => {
      if (data[k] && data[k].message) {
        i18nOverride[k] = data[k].message;
      }
    });
  }
}

/**
 * BCP-47 for Intl
 * @returns {string}
 */
function getEffectiveBcpForIntl() {
  if (i18nMode === "en") {
    return "en";
  }
  if (i18nMode === "zh_CN") {
    return "zh-CN";
  }
  if (i18nMode === "zh_TW") {
    return "zh-TW";
  }
  return chrome.i18n.getUILanguage() || "en";
}

/**
 * @param {HTMLSelectElement} selectEl
 */
function populateUiLanguageSelect(selectEl) {
  if (!selectEl) {
    return;
  }
  const opts = [
    { value: "auto", key: "optionLangAuto" },
    { value: "en", key: "optionLangEn" },
    { value: "zh_CN", key: "optionLangZhCN" },
    { value: "zh_TW", key: "optionLangZhTW" },
  ];
  selectEl.textContent = "";
  opts.forEach((o) => {
    const opt = document.createElement("option");
    opt.value = o.value;
    opt.textContent = t(o.key);
    selectEl.appendChild(opt);
  });
}

function applyLocaleToDocument() {
  const bcp = getEffectiveBcpForIntl();
  if (bcp === "en") {
    document.documentElement.lang = "en";
  } else if (bcp.startsWith("zh-TW") || bcp === "zh-Hant" || bcp === "zh-HK") {
    document.documentElement.lang = "zh-TW";
  } else if (bcp.startsWith("zh")) {
    document.documentElement.lang = "zh-CN";
  } else {
    document.documentElement.lang = bcp;
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

/**
 * @param {HTMLElement} el
 * @param {string} text
 * @param {string} kind
 */
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
    const detail = await MindGraphShared.parseErrorDetailFromResponse(res);
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

/**
 * @param {HTMLInputElement} baseUrl
 * @param {HTMLInputElement} account
 * @param {HTMLInputElement} token
 * @param {HTMLElement} hint
 */
async function updateTokenExpiresHint(baseUrl, account, token, hint) {
  if (!hint) {
    return;
  }
  const origin = MindGraphShared.normalizeBaseUrl(baseUrl);
  const acc = (account || "").trim();
  const tok = (token || "").trim();
  if (!origin || !acc || !tok) {
    hint.textContent = "";
    return;
  }
  const url = `${origin}/api/auth/api-token`;
  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${tok}`,
        "X-MG-Account": acc,
        "X-MG-Client": "chrome-extension",
        "X-Request-Id": newRequestId(),
      },
    });
    if (!res.ok) {
      hint.textContent = t("tokenStatusUnknown");
      return;
    }
    const j = await res.json();
    if (!j.exists || j.is_active === false) {
      hint.textContent = t("tokenStatusNoToken");
      return;
    }
    if (!j.expires_at) {
      hint.textContent = t("tokenStatusNoToken");
      return;
    }
    const exp = new Date(j.expires_at);
    if (Number.isNaN(exp.getTime())) {
      hint.textContent = t("tokenStatusUnknown");
      return;
    }
    if (exp.getTime() <= Date.now()) {
      hint.textContent = t("tokenStatusExpired");
      return;
    }
    const bcp = getEffectiveBcpForIntl();
    const formatted = exp.toLocaleString(bcp, { dateStyle: "short", timeStyle: "short" });
    hint.textContent = t("tokenStatusValid", [formatted]);
  } catch (e) {
    console.error("[MindGraph] api-token", e);
    hint.textContent = t("tokenStatusUnknown");
  }
}

async function startPopup() {
  await initI18n();
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
  const fieldPngWidth = document.getElementById("field-png-width");
  const fieldPngHeight = document.getElementById("field-png-height");
  const fieldUiLanguage = document.getElementById("field-ui-language");
  const fieldTokenExpires = document.getElementById("field-token-expires");
  const progressWrap = document.getElementById("progress-wrap");
  const progressFill = document.getElementById("progress-fill");
  const progressStage = document.getElementById("progress-stage");
  const linkViewDiagram = document.getElementById("link-view-diagram");
  const libraryFullNote = document.getElementById("library-full-note");

  if (
    !mainView ||
    !settingsView ||
    !btnGenerate ||
    !btnSettings ||
    !btnSave ||
    !btnBack ||
    !fieldBaseUrl ||
    !fieldAccount ||
    !fieldToken ||
    !fieldSaveAs ||
    !fieldPngWidth ||
    !fieldPngHeight ||
    !fieldUiLanguage
  ) {
    console.error("[MindGraph] popup DOM missing");
    return;
  }

  applyLocaleToDocument();
  populateUiLanguageSelect(fieldUiLanguage);
  const storedLang = (await chrome.storage.local.get("uiLanguage")).uiLanguage;
  if (storedLang && ["auto", "en", "zh_CN", "zh_TW"].includes(String(storedLang))) {
    fieldUiLanguage.value = String(storedLang);
  } else {
    fieldUiLanguage.value = "auto";
  }
  applyI18n();

  /**
   * @param {boolean} visible
   */
  function setProgressVisible(visible) {
    if (!progressWrap) {
      return;
    }
    progressWrap.hidden = !visible;
    if (!visible && progressFill) {
      progressFill.style.width = "0%";
      progressFill.classList.remove("is-active");
    }
  }

  function closePopup() {
    window.close();
  }

  document.getElementById("btn-close-main")?.addEventListener("click", closePopup);
  document.getElementById("btn-close-settings")?.addEventListener("click", closePopup);

  fieldUiLanguage.addEventListener("change", async () => {
    const v = fieldUiLanguage.value;
    await chrome.storage.local.set({ uiLanguage: v });
    await initI18n();
    applyLocaleToDocument();
    populateUiLanguageSelect(fieldUiLanguage);
    fieldUiLanguage.value = v;
    applyI18n();
    await updateTokenExpiresHint(fieldBaseUrl.value, fieldAccount.value, fieldToken.value, fieldTokenExpires);
  });

  btnSettings.addEventListener("click", () => {
    mainView.hidden = true;
    settingsView.hidden = false;
    setStatus(settingsStatus, "", "");
    chrome.storage.local.get(
      ["baseUrl", "account", "token", "saveAs", "uiLanguage", "pngWidth", "pngHeight"],
      (data) => {
        fieldBaseUrl.value = data.baseUrl || MindGraphShared.DEFAULT_MINDGRAPH_BASE_URL;
        fieldAccount.value = data.account || "";
        fieldToken.value = data.token || "";
        fieldSaveAs.checked = Boolean(data.saveAs);
        if (data.uiLanguage && ["auto", "en", "zh_CN", "zh_TW"].includes(String(data.uiLanguage))) {
          fieldUiLanguage.value = String(data.uiLanguage);
        } else {
          fieldUiLanguage.value = "auto";
        }
        if (typeof data.pngWidth === "number") {
          fieldPngWidth.value = String(data.pngWidth);
        } else {
          fieldPngWidth.value = "";
        }
        if (typeof data.pngHeight === "number") {
          fieldPngHeight.value = String(data.pngHeight);
        } else {
          fieldPngHeight.value = "";
        }
        void updateTokenExpiresHint(fieldBaseUrl.value, fieldAccount.value, fieldToken.value, fieldTokenExpires);
      },
    );
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

      const wn = fieldPngWidth.value.trim() === "" ? Number.NaN : parseInt(fieldPngWidth.value, 10);
      const hn = fieldPngHeight.value.trim() === "" ? Number.NaN : parseInt(fieldPngHeight.value, 10);
      const payload = {
        baseUrl,
        account,
        token,
        saveAs: fieldSaveAs.checked,
        uiLanguage: fieldUiLanguage.value,
      };
      if (Number.isFinite(wn) && wn >= 400 && wn <= 4000) {
        payload.pngWidth = wn;
      }
      if (Number.isFinite(hn) && hn >= 300 && hn <= 3000) {
        payload.pngHeight = hn;
      }

      await new Promise((resolve, reject) => {
        chrome.storage.local.set(payload, () => {
          const err = chrome.runtime.lastError;
          if (err) {
            reject(new Error(err.message));
            return;
          }
          const toRemove = [];
          if (!Number.isFinite(wn) || wn < 400 || wn > 4000) {
            toRemove.push("pngWidth");
          }
          if (!Number.isFinite(hn) || hn < 300 || hn > 3000) {
            toRemove.push("pngHeight");
          }
          if (toRemove.length === 0) {
            resolve(undefined);
            return;
          }
          chrome.storage.local.remove(toRemove, () => {
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
      await initI18n();
      applyLocaleToDocument();
      populateUiLanguageSelect(fieldUiLanguage);
      fieldUiLanguage.value = String(payload.uiLanguage);
      applyI18n();
      await updateTokenExpiresHint(baseUrl, account, token, fieldTokenExpires);
    } catch (e) {
      console.error("[MindGraph] settings save error", e);
      setStatus(settingsStatus, t("errNetwork"), "err");
    } finally {
      btnSave.disabled = false;
      btnBack.disabled = false;
    }
  });

  if (linkViewDiagram) {
    linkViewDiagram.addEventListener("click", (e) => {
      e.preventDefault();
      const url = linkViewDiagram.getAttribute("data-href");
      if (url) {
        chrome.tabs.create({ url });
      }
    });
  }

  btnGenerate.addEventListener("click", () => {
    void (async () => {
      setStatus(statusEl, "", "");
      if (linkViewDiagram) {
        linkViewDiagram.hidden = true;
        linkViewDiagram.removeAttribute("data-href");
      }
      if (libraryFullNote) {
        libraryFullNote.hidden = true;
        libraryFullNote.textContent = "";
      }
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
      let completed = false;
      let cleaned = false;
      const cleanup = () => {
        if (cleaned) {
          return;
        }
        cleaned = true;
        if (port) {
          try {
            port.onMessage.removeListener(onMsg);
          } catch {
            /* ignore */
          }
          try {
            port.onDisconnect.removeListener(onDisc);
          } catch {
            /* ignore */
          }
        }
      };
      const onMsg = (msg) => {
        if (!msg) {
          return;
        }
        if (msg.type === "progress" && typeof msg.stage === "string" && STAGE_I18N[msg.stage]) {
          setProgressStage(msg.stage);
        } else if (msg.type === "result") {
          completed = true;
          cleanup();
          setProgressVisible(false);
          if (msg.ok) {
            setStatus(statusEl, t("statusDownloadStarted"), "ok");
            if (linkViewDiagram && msg.diagramUrl && typeof msg.diagramUrl === "string") {
              linkViewDiagram.setAttribute("data-href", msg.diagramUrl);
              linkViewDiagram.textContent = t("linkViewInLibrary");
              linkViewDiagram.hidden = false;
            } else if (libraryFullNote && msg.saveError === "limit_reached") {
              libraryFullNote.textContent = t("errLibraryFull");
              libraryFullNote.hidden = false;
            }
          } else {
            console.error("[MindGraph] generate failed", msg.error);
            setStatus(statusEl, msg.error || t("errFailed"), "err");
          }
          btnGenerate.disabled = false;
          btnSettings.disabled = false;
        }
      };
      const onDisc = () => {
        const disconnectErr = chrome.runtime.lastError;
        if (completed) {
          return;
        }
        cleanup();
        setProgressVisible(false);
        const reason = disconnectErr && disconnectErr.message;
        setStatus(
          statusEl,
          reason
            ? `${t("errPortDisconnected")} (${reason})`
            : t("errPortDisconnected"),
          "err",
        );
        btnGenerate.disabled = false;
        btnSettings.disabled = false;
      };

      let tab;
      try {
        [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      } catch (e) {
        console.error("[MindGraph] tabs.query", e);
        setProgressVisible(false);
        setStatus(statusEl, e?.message || String(e), "err");
        btnGenerate.disabled = false;
        btnSettings.disabled = false;
        return;
      }
      if (!tab?.id) {
        setProgressVisible(false);
        setStatus(statusEl, t("errNoTab"), "err");
        btnGenerate.disabled = false;
        btnSettings.disabled = false;
        return;
      }

      const connectName = `${MindGraphShared.MINDMAP_GENERATE_PORT}-${tab.id}`;
      try {
        port = chrome.runtime.connect({ name: connectName });
      } catch (e) {
        setProgressVisible(false);
        setStatus(
          statusEl,
          e?.message ? `${t("errPortDisconnected")} (${e.message})` : t("errPortDisconnected"),
          "err",
        );
        btnGenerate.disabled = false;
        btnSettings.disabled = false;
        return;
      }

      port.onMessage.addListener(onMsg);
      port.onDisconnect.addListener(onDisc);
    })();
  });
}

void startPopup().catch((e) => {
  console.error("[MindGraph] startPopup", e);
});
