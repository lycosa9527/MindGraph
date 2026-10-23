/**
 * Interface languages for the extension — 43 picker codes (web has 44;
 * Traditional Chinese / zh-tw is omitted from the extension).
 *
 * Chrome only accepts a fixed set of folders under _locales. Albanian, Afrikaans,
 * Azerbaijani, Sinhala, and Uzbek live in i18n/ and are loaded by this module.
 * Tagalog is Chrome's fil. Portuguese is pt_BR (pt_PT is a copy for browser match).
 */
(function (global) {
  "use strict";

  /**
   * @typedef {object} ExtensionUiLocale
   * @property {string} code
   * @property {string} nativeName
   * @property {string} intl
   * @property {string} prompt
   * @property {string} messages
   * @property {string | null} chrome
   * @property {boolean} rtl
   * @property {string[]} prefixes
   */

  /** @type {Array<[string, string, string, string, string, string | null, boolean, string[] | null]>} */
  const ROWS = [
    ["zh", "中文", "zh-CN", "zh", "_locales/zh_CN/messages.json", "zh_CN", false, ["zh", "zh-cn", "zh-hans", "zh-sg"]],
    ["en", "English", "en", "en", "_locales/en/messages.json", "en", false, ["en"]],
    ["es", "Español", "es", "es", "_locales/es/messages.json", "es", false, null],
    ["az", "Azərbaycan", "az-AZ", "az", "i18n/az/messages.json", null, false, null],
    ["th", "ไทย", "th", "th", "_locales/th/messages.json", "th", false, null],
    ["fr", "Français", "fr", "fr", "_locales/fr/messages.json", "fr", false, null],
    ["de", "Deutsch", "de", "de", "_locales/de/messages.json", "de", false, null],
    ["sq", "Shqip", "sq", "sq", "i18n/sq/messages.json", null, false, null],
    ["ja", "日本語", "ja", "ja", "_locales/ja/messages.json", "ja", false, null],
    ["ko", "한국어", "ko", "ko", "_locales/ko/messages.json", "ko", false, null],
    ["pt", "Português", "pt-BR", "pt", "_locales/pt_BR/messages.json", "pt_BR", false, ["pt"]],
    ["ru", "Русский", "ru", "ru", "_locales/ru/messages.json", "ru", false, null],
    ["ar", "العربية", "ar", "ar", "_locales/ar/messages.json", "ar", true, null],
    ["fa", "فارسی", "fa", "fa", "_locales/fa/messages.json", "fa", true, null],
    ["uz", "Oʻzbek", "uz-UZ", "uz", "i18n/uz/messages.json", null, false, null],
    ["nl", "Nederlands", "nl", "nl", "_locales/nl/messages.json", "nl", false, null],
    ["it", "Italiano", "it", "it", "_locales/it/messages.json", "it", false, null],
    ["hi", "हिन्दी", "hi", "hi", "_locales/hi/messages.json", "hi", false, null],
    ["si", "සිංහල", "si", "si", "i18n/si/messages.json", null, false, null],
    ["ta", "தமிழ்", "ta", "ta", "_locales/ta/messages.json", "ta", false, null],
    ["te", "తెలుగు", "te", "te", "_locales/te/messages.json", "te", false, null],
    ["kn", "ಕನ್ನಡ", "kn", "kn", "_locales/kn/messages.json", "kn", false, null],
    ["ml", "മലയാളം", "ml", "ml", "_locales/ml/messages.json", "ml", false, null],
    ["id", "Bahasa Indonesia", "id", "id", "_locales/id/messages.json", "id", false, null],
    ["tl", "Tagalog", "fil", "tl", "_locales/fil/messages.json", "fil", false, ["fil", "tl"]],
    ["vi", "Tiếng Việt", "vi", "vi", "_locales/vi/messages.json", "vi", false, null],
    ["tr", "Türkçe", "tr", "tr", "_locales/tr/messages.json", "tr", false, null],
    ["pl", "Polski", "pl", "pl", "_locales/pl/messages.json", "pl", false, null],
    ["uk", "Українська", "uk", "uk", "_locales/uk/messages.json", "uk", false, null],
    ["ms", "Bahasa Melayu", "ms", "ms", "_locales/ms/messages.json", "ms", false, null],
    ["af", "Afrikaans", "af", "af", "i18n/af/messages.json", null, false, null],
    ["no", "Norsk", "nb-NO", "no", "_locales/no/messages.json", "no", false, ["no", "nb", "nn"]],
    ["sv", "Svenska", "sv", "sv", "_locales/sv/messages.json", "sv", false, null],
    ["da", "Dansk", "da", "da", "_locales/da/messages.json", "da", false, null],
    ["fi", "Suomi", "fi", "fi", "_locales/fi/messages.json", "fi", false, null],
    ["cs", "Čeština", "cs", "cs", "_locales/cs/messages.json", "cs", false, null],
    ["sk", "Slovenčina", "sk", "sk", "_locales/sk/messages.json", "sk", false, null],
    ["ro", "Română", "ro", "ro", "_locales/ro/messages.json", "ro", false, null],
    ["hu", "Magyar", "hu", "hu", "_locales/hu/messages.json", "hu", false, null],
    ["el", "Ελληνικά", "el", "el", "_locales/el/messages.json", "el", false, null],
    ["bg", "Български", "bg", "bg", "_locales/bg/messages.json", "bg", false, null],
    ["hr", "Hrvatski", "hr", "hr", "_locales/hr/messages.json", "hr", false, null],
    ["sr", "Српски", "sr", "sr", "_locales/sr/messages.json", "sr", false, null],
  ];

  /** @type {ExtensionUiLocale[]} */
  const LOCALES = ROWS.map((row) => ({
    code: row[0],
    nativeName: row[1],
    intl: row[2],
    prompt: row[3],
    messages: row[4],
    chrome: row[5],
    rtl: row[6],
    prefixes: row[7] || [row[0]],
  }));

  /** @type {Record<string, ExtensionUiLocale>} */
  const BY_CODE = {};
  LOCALES.forEach((entry) => {
    BY_CODE[entry.code] = entry;
  });

  /** @type {Record<string, string> | null} */
  let override = null;
  /** @type {string} */
  let effective = "en";
  /** @type {string} */
  let loadedFor = "";
  /** @type {string} */
  let failedFor = "";
  /** @type {{ code: string, promise: Promise<Record<string, string> | null> } | null} */
  let pending = null;

  /**
   * @param {string | null | undefined} raw
   * @returns {string}
   */
  function normalizeUiLanguage(raw) {
    if (raw == null) {
      return "auto";
    }
    const text = String(raw).trim();
    if (!text || text.toLowerCase() === "auto") {
      return "auto";
    }
    const key = text.toLowerCase().replace(/_/g, "-");
    if (key === "zh-cn" || key === "zh-hans") {
      return "zh";
    }
    if (key === "zh-tw" || key === "zh-hk" || key === "zh-mo" || key === "zh-hant") {
      return "zh";
    }
    if (BY_CODE[key]) {
      return key;
    }
    return "auto";
  }

  /**
   * Longest browser-prefix match (e.g. pt before en for pt-PT).
   * @param {string | null | undefined} raw
   * @returns {string | null}
   */
  function matchUiLanguage(raw) {
    if (!raw || typeof raw !== "string") {
      return null;
    }
    const tag = raw.trim().toLowerCase().replace(/_/g, "-");
    if (!tag) {
      return null;
    }
    let best = null;
    let bestLen = -1;
    LOCALES.forEach((entry) => {
      entry.prefixes.forEach((prefix) => {
        const hit = tag === prefix || tag.startsWith(`${prefix}-`);
        if (hit && prefix.length > bestLen) {
          best = entry.code;
          bestLen = prefix.length;
        }
      });
    });
    return best;
  }

  /**
   * @param {string} code
   * @returns {ExtensionUiLocale | null}
   */
  function entryFor(code) {
    return BY_CODE[code] || null;
  }

  /**
   * @param {string} code
   * @returns {string | null}
   */
  function promptFor(code) {
    const entry = entryFor(code);
    return entry ? entry.prompt : null;
  }

  /**
   * @param {string} raw
   * @param {string[] | string | undefined} substitutions
   * @returns {string}
   */
  function applySubstitutions(raw, substitutions) {
    let text = String(raw);
    if (substitutions == null) {
      return text;
    }
    const list = Array.isArray(substitutions) ? substitutions : [substitutions];
    for (let i = 0; i < list.length; i += 1) {
      text = text.split(`$${i + 1}`).join(String(list[i]));
    }
    return text;
  }

  /**
   * @param {string} key
   * @param {string[] | string | undefined} substitutions
   * @returns {string}
   */
  function message(key, substitutions) {
    if (override && Object.prototype.hasOwnProperty.call(override, key)) {
      return applySubstitutions(override[key], substitutions);
    }
    if (typeof chrome !== "undefined" && chrome.i18n && typeof chrome.i18n.getMessage === "function") {
      return chrome.i18n.getMessage(key, substitutions) || key;
    }
    return key;
  }

  /**
   * @param {string} code
   * @returns {Promise<Record<string, string> | null>}
   */
  function fetchCatalog(code) {
    const entry = entryFor(code);
    if (!entry || typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.getURL) {
      return Promise.resolve(null);
    }
    const url = chrome.runtime.getURL(entry.messages);
    return fetch(url).then((res) => {
      if (!res.ok) {
        throw new Error(`locale ${code} ${res.status}`);
      }
      return res.json();
    }).then((data) => {
      /** @type {Record<string, string>} */
      const map = {};
      Object.keys(data || {}).forEach((key) => {
        const row = data[key];
        if (row && typeof row.message === "string") {
          map[key] = row.message;
        }
      });
      return map;
    });
  }

  /**
   * Load messages for the stored language, or the browser language when set to auto.
   * @returns {Promise<Record<string, string> | null>}
   */
  function ensureLoaded() {
    if (typeof chrome === "undefined" || !chrome.storage || !chrome.storage.local) {
      return Promise.resolve(override);
    }
    return chrome.storage.local.get("uiLanguage").then((data) => {
      const mode = normalizeUiLanguage(data && data.uiLanguage);
      const browser =
        chrome.i18n && typeof chrome.i18n.getUILanguage === "function"
          ? chrome.i18n.getUILanguage()
          : "en";
      const next = mode === "auto" ? matchUiLanguage(browser) || "en" : mode;
      if (loadedFor === next && override) {
        effective = next;
        return override;
      }
      if (failedFor === next) {
        effective = next;
        return null;
      }
      if (pending && pending.code === next) {
        return pending.promise;
      }
      const promise = fetchCatalog(next).then((map) => {
        override = map;
        loadedFor = next;
        failedFor = "";
        effective = next;
        return map;
      }).catch((err) => {
        console.error("[MindGraph] locale load failed", err);
        override = null;
        loadedFor = "";
        failedFor = next;
        effective = next;
        return null;
      }).finally(() => {
        if (pending && pending.promise === promise) {
          pending = null;
        }
      });
      pending = { code: next, promise };
      return promise;
    });
  }

  /**
   * @returns {string}
   */
  function effectiveCode() {
    return effective;
  }

  const MindGraphExtensionLocales = {
    LOCALES,
    normalizeUiLanguage,
    matchUiLanguage,
    entryFor,
    promptFor,
    message,
    ensureLoaded,
    effectiveCode,
    applySubstitutions,
  };

  if (global && typeof global === "object") {
    global.MindGraphExtensionLocales = MindGraphExtensionLocales;
  }
})(typeof self !== "undefined" ? self : typeof globalThis !== "undefined" ? globalThis : this);
