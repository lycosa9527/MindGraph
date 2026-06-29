/**
 * SmartEdu auth token helpers — mirrors file_reader/smartedu/token_store.py.
 * Keep X-ND-AUTH header shape in sync with the file-reader SmartEdu tab.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

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

  /**
   * Injected into SmartEdu tab — reads ND_UC_AUTH localStorage keys.
   * @returns {{ accessToken: string | null, rawKey: string | null }}
   */
  function readSmartEduTokenFromPage() {
    let rawKey = null;
    let accessToken = null;
    try {
      for (let i = 0; i < localStorage.length; i += 1) {
        const key = localStorage.key(i);
        if (!key || !key.startsWith("ND_UC_AUTH")) {
          continue;
        }
        rawKey = key;
        const raw = localStorage.getItem(key);
        if (!raw) {
          continue;
        }
        try {
          const parsed = JSON.parse(raw);
          if (parsed && typeof parsed.access_token === "string" && parsed.access_token.trim()) {
            accessToken = parsed.access_token.trim();
            break;
          }
        } catch {
          if (raw.trim()) {
            accessToken = raw.trim();
            break;
          }
        }
      }
    } catch {
      /* localStorage blocked */
    }
    return { accessToken, rawKey };
  }

  MindGraphDocExtract.buildSmartEduAuthHeaders = buildSmartEduAuthHeaders;
  MindGraphDocExtract.appendAccessTokenQuery = appendAccessTokenQuery;
  MindGraphDocExtract.readSmartEduTokenFromPage = readSmartEduTokenFromPage;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
