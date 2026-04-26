/**
 * Shared helpers for MindGraph extension (service worker and popup).
 * @fileoverview URL normalization, PNG filename, HTTP error detail, and API body.
 */
(function (global) {
  "use strict";

  const MAX_PAGE_CHARS = 32000;
  const FETCH_TIMEOUT_MS = 180000;
  const VERIFY_TIMEOUT_MS = 60000;
  const DEFAULT_MINDGRAPH_BASE_URL = "https://mg.mindspringedu.com";
  const MINDMAP_GENERATE_PORT = "mindmap-generate";

  function normalizeBaseUrl(url) {
    const trimmed = (url || "").trim().replace(/\/+$/, "");
    return trimmed;
  }

  function sanitizeFilename(title) {
    const base = (title || "mindgraph").replace(/[<>:"/\\|?*\x00-\x1f]/g, "_").slice(0, 80);
    return base.endsWith(".png") ? base : `${base}.png`;
  }

  /**
   * @param {unknown} raw
   * @returns {string}
   */
  function formatDetailValue(raw) {
    if (raw === null || raw === undefined) {
      return "";
    }
    if (typeof raw === "string") {
      return raw;
    }
    if (Array.isArray(raw)) {
      return raw
        .map((item) => {
          if (item && typeof item === "object" && item.msg) {
            const loc = item.loc;
            if (Array.isArray(loc) && loc.length) {
              return `${loc.join(".")}: ${item.msg}`;
            }
            return String(item.msg);
          }
          return formatDetailValue(item);
        })
        .filter(Boolean)
        .join("; ");
    }
    try {
      return JSON.stringify(raw);
    } catch {
      return String(raw);
    }
  }

  /**
   * @param {Response} res
   * @returns {Promise<string>}
   */
  async function parseErrorDetailFromResponse(res) {
    const text = await res.text();
    let detail = text || res.statusText;
    if (text) {
      try {
        const errJson = JSON.parse(text);
        if (errJson && (errJson.detail !== undefined || errJson.message !== undefined)) {
          const raw = errJson.detail !== undefined ? errJson.detail : errJson.message;
          detail = formatDetailValue(raw) || (typeof raw === "string" ? raw : String(raw));
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
   * @param {object} payload
   * @param {object} [sizeOpts]
   * @param {number} [sizeOpts.pngWidth]
   * @param {number} [sizeOpts.pngHeight]
   * @returns {object}
   */
  /**
   * Map a BCP-47 / browser UI string to a server prompt language code.
   * @param {string|undefined} raw
   * @param {string[]} allowedCodes
   * @returns {string|null}
   */
  function matchPromptLanguageCode(raw, allowedCodes) {
    const allowedSet = new Set(allowedCodes);
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
  }

  /**
   * One setting for extension UI and mind map generation language.
   * @param {string|undefined} uiMode
   * @param {string|undefined} browserUiLang
   * @param {string[]} allowedCodes
   * @returns {string}
   */
  function resolvePromptLanguageFromUiMode(uiMode, browserUiLang, allowedCodes) {
    const mode = (uiMode || "auto").toString();
    const allowedSet = new Set(allowedCodes);
    if (mode === "en") {
      return allowedSet.has("en") ? "en" : "zh";
    }
    if (mode === "zh_CN") {
      return "zh";
    }
    if (mode === "zh_TW") {
      return allowedSet.has("zh-hant") ? "zh-hant" : "zh";
    }
    const fromBrowser = matchPromptLanguageCode(browserUiLang, allowedCodes);
    if (fromBrowser) {
      return fromBrowser;
    }
    return "zh";
  }

  function buildPngRequestBody(payload, sizeOpts) {
    const body = {
      page_content: payload.page_content,
      content_format: payload.content_format || "text/plain",
      page_title: payload.page_title || null,
      page_url: payload.page_url || null,
      language: payload.language || "zh",
    };
    if (!sizeOpts) {
      return body;
    }
    const w = sizeOpts.pngWidth;
    const h = sizeOpts.pngHeight;
    if (typeof w === "number" && w >= 400 && w <= 4000) {
      body.width = Math.round(w);
    }
    if (typeof h === "number" && h >= 300 && h <= 3000) {
      body.height = Math.round(h);
    }
    return body;
  }

  const MindGraphShared = {
    MAX_PAGE_CHARS,
    FETCH_TIMEOUT_MS,
    VERIFY_TIMEOUT_MS,
    DEFAULT_MINDGRAPH_BASE_URL,
    MINDMAP_GENERATE_PORT,
    normalizeBaseUrl,
    sanitizeFilename,
    parseErrorDetailFromResponse,
    isRestrictedTabUrl,
    buildPngRequestBody,
    matchPromptLanguageCode,
    resolvePromptLanguageFromUiMode,
  };
  if (global && typeof global === "object") {
    global.MindGraphShared = MindGraphShared;
  }
})(typeof self !== "undefined" ? self : typeof globalThis !== "undefined" ? globalThis : this);
