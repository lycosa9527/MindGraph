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

  /** @type {readonly { id: string, url: string, labelKey: string }[]} */
  const BASE_URL_PRESETS = Object.freeze([
    { id: "production", url: "https://mg.mindspringedu.com", labelKey: "baseUrlPresetProduction" },
    { id: "test", url: "https://test.mindspringedu.com", labelKey: "baseUrlPresetTest" },
    { id: "local", url: "http://localhost:9527", labelKey: "baseUrlPresetLocal" },
  ]);

  /**
   * @returns {"edge" | "chrome" | "chromium"}
   */
  function detectExtensionBrowser() {
    const ua = (typeof navigator !== "undefined" && navigator.userAgent) || "";
    if (/Edg\//.test(ua)) {
      return "edge";
    }
    if (/Chrome\//.test(ua)) {
      return "chrome";
    }
    return "chromium";
  }

  /**
   * Server audit label — same extension build, Chrome or Edge host.
   * @returns {"chrome-extension" | "edge-extension"}
   */
  function mgClientHeader() {
    return detectExtensionBrowser() === "edge" ? "edge-extension" : "chrome-extension";
  }

  /**
   * Edge MV3: prefer offscreen blob URLs over service-worker createObjectURL.
   * @returns {boolean}
   */
  function preferOffscreenBlobUrls() {
    return detectExtensionBrowser() === "edge";
  }

  /**
   * @returns {boolean}
   */
  function offscreenApiAvailable() {
    if (typeof chrome !== "undefined" && chrome.offscreen && typeof chrome.offscreen.createDocument === "function") {
      return true;
    }
    if (global.browser && global.browser.offscreen && typeof global.browser.offscreen.createDocument === "function") {
      return true;
    }
    return false;
  }

  /**
   * @returns {boolean}
   */
  function isOffscreenDuplicateError(err) {
    const text = (err && err.message) || String(err || "");
    return /only a single|already exists|offscreen|OFFSCREEN|single offscreen/i.test(text);
  }

  function normalizeBaseUrl(url) {
    const trimmed = (url || "").trim().replace(/\/+$/, "");
    return trimmed;
  }

  /**
   * Resolve stored settings or preset id to the canonical API origin for one of the
   * three MindGraph servers (production, test, local).
   * @param {string | undefined} storedUrlOrPresetId
   * @returns {string}
   */
  function resolveMindGraphBaseUrl(storedUrlOrPresetId) {
    if (BASE_URL_PRESETS.some((entry) => entry.id === storedUrlOrPresetId)) {
      return baseUrlFromPresetId(storedUrlOrPresetId);
    }
    return baseUrlFromPresetId(resolveBaseUrlPresetId(storedUrlOrPresetId));
  }

  /**
   * @param {{ baseUrl?: string, baseUrlPresetId?: string } | null | undefined} settings
   * @returns {{ presetId: string, baseUrl: string }}
   */
  function resolveMindGraphSettings(settings) {
    const raw = settings && typeof settings === "object" ? settings : {};
    const presetFromStorage =
      typeof raw.baseUrlPresetId === "string" &&
      BASE_URL_PRESETS.some((entry) => entry.id === raw.baseUrlPresetId)
        ? raw.baseUrlPresetId
        : resolveBaseUrlPresetId(raw.baseUrl);
    return {
      presetId: presetFromStorage,
      baseUrl: baseUrlFromPresetId(presetFromStorage),
    };
  }

  /**
   * @param {string | undefined} baseUrl
   * @returns {string}
   */
  function ensureAbsoluteBaseUrl(baseUrl) {
    return resolveMindGraphBaseUrl(baseUrl);
  }

  /**
   * @param {Response} res
   * @returns {string | null}
   */
  function parseDiagramIdFromPngResponse(res) {
    const headerId = (res.headers.get("X-MG-Diagram-Id") || "").trim();
    if (headerId) {
      return headerId;
    }
    const disposition = res.headers.get("Content-Disposition") || "";
    const namedMatch = disposition.match(/filename="mindgraph-([^"]+)\.png"/i);
    if (namedMatch && namedMatch[1] && namedMatch[1] !== "web-content") {
      return namedMatch[1];
    }
    return null;
  }

  /**
   * @param {string | undefined} baseUrl
   * @param {string} diagramId
   * @returns {string | null}
   */
  function buildCanvasDiagramUrl(baseUrl, diagramId) {
    const id = (diagramId || "").trim();
    if (!id) {
      return null;
    }
    const origin = resolveMindGraphBaseUrl(baseUrl);
    return `${origin}/canvas?diagramId=${encodeURIComponent(id)}`;
  }

  /**
   * @param {string | undefined} presetId
   * @returns {string}
   */
  function baseUrlFromPresetId(presetId) {
    const preset = BASE_URL_PRESETS.find((entry) => entry.id === presetId);
    return preset ? preset.url : DEFAULT_MINDGRAPH_BASE_URL;
  }

  /**
   * @param {string | undefined} storedUrl
   * @returns {string}
   */
  function resolveBaseUrlPresetId(storedUrl) {
    if (BASE_URL_PRESETS.some((entry) => entry.id === storedUrl)) {
      return storedUrl;
    }
    const normalized = normalizeBaseUrl(storedUrl);
    if (!normalized) {
      return "production";
    }
    for (const preset of BASE_URL_PRESETS) {
      if (normalizeBaseUrl(preset.url) === normalized) {
        return preset.id;
      }
    }
    try {
      const withScheme = normalized.includes("://") ? normalized : `https://${normalized}`;
      const parsed = new URL(withScheme);
      if (
        (parsed.hostname === "localhost" || parsed.hostname === "127.0.0.1") &&
        (parsed.port === "9527" || parsed.port === "")
      ) {
        return "local";
      }
      for (const preset of BASE_URL_PRESETS) {
        if (new URL(preset.url).host === parsed.host) {
          return preset.id;
        }
      }
    } catch {
      /* ignore invalid URL */
    }
    return "production";
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
    BASE_URL_PRESETS,
    MINDMAP_GENERATE_PORT,
    normalizeBaseUrl,
    resolveMindGraphBaseUrl,
    resolveMindGraphSettings,
    ensureAbsoluteBaseUrl,
    parseDiagramIdFromPngResponse,
    buildCanvasDiagramUrl,
    baseUrlFromPresetId,
    resolveBaseUrlPresetId,
    sanitizeFilename,
    parseErrorDetailFromResponse,
    isRestrictedTabUrl,
    buildPngRequestBody,
    matchPromptLanguageCode,
    resolvePromptLanguageFromUiMode,
    detectExtensionBrowser,
    mgClientHeader,
    preferOffscreenBlobUrls,
    offscreenApiAvailable,
    isOffscreenDuplicateError,
  };
  if (global && typeof global === "object") {
    global.MindGraphShared = MindGraphShared;
  }
})(typeof self !== "undefined" ? self : typeof globalThis !== "undefined" ? globalThis : this);
