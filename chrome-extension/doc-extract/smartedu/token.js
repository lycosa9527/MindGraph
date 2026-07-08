/**
 * SmartEdu auth token helpers — mirrors file_reader/smartedu/token_store.py.
 * Keep X-ND-AUTH header shape in sync with the file-reader SmartEdu tab.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MindGraphExtensionStorage = global.MindGraphExtensionStorage;
  const MindGraphExtensionSecurity = global.MindGraphExtensionSecurity;
  const TOKEN_READ_PAGE = "doc-extract/smartedu/token-read-page.js";
  const SMARTEDU_HOST_SUFFIX = "smartedu.cn";

  /**
   * Parse one ND_UC_AUTH localStorage / sessionStorage entry (tchMaterial-parser shape).
   * @param {string | null | undefined} raw
   * @returns {string | null}
   */
  function parseSmartEduAuthStorageValue(raw) {
    if (!raw || typeof raw !== "string") {
      return null;
    }
    const trimmed = raw.trim();
    if (!trimmed) {
      return null;
    }
    try {
      const outer = JSON.parse(trimmed);
      if (!outer || typeof outer !== "object") {
        return null;
      }
      if (typeof outer.access_token === "string" && outer.access_token.trim()) {
        return outer.access_token.trim();
      }
      if (typeof outer.value === "string" && outer.value.trim()) {
        try {
          const inner = JSON.parse(outer.value);
          if (inner && typeof inner.access_token === "string" && inner.access_token.trim()) {
            return inner.access_token.trim();
          }
        } catch {
          if (outer.value.trim()) {
            return outer.value.trim();
          }
        }
      }
    } catch {
      return trimmed;
    }
    return null;
  }

  /**
   * Injected into SmartEdu tab — reads ND_UC_AUTH storage keys.
   * @returns {{ accessToken: string | null, rawKey: string | null }}
   */
  function readSmartEduTokenFromPage() {
    let rawKey = null;
    let accessToken = null;
    const storages = [];
    if (typeof localStorage !== "undefined") {
      storages.push(localStorage);
    }
    if (typeof sessionStorage !== "undefined") {
      storages.push(sessionStorage);
    }
    for (const storage of storages) {
      try {
        for (let i = 0; i < storage.length; i += 1) {
          const key = storage.key(i);
          if (!key || !key.toUpperCase().includes("ND_UC_AUTH")) {
            continue;
          }
          rawKey = key;
          const token = parseSmartEduAuthStorageValue(storage.getItem(key));
          if (token) {
            accessToken = token;
            break;
          }
        }
      } catch {
        /* storage blocked */
      }
      if (accessToken) {
        break;
      }
    }
    return { accessToken, rawKey };
  }

  /**
   * @param {string} hostname
   * @returns {boolean}
   */
  function isSmartEduHostname(hostname) {
    const host = (hostname || "").toLowerCase();
    return host === SMARTEDU_HOST_SUFFIX || host.endsWith(`.${SMARTEDU_HOST_SUFFIX}`);
  }

  /**
   * @param {number} tabId
   * @returns {Promise<{ accessToken: string | null, rawKey: string | null } | null>}
   */
  async function readSmartEduTokenFromTabId(tabId) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: [TOKEN_READ_PAGE],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: () => {
        if (globalThis.__MGSmartEduTokenRead) {
          return globalThis.__MGSmartEduTokenRead();
        }
        return { accessToken: null, rawKey: null };
      },
    });
    return results && results[0] ? results[0].result : null;
  }

  /**
   * Scan the active tab first, then any open SmartEdu tab.
   * @param {number | undefined} preferredTabId
   * @returns {Promise<string | null>}
   */
  async function discoverSmartEduToken(preferredTabId) {
    const tabIds = [];
    if (typeof preferredTabId === "number" && preferredTabId > 0) {
      tabIds.push(preferredTabId);
    }
    const tabs = await chrome.tabs.query({});
    for (const tab of tabs) {
      if (!tab.id || !tab.url || tabIds.includes(tab.id)) {
        continue;
      }
      try {
        const parsed = new URL(tab.url);
        if (isSmartEduHostname(parsed.hostname)) {
          tabIds.push(tab.id);
        }
      } catch {
        /* ignore bad URLs */
      }
    }
    for (const tabId of tabIds) {
      try {
        const result = await readSmartEduTokenFromTabId(tabId);
        if (result && result.accessToken) {
          return result.accessToken;
        }
      } catch {
        /* restricted tab or injection blocked */
      }
    }
    return null;
  }

  /**
   * @param {string} token
   * @returns {Promise<void>}
   */
  async function persistSmartEduToken(token) {
    let parsed = null;
    if (MindGraphExtensionSecurity && typeof MindGraphExtensionSecurity.parseSmartEduToken === "function") {
      parsed = MindGraphExtensionSecurity.parseSmartEduToken(token);
    } else {
      parsed = typeof token === "string" ? token.trim() : "";
      if (!parsed) {
        parsed = null;
      }
    }
    if (!parsed) {
      return;
    }
    if (MindGraphExtensionStorage && typeof MindGraphExtensionStorage.persistSmartEduToken === "function") {
      await MindGraphExtensionStorage.persistSmartEduToken(parsed);
      return;
    }
    await chrome.storage.local.set({
      smarteduAccessToken: parsed,
      smarteduAccessTokenSyncedAt: Date.now(),
    });
  }

  /**
   * @returns {Promise<void>}
   */
  async function clearSmartEduToken() {
    if (MindGraphExtensionStorage && typeof MindGraphExtensionStorage.clearSmartEduToken === "function") {
      await MindGraphExtensionStorage.clearSmartEduToken();
      return;
    }
    await chrome.storage.local.remove(["smarteduAccessToken", "smarteduAccessTokenSyncedAt"]);
  }

  /**
   * @param {string | null | undefined} accessToken
   * @returns {Record<string, string>}
   */
  function buildSmartEduAuthHeaders(accessToken) {
    const token = (accessToken || "").trim();
    if (!token) {
      return {};
    }
    return {
      "X-ND-AUTH": `MAC id="${token}",nonce="0",mac="0"`,
    };
  }

  /**
   * Append accessToken query suffix (smartedu-dl-go pattern).
   * @param {string} url
   * @param {string | null | undefined} accessToken
   * @returns {string}
   */
  function appendAccessTokenQuery(url, accessToken) {
    const token = (accessToken || "").trim();
    if (!token) {
      return url;
    }
    const sep = url.includes("?") ? "&" : "?";
    return `${url}${sep}accessToken=${encodeURIComponent(token)}`;
  }

  MindGraphDocExtract.parseSmartEduAuthStorageValue = parseSmartEduAuthStorageValue;
  MindGraphDocExtract.readSmartEduTokenFromPage = readSmartEduTokenFromPage;
  MindGraphDocExtract.readSmartEduTokenFromTabId = readSmartEduTokenFromTabId;
  MindGraphDocExtract.discoverSmartEduToken = discoverSmartEduToken;
  MindGraphDocExtract.persistSmartEduToken = persistSmartEduToken;
  MindGraphDocExtract.clearSmartEduToken = clearSmartEduToken;
  MindGraphDocExtract.buildSmartEduAuthHeaders = buildSmartEduAuthHeaders;
  MindGraphDocExtract.appendAccessTokenQuery = appendAccessTokenQuery;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
