/**
 * Page-context SmartEdu token reader + passive sync to extension storage.
 * Keep parse logic in sync with doc-extract/smartedu/token.js (parseSmartEduAuthStorageValue).
 */
(function (global) {
  "use strict";

  /**
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
   * @returns {{ accessToken: string | null, rawKey: string | null }}
   */
  function syncTokenToExtension() {
    const result = readSmartEduTokenFromPage();
    if (
      result.accessToken &&
      typeof chrome !== "undefined" &&
      chrome.runtime &&
      typeof chrome.runtime.sendMessage === "function"
    ) {
      chrome.runtime.sendMessage({ type: "SAVE_SMARTEDU_TOKEN", token: result.accessToken });
    }
    return result;
  }

  global.__MGSmartEduTokenRead = readSmartEduTokenFromPage;

  if (typeof window !== "undefined" && typeof localStorage !== "undefined") {
    syncTokenToExtension();
    window.addEventListener("storage", (event) => {
      if (event.key && event.key.toUpperCase().includes("ND_UC_AUTH")) {
        syncTokenToExtension();
      }
    });
  }
})(typeof globalThis !== "undefined" ? globalThis : window);
