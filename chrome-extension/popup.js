/**
 * Popup UI — i18n via chrome.i18n with optional override from _locales.
 * The Language setting also drives mind map generation language (via the service worker).
 */

/* global MindGraphShared, MindGraphMindMate, MindGraphExtensionStorage */

const STAGE_I18N = {
  reading: "stageReadingPage",
  sending: "stageSending",
  serverProcessing: "stageServerProcessing",
  receiving: "stageReceiving",
  saving: "stageSaving",
};

const EXTRACT_STAGE_I18N = {
  preparing: "extractStagePreparing",
  scrolling: "extractStageScrolling",
  collecting: "extractStageCollecting",
  assembling: "extractStageAssembling",
  downloading: "extractStageDownloading",
};

const EXTRACT_STAGE_WIDTH_PCT = {
  preparing: 15,
  scrolling: 35,
  collecting: 55,
  assembling: 75,
  downloading: 100,
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
 * @param {string | undefined} code
 * @returns {string}
 */
function userFacingError(code) {
  if (code && code.startsWith("err")) {
    return t(code);
  }
  return t("errExtractFailed");
}

/**
 * Progress bar + label; used by the SW progress port while generating.
 * @param {string} stage
 */
function setProgressStage(stage) {
  const key = STAGE_I18N[stage] || EXTRACT_STAGE_I18N[stage];
  const pct = STAGE_WIDTH_PCT[stage] ?? EXTRACT_STAGE_WIDTH_PCT[stage];
  applyProgressStage(document.getElementById("progress-stage"), document.getElementById("progress-fill"), key, pct);
}

/**
 * @param {HTMLElement | null} elStage
 * @param {HTMLElement | null} elFill
 * @param {string | undefined} key
 * @param {number | undefined} pct
 */
function applyProgressStage(elStage, elFill, key, pct) {
  if (key && elStage) {
    elStage.textContent = t(key);
  }
  if (typeof pct === "number" && elFill) {
    elFill.style.width = `${pct}%`;
    elFill.classList.add("is-active");
  }
}

/**
 * Progress bar for the Download tab extract flow.
 * @param {string} stage
 */
function setDownloadExtractProgressStage(stage) {
  const key = EXTRACT_STAGE_I18N[stage];
  const pct = EXTRACT_STAGE_WIDTH_PCT[stage];
  applyProgressStage(
    document.getElementById("download-progress-stage"),
    document.getElementById("download-progress-fill"),
    key,
    pct,
  );
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
 * @param {string | undefined} selectedPresetId
 */
function populateBaseUrlSelect(selectEl, selectedPresetId) {
  if (!selectEl) {
    return;
  }
  const current = selectedPresetId || selectEl.value || "production";
  selectEl.textContent = "";
  for (const preset of MindGraphShared.BASE_URL_PRESETS) {
    const opt = document.createElement("option");
    opt.value = preset.id;
    opt.textContent = t(preset.labelKey);
    selectEl.appendChild(opt);
  }
  const resolved = MindGraphShared.resolveBaseUrlPresetId(current);
  selectEl.value = MindGraphShared.BASE_URL_PRESETS.some((entry) => entry.id === resolved)
    ? resolved
    : "production";
}

/**
 * @param {HTMLSelectElement} selectEl
 * @returns {string}
 */
function readBaseUrlFromSelect(selectEl) {
  return MindGraphShared.baseUrlFromPresetId(selectEl ? selectEl.value : "production");
}

/**
 * @param {HTMLSelectElement | null} selectEl
 * @param {HTMLElement | null} warningEl
 */
function updateLocalServerWarning(selectEl, warningEl) {
  if (!selectEl || !warningEl) {
    return;
  }
  warningEl.hidden = selectEl.value !== "local";
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
    const res = await fetch(url, MindGraphShared.mgatFetchInit({
      method: "GET",
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${token}`,
        "X-MG-Account": account,
        "X-MG-Client": MindGraphShared.mgClientHeader(),
        "X-Request-Id": newRequestId(),
      },
    }));
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
    const res = await fetch(url, MindGraphShared.mgatFetchInit({
      method: "GET",
      headers: {
        Authorization: `Bearer ${tok}`,
        "X-MG-Account": acc,
        "X-MG-Client": MindGraphShared.mgClientHeader(),
        "X-Request-Id": newRequestId(),
      },
    }));
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
  const generateView = document.getElementById("generate-view");
  const mindmateView = document.getElementById("mindmate-view");
  const downloadView = document.getElementById("download-view");
  const settingsView = document.getElementById("settings-view");
  const tabGenerate = document.getElementById("tab-generate");
  const tabMindmate = document.getElementById("tab-mindmate");
  const tabDownload = document.getElementById("tab-download");
  const tabSettings = document.getElementById("tab-settings");
  const mainView = generateView;
  const btnGenerate = document.getElementById("btn-generate");
  const btnSave = document.getElementById("btn-save");
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
  const fieldLocalServerWarning = document.getElementById("field-local-server-warning");
  const progressWrap = document.getElementById("progress-wrap");
  const progressFill = document.getElementById("progress-fill");
  const progressStage = document.getElementById("progress-stage");
  const linkViewDiagram = document.getElementById("link-view-diagram");
  const libraryFullNote = document.getElementById("library-full-note");

  if (
    !generateView ||
    !mindmateView ||
    !downloadView ||
    !settingsView ||
    !tabGenerate ||
    !tabMindmate ||
    !tabDownload ||
    !tabSettings ||
    !mainView ||
    !btnGenerate ||
    !btnSave ||
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

  /** @type {Array<HTMLButtonElement>} */
  const mainTabButtons = [tabGenerate, tabMindmate, tabDownload, tabSettings];

  /**
   * @param {boolean} disabled
   */
  function setMainTabsDisabled(disabled) {
    for (const btn of mainTabButtons) {
      btn.disabled = disabled;
    }
  }

  /** @type {"generate" | "mindmate" | "download" | "settings"} */
  let activeMainTab = "generate";

  /** @type {{ onTabShown?: () => void } | null} */
  let mindmatePanel = null;

  function loadSettingsFields() {
    setStatus(settingsStatus, "", "");
    chrome.storage.local.get(
      ["baseUrl", "baseUrlPresetId", "account", "token", "saveAs", "uiLanguage", "pngWidth", "pngHeight"],
      (data) => {
        populateBaseUrlSelect(
          fieldBaseUrl,
          data.baseUrlPresetId ||
            MindGraphShared.resolveBaseUrlPresetId(
              data.baseUrl || MindGraphShared.DEFAULT_MINDGRAPH_BASE_URL,
            ),
        );
        updateLocalServerWarning(fieldBaseUrl, fieldLocalServerWarning);
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
        void updateTokenExpiresHint(
          readBaseUrlFromSelect(fieldBaseUrl),
          fieldAccount.value,
          fieldToken.value,
          fieldTokenExpires,
        );
      },
    );
  }

  /**
   * @param {"generate" | "mindmate" | "download" | "settings"} tab
   * @returns {Promise<void>}
   */
  async function switchMainTab(tab) {
    activeMainTab = tab;
    generateView.hidden = tab !== "generate";
    mindmateView.hidden = tab !== "mindmate";
    downloadView.hidden = tab !== "download";
    settingsView.hidden = tab !== "settings";
    tabGenerate.classList.toggle("is-active", tab === "generate");
    tabMindmate.classList.toggle("is-active", tab === "mindmate");
    tabDownload.classList.toggle("is-active", tab === "download");
    tabSettings.classList.toggle("is-active", tab === "settings");
    tabGenerate.setAttribute("aria-selected", tab === "generate" ? "true" : "false");
    tabMindmate.setAttribute("aria-selected", tab === "mindmate" ? "true" : "false");
    tabDownload.setAttribute("aria-selected", tab === "download" ? "true" : "false");
    tabSettings.setAttribute("aria-selected", tab === "settings" ? "true" : "false");
    if (tab === "download") {
      await loadExtractPreview();
    }
    if (tab === "settings") {
      loadSettingsFields();
    }
    if (tab === "mindmate" && mindmatePanel && mindmatePanel.onTabShown) {
      mindmatePanel.onTabShown();
    }
  }

  tabGenerate.addEventListener("click", () => {
    void switchMainTab("generate");
  });
  tabMindmate.addEventListener("click", () => {
    void switchMainTab("mindmate");
  });
  tabDownload.addEventListener("click", () => {
    void switchMainTab("download");
  });
  tabSettings.addEventListener("click", () => {
    void switchMainTab("settings");
  });

  mindmatePanel = MindGraphMindMate.initMindMatePanel({
    t,
    newRequestId,
    getCredentials: async () => {
      const data = await chrome.storage.local.get(["baseUrl", "baseUrlPresetId", "account", "token"]);
      const resolvedServer = MindGraphShared.resolveMindGraphSettings(data);
      return {
        baseUrl: resolvedServer.baseUrl,
        account: data.account || "",
        token: data.token || "",
      };
    },
    getActiveTabId: async () => {
      let tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
      if (tabs[0]?.id) {
        return tabs[0].id;
      }
      tabs = await chrome.tabs.query({ active: true, currentWindow: true });
      return tabs[0]?.id ?? null;
    },
    setMainTabsDisabled,
    switchMainTab,
    view: mindmateView,
    setupHint: document.getElementById("mindmate-setup-hint"),
    chatWrap: document.getElementById("mindmate-chat-wrap"),
    messagesEl: document.getElementById("mindmate-messages"),
    inputEl: document.getElementById("mindmate-input"),
    btnSend: document.getElementById("btn-mindmate-send"),
    btnStop: document.getElementById("btn-mindmate-stop"),
    btnNew: document.getElementById("btn-mindmate-new"),
    linkWeb: document.getElementById("link-mindmate-web"),
    statusEl: document.getElementById("mindmate-status"),
    pageContextNoticeEl: document.getElementById("mindmate-page-context-notice"),
    btnGoSettings: document.getElementById("btn-mindmate-go-settings"),
    includePageCheckbox: document.getElementById("mindmate-include-page"),
    historyListEl: document.getElementById("mindmate-history-list"),
  });

  applyLocaleToDocument();
  populateBaseUrlSelect(fieldBaseUrl);
  updateLocalServerWarning(fieldBaseUrl, fieldLocalServerWarning);
  populateUiLanguageSelect(fieldUiLanguage);
  const storedLang = (await chrome.storage.local.get("uiLanguage")).uiLanguage;
  if (storedLang && ["auto", "en", "zh_CN", "zh_TW"].includes(String(storedLang))) {
    fieldUiLanguage.value = String(storedLang);
  } else {
    fieldUiLanguage.value = "auto";
  }
  applyI18n();
  void MindGraphExtensionStorage.pruneStaleExtensionStorage();

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
  document.getElementById("btn-close-mindmate")?.addEventListener("click", closePopup);
  document.getElementById("btn-close-download")?.addEventListener("click", closePopup);
  document.getElementById("btn-close-settings")?.addEventListener("click", closePopup);

  fieldBaseUrl.addEventListener("change", () => {
    updateLocalServerWarning(fieldBaseUrl, fieldLocalServerWarning);
  });

  fieldUiLanguage.addEventListener("change", async () => {
    const v = fieldUiLanguage.value;
    await chrome.storage.local.set({ uiLanguage: v });
    await initI18n();
    applyLocaleToDocument();
    populateBaseUrlSelect(fieldBaseUrl, fieldBaseUrl.value);
    updateLocalServerWarning(fieldBaseUrl, fieldLocalServerWarning);
    populateUiLanguageSelect(fieldUiLanguage);
    fieldUiLanguage.value = v;
    applyI18n();
    await updateTokenExpiresHint(
      readBaseUrlFromSelect(fieldBaseUrl),
      fieldAccount.value,
      fieldToken.value,
      fieldTokenExpires,
    );
  });

  btnSave.addEventListener("click", async () => {
    const baseUrl = readBaseUrlFromSelect(fieldBaseUrl);
    const account = fieldAccount.value.trim();
    const token = fieldToken.value.trim();
    if (!baseUrl || !account || !token) {
      setStatus(settingsStatus, t("errFillAll"), "err");
      return;
    }

    setStatus(settingsStatus, t("statusVerifying"), "loading");
    btnSave.disabled = true;
    setMainTabsDisabled(true);
    try {
      const previous = await chrome.storage.local.get(["baseUrl", "account"]);
      const previousAuthKey = MindGraphExtensionStorage.buildMindGraphAuthKey(
        previous.baseUrl,
        previous.account,
      );
      const nextAuthKey = MindGraphExtensionStorage.buildMindGraphAuthKey(baseUrl, account);
      const verified = await verifyCredentials(baseUrl, account, token);
      if (!verified.ok) {
        console.error("[MindGraph] settings verify failed", verified.error);
        setStatus(settingsStatus, verified.error, "err");
        return;
      }

      if (previousAuthKey !== nextAuthKey) {
        await MindGraphExtensionStorage.clearMindMateThread();
      }

      const wn = fieldPngWidth.value.trim() === "" ? Number.NaN : parseInt(fieldPngWidth.value, 10);
      const hn = fieldPngHeight.value.trim() === "" ? Number.NaN : parseInt(fieldPngHeight.value, 10);
      const payload = {
        baseUrl,
        baseUrlPresetId: fieldBaseUrl.value,
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
      if (mindmatePanel && mindmatePanel.onTabShown) {
        mindmatePanel.onTabShown();
      }
      await initI18n();
      applyLocaleToDocument();
      populateBaseUrlSelect(fieldBaseUrl, MindGraphShared.resolveBaseUrlPresetId(baseUrl));
      updateLocalServerWarning(fieldBaseUrl, fieldLocalServerWarning);
      populateUiLanguageSelect(fieldUiLanguage);
      fieldUiLanguage.value = String(payload.uiLanguage);
      applyI18n();
      await updateTokenExpiresHint(baseUrl, account, token, fieldTokenExpires);
    } catch (e) {
      console.error("[MindGraph] settings save error", e);
      setStatus(settingsStatus, t("errNetwork"), "err");
    } finally {
      btnSave.disabled = false;
      setMainTabsDisabled(false);
    }
  });

  if (linkViewDiagram) {
    linkViewDiagram.addEventListener("click", (e) => {
      e.preventDefault();
      const diagramId = linkViewDiagram.getAttribute("data-diagram-id");
      const presetId = linkViewDiagram.getAttribute("data-base-url-preset");
      let url = linkViewDiagram.getAttribute("data-href") || linkViewDiagram.href;
      if (diagramId) {
        const resolved = MindGraphShared.resolveMindGraphSettings({
          baseUrlPresetId: presetId || undefined,
        });
        const rebuilt = MindGraphShared.buildCanvasDiagramUrl(resolved.baseUrl, diagramId);
        if (rebuilt) {
          url = rebuilt;
        }
      }
      if (url && url !== "#" && !url.endsWith("#")) {
        void chrome.tabs.create({ url, active: true });
      }
    });
  }

  const fileCenterSection = document.getElementById("file-center-section");
  const fieldPackage = document.getElementById("field-package");
  const btnSaveFileCenter = document.getElementById("btn-save-file-center");

  /**
   * Populate the package picker from the backend. Hides the section when no
   * package exists or credentials are missing.
   * @returns {Promise<void>}
   */
  async function loadPackages() {
    if (!fileCenterSection || !fieldPackage || !btnSaveFileCenter) {
      return;
    }
    const response = await new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: "LIST_PACKAGES" }, (res) => {
        void chrome.runtime.lastError;
        resolve(res || { ok: false, error: "no_response" });
      });
    });
    if (!response.ok || !Array.isArray(response.packages) || response.packages.length === 0) {
      fileCenterSection.hidden = true;
      return;
    }
    fieldPackage.textContent = "";
    response.packages.forEach((pkg) => {
      const opt = document.createElement("option");
      opt.value = String(pkg.id);
      opt.textContent = pkg.name || t("fileCenterUntitled");
      fieldPackage.appendChild(opt);
    });
    fileCenterSection.hidden = false;
  }

  void loadPackages();

  const docExtractSection = document.getElementById("doc-extract-section");
  const downloadUnsupported = document.getElementById("download-unsupported");
  const docExtractDetected = document.getElementById("doc-extract-detected");
  const docExtractActiveTab = document.getElementById("doc-extract-active-tab");
  const docExtractTitle = document.getElementById("doc-extract-title");
  const docExtractPages = document.getElementById("doc-extract-pages");
  const smarteduPanel = document.getElementById("smartedu-extract-panel");
  const smarteduTokenStatus = document.getElementById("smartedu-token-status");
  const smarteduAssetList = document.getElementById("smartedu-asset-list");
  const btnSyncSmartEduToken = document.getElementById("btn-sync-smartedu-token");
  const btnPasteSmartEduToken = document.getElementById("btn-paste-smartedu-token");
  const btnExtractDocument = document.getElementById("btn-extract-document");
  const downloadStatusEl = document.getElementById("download-status");
  const downloadProgressWrap = document.getElementById("download-progress-wrap");
  const downloadProgressFill = document.getElementById("download-progress-fill");
  const downloadProgressStage = document.getElementById("download-progress-stage");

  /** @type {Array<object>} */
  let previewSmartEduAssets = [];

  /** @type {ReturnType<typeof setTimeout> | null} */
  let extractPreviewRefreshTimer = null;

  /**
   * Active page tab for Download — lastFocusedWindow avoids stale window on Edge/Chrome.
   * @returns {Promise<chrome.tabs.Tab | undefined>}
   */
  async function getActiveContentTab() {
    let tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tabs[0]?.id) {
      return tabs[0];
    }
    tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    return tabs[0];
  }

  /**
   * @param {string | undefined} url
   * @returns {string}
   */
  function hostnameFromUrl(url) {
    if (!url) {
      return "";
    }
    try {
      return new URL(url).hostname;
    } catch {
      return url;
    }
  }

  /**
   * Debounced refresh when the user switches tabs while the Download panel is open.
   */
  function scheduleExtractPreviewRefresh() {
    if (activeMainTab !== "download") {
      return;
    }
    if (extractPreviewRefreshTimer) {
      clearTimeout(extractPreviewRefreshTimer);
    }
    extractPreviewRefreshTimer = setTimeout(() => {
      extractPreviewRefreshTimer = null;
      void loadExtractPreview();
    }, 120);
  }

  chrome.tabs.onActivated.addListener(scheduleExtractPreviewRefresh);
  chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
    if (changeInfo.url || changeInfo.status === "complete") {
      scheduleExtractPreviewRefresh();
    }
  });

  /**
   * @param {Array<object>} assets
   */
  function renderSmartEduAssetChecklist(assets) {
    if (!smarteduAssetList) {
      return;
    }
    smarteduAssetList.textContent = "";
    previewSmartEduAssets = assets.map((a) => ({ ...a, selected: a.selected !== false }));
    previewSmartEduAssets.forEach((asset, idx) => {
      const label = document.createElement("label");
      label.className = "field-row-checkbox";
      const box = document.createElement("input");
      box.type = "checkbox";
      box.checked = asset.selected !== false;
      box.dataset.assetIndex = String(idx);
      box.addEventListener("change", () => {
        previewSmartEduAssets[idx].selected = box.checked;
      });
      const span = document.createElement("span");
      span.className = "field-row-label";
      span.textContent = asset.title || asset.alias || `Asset ${idx + 1}`;
      label.appendChild(box);
      label.appendChild(span);
      smarteduAssetList.appendChild(label);
    });
  }

  /**
   * @param {boolean} visible
   */
  function setDownloadProgressVisible(visible) {
    if (!downloadProgressWrap) {
      return;
    }
    downloadProgressWrap.hidden = !visible;
    if (!visible && downloadProgressFill) {
      downloadProgressFill.style.width = "0%";
      downloadProgressFill.classList.remove("is-active");
    }
  }

  /**
   * Show extract UI when the active tab matches a known host (not generic-only).
   * @returns {Promise<void>}
   */
  async function loadExtractPreview() {
    if (!docExtractSection || !docExtractDetected || !btnExtractDocument) {
      return;
    }
    if (smarteduPanel) {
      smarteduPanel.hidden = true;
    }
    if (docExtractPages) {
      docExtractPages.hidden = true;
    }
    if (downloadUnsupported) {
      downloadUnsupported.hidden = true;
    }
    if (docExtractActiveTab) {
      docExtractActiveTab.textContent = "";
    }
    docExtractSection.hidden = true;
    const tab = await getActiveContentTab();
    if (!tab?.id || !tab.url || MindGraphShared.isRestrictedTabUrl(tab.url)) {
      if (downloadUnsupported) {
        downloadUnsupported.hidden = false;
      }
      return;
    }
    const preview = await new Promise((resolve) => {
      chrome.runtime.sendMessage(
        { type: "PREVIEW_EXTRACT", pageUrl: tab.url, tabId: tab.id },
        (res) => {
          void chrome.runtime.lastError;
          resolve(res || { host: { id: "generic" } });
        },
      );
    });
    const host = preview.host || { id: "generic", label: "网页", engine: "dom-article" };
    const resolvedPageUrl = preview.pageUrl || tab.url || "";
    if (host.id === "generic") {
      if (downloadUnsupported) {
        downloadUnsupported.hidden = false;
      }
      return;
    }
    docExtractDetected.textContent = t("docExtractDetectedSite", [host.label]);
    if (docExtractActiveTab) {
      docExtractActiveTab.textContent = t("docExtractActiveTab", [hostnameFromUrl(resolvedPageUrl)]);
    }
    if (docExtractTitle) {
      docExtractTitle.textContent = preview.title || tab.title || "";
    }
    if (
      docExtractPages &&
      typeof preview.pageCount === "number" &&
      preview.pageCount > 0 &&
      (host.engine === "canvas-pdf" || host.engine === "html2canvas-pdf")
    ) {
      docExtractPages.textContent = t("docExtractPageCount", [String(preview.pageCount)]);
      docExtractPages.hidden = false;
    } else if (docExtractPages && host.prep && host.prep.includes("autoscroll")) {
      docExtractPages.textContent = t("docExtractScrollHint");
      docExtractPages.hidden = false;
    }
    if (host.id === "smartedu" && smarteduPanel) {
      smarteduPanel.hidden = false;
      if (smarteduTokenStatus) {
        smarteduTokenStatus.textContent = preview.smarteduTokenSet
          ? t("smarteduTokenConnected")
          : t("smarteduTokenMissing");
      }
      const docAssets = Array.isArray(preview.assets)
        ? preview.assets.filter((asset) => asset.localKind !== "m3u8" && asset.alias !== "micro_lesson_video")
        : [];
      if (docAssets.length) {
        renderSmartEduAssetChecklist(docAssets);
      }
    }
    docExtractSection.hidden = false;
  }

  if (btnSyncSmartEduToken) {
    btnSyncSmartEduToken.addEventListener("click", () => {
      void (async () => {
        const tab = await getActiveContentTab();
        if (smarteduTokenStatus) {
          smarteduTokenStatus.textContent = t("smarteduTokenSyncing");
        }
        const response = await new Promise((resolve) => {
          chrome.runtime.sendMessage(
            { type: "SYNC_SMARTEDU_TOKEN", tabId: tab?.id },
            (res) => {
              void chrome.runtime.lastError;
              resolve(res || { ok: false, tokenSet: false });
            },
          );
        });
        if (response.tokenSet) {
          await loadExtractPreview();
          return;
        }
        if (smarteduTokenStatus) {
          smarteduTokenStatus.textContent = t("smarteduTokenMissing");
        }
      })();
    });
  }

  if (btnPasteSmartEduToken) {
    btnPasteSmartEduToken.addEventListener("click", () => {
      void (async () => {
        const token = window.prompt(t("smarteduPasteTokenPrompt"), "");
        if (!token || !token.trim()) {
          return;
        }
        await new Promise((resolve) => {
          chrome.runtime.sendMessage({ type: "SAVE_SMARTEDU_TOKEN", token: token.trim() }, (res) => {
            void chrome.runtime.lastError;
            resolve(res);
          });
        });
        await loadExtractPreview();
      })();
    });
  }

  if (btnExtractDocument) {
    btnExtractDocument.addEventListener("click", () => {
      void (async () => {
        if (downloadStatusEl) {
          setStatus(downloadStatusEl, "", "");
        }
        setDownloadProgressVisible(true);
        if (downloadProgressStage) {
          downloadProgressStage.textContent = t("statusWorking");
        }
        btnExtractDocument.disabled = true;
        setMainTabsDisabled(true);

        const tab = await getActiveContentTab();
        if (!tab?.id) {
          if (downloadStatusEl) {
            setStatus(downloadStatusEl, t("errNoTab"), "err");
          }
          setDownloadProgressVisible(false);
          btnExtractDocument.disabled = false;
          setMainTabsDisabled(false);
          return;
        }

        const stored = await MindGraphExtensionStorage.getSmartEduTokenIfFresh();
        const portName = `doc-extract-${tab.id}`;
        let port;
        let completed = false;
        try {
          port = chrome.runtime.connect({ name: portName });
        } catch (e) {
          if (downloadStatusEl) {
            setStatus(downloadStatusEl, t("errPortDisconnected"), "err");
          }
          setDownloadProgressVisible(false);
          btnExtractDocument.disabled = false;
          setMainTabsDisabled(false);
          return;
        }

        const finish = (result) => {
          if (completed) {
            return;
          }
          completed = true;
          setDownloadProgressVisible(false);
          if (downloadStatusEl) {
            if (result.ok) {
              const noticeText =
                result.notice && t(result.notice, result.noticeArgs || [])
                  ? t(result.notice, result.noticeArgs || [])
                  : null;
              setStatus(downloadStatusEl, noticeText || t("statusExtractDownloadStarted"), "ok");
            } else {
              setStatus(downloadStatusEl, userFacingError(result.error), "err");
            }
          }
          btnExtractDocument.disabled = false;
          setMainTabsDisabled(false);
        };

        port.onMessage.addListener((msg) => {
          if (!msg) {
            return;
          }
          if (msg.type === "extractProgress" && typeof msg.stage === "string") {
            setDownloadExtractProgressStage(msg.stage);
          } else if (msg.type === "extractResult") {
            finish(msg);
          }
        });
        port.onDisconnect.addListener(() => {
          if (!completed) {
            finish({ ok: false, error: "errPortDisconnected" });
          }
        });

        const startPayload = {
          type: "start",
          smarteduToken: stored || "",
        };
        if (previewSmartEduAssets.length) {
          startPayload.smarteduAssets = previewSmartEduAssets.filter((a) => a.selected !== false);
        }
        port.postMessage(startPayload);
      })();
    });
  }

  if (btnSaveFileCenter && fieldPackage) {
    btnSaveFileCenter.addEventListener("click", () => {
      void (async () => {
        const packageId = parseInt(fieldPackage.value, 10);
        if (!Number.isFinite(packageId)) {
          return;
        }
        setStatus(statusEl, t("statusWorking"), "loading");
        btnSaveFileCenter.disabled = true;
        try {
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (!tab?.id) {
            setStatus(statusEl, t("errNoTab"), "err");
            return;
          }
          const response = await new Promise((resolve) => {
            chrome.runtime.sendMessage(
              { type: "SAVE_TO_FILE_CENTER", tabId: tab.id, packageId },
              (res) => {
                void chrome.runtime.lastError;
                resolve(res || { ok: false, error: t("errFailed") });
              },
            );
          });
          if (response.ok) {
            setStatus(statusEl, t("statusSavedToFileCenter"), "ok");
          } else {
            console.error("[MindGraph] save to file center failed", response.error);
            setStatus(statusEl, response.error || t("errFailed"), "err");
          }
        } catch (e) {
          setStatus(statusEl, e?.message || String(e), "err");
        } finally {
          btnSaveFileCenter.disabled = false;
        }
      })();
    });
  }

  btnGenerate.addEventListener("click", () => {
    void (async () => {
      setStatus(statusEl, "", "");
      if (linkViewDiagram) {
        linkViewDiagram.hidden = true;
        linkViewDiagram.removeAttribute("data-href");
        linkViewDiagram.removeAttribute("data-diagram-id");
        linkViewDiagram.removeAttribute("data-base-url-preset");
        linkViewDiagram.href = "#";
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
      setMainTabsDisabled(true);

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
            if (linkViewDiagram && msg.diagramId && typeof msg.diagramId === "string") {
              const presetId =
                typeof msg.baseUrlPresetId === "string" ? msg.baseUrlPresetId : fieldBaseUrl.value;
              const resolved = MindGraphShared.resolveMindGraphSettings({
                baseUrlPresetId: presetId,
              });
              const diagramUrl =
                (typeof msg.diagramUrl === "string" && msg.diagramUrl) ||
                MindGraphShared.buildCanvasDiagramUrl(resolved.baseUrl, msg.diagramId);
              if (diagramUrl) {
                linkViewDiagram.href = diagramUrl;
                linkViewDiagram.setAttribute("data-href", diagramUrl);
                linkViewDiagram.setAttribute("data-diagram-id", msg.diagramId);
                linkViewDiagram.setAttribute("data-base-url-preset", resolved.presetId);
                linkViewDiagram.textContent = t("linkViewInLibrary");
                linkViewDiagram.hidden = false;
              }
            } else if (linkViewDiagram && msg.diagramUrl && typeof msg.diagramUrl === "string") {
              linkViewDiagram.href = msg.diagramUrl;
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
          setMainTabsDisabled(false);
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
        setMainTabsDisabled(false);
      };

      let tab;
      try {
        [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      } catch (e) {
        console.error("[MindGraph] tabs.query", e);
        setProgressVisible(false);
        setStatus(statusEl, e?.message || String(e), "err");
        btnGenerate.disabled = false;
        setMainTabsDisabled(false);
        return;
      }
      if (!tab?.id) {
        setProgressVisible(false);
        setStatus(statusEl, t("errNoTab"), "err");
        btnGenerate.disabled = false;
        setMainTabsDisabled(false);
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
        setMainTabsDisabled(false);
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
