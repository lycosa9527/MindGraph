/**
 * Map extract engine errors to i18n keys — plain language for popup + notifications.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /** @type {Record<string, string>} */
  const EXACT_CODES = {
    CANVAS_EMPTY: "errExtractNoPages",
    HTML2CANVAS_EMPTY: "errExtractNoPages",
    NO_IMAGES: "errExtractNoPages",
    DOM_ARTICLE_EMPTY: "errExtractNoText",
    PREP_NOT_LOADED: "errExtractRetry",
    COLLECT_NOT_LOADED: "errExtractRetry",
    SMARTEDU_NO_ASSETS: "errExtractSmartEduNoFiles",
    SMARTEDU_URL_INVALID: "errExtractWrongPage",
    WENKU_API_TIER_MISS: "errExtractWenkuNoPreview",
    API_BINARY_UNSUPPORTED_HOST: "errExtractWrongPage",
    CNKI_CAPTCHA: "errExtractCnkiCaptcha",
    CNKI_LOGIN_REQUIRED: "errExtractLoginRequired",
    CNKI_PDF_URL_MISS: "errExtractNoPages",
    CNKI_RESOLVE_NOT_LOADED: "errExtractRetry",
  };

  /**
   * @param {string} message
   * @param {object | undefined} hostEntry
   * @returns {string}
   */
  function resolveExtractErrorKey(message, hostEntry) {
    const msg = (message || "").trim();
    if (!msg) {
      return "errExtractFailed";
    }
    if (msg.startsWith("err")) {
      return msg;
    }
    if (EXACT_CODES[msg]) {
      return EXACT_CODES[msg];
    }
    if (/SmartEdu metadata HTTP/i.test(msg)) {
      return "errExtractSmartEduLogin";
    }
    if (/SmartEdu download HTTP/i.test(msg)) {
      return "errExtractSmartEduDownload";
    }
    if (/SmartEdu video download is not supported/i.test(msg)) {
      return "errExtractSmartEduVideoUnsupported";
    }
    if (/BINARY_HTTP_401|BINARY_HTTP_403/i.test(msg)) {
      return "errExtractLoginRequired";
    }
    if (/BINARY_HTTP_/i.test(msg)) {
      return "errExtractDownloadBlocked";
    }
    const hostId = hostEntry && hostEntry.id;
    if (hostId === "wenku" && /EMPTY|NO_IMAGES|CANVAS/i.test(msg)) {
      return "errExtractWenkuNoPreview";
    }
    if (hostId === "cnki") {
      if (/CAPTCHA/i.test(msg)) {
        return "errExtractCnkiCaptcha";
      }
      if (/LOGIN|401|403/i.test(msg)) {
        return "errExtractLoginRequired";
      }
      if (/EMPTY|NO_IMAGES|CANVAS|PDF_URL_MISS/i.test(msg)) {
        return "errExtractNoPages";
      }
      return "errExtractFailed";
    }
    if (hostId === "smartedu") {
      return "errExtractSmartEduDownload";
    }
    return "errExtractFailed";
  }

  MindGraphDocExtract.resolveExtractErrorKey = resolveExtractErrorKey;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
