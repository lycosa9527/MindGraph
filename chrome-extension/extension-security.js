/**
 * Extension security helpers — sender validation and payload parsing.
 */
(function (global) {
  "use strict";

  const MindGraphExtensionSecurity = global.MindGraphExtensionSecurity || {};

  /** @type {number} */
  const SMARTEDU_TOKEN_MAX_LEN = 8192;

  /**
   * @param {chrome.runtime.MessageSender | undefined} sender
   * @returns {boolean}
   */
  function isExtensionSender(sender) {
    if (!sender || typeof sender.id !== "string") {
      return false;
    }
    return sender.id === chrome.runtime.id;
  }

  /**
   * @param {unknown} value
   * @returns {number | null}
   */
  function parsePositiveInt(value) {
    if (typeof value === "number" && Number.isInteger(value) && value > 0) {
      return value;
    }
    if (typeof value === "string" && /^\d+$/.test(value)) {
      const parsed = parseInt(value, 10);
      if (parsed > 0) {
        return parsed;
      }
    }
    return null;
  }

  /**
   * @param {unknown} value
   * @param {number} maxLen
   * @returns {string | null}
   */
  function parseBoundedToken(value, maxLen) {
    if (typeof value !== "string") {
      return null;
    }
    const trimmed = value.trim();
    if (!trimmed || trimmed.length > maxLen) {
      return null;
    }
    return trimmed;
  }

  /**
   * @param {unknown} value
   * @returns {string | null}
   */
  function parseSmartEduToken(value) {
    return parseBoundedToken(value, SMARTEDU_TOKEN_MAX_LEN);
  }

  MindGraphExtensionSecurity.isExtensionSender = isExtensionSender;
  MindGraphExtensionSecurity.parsePositiveInt = parsePositiveInt;
  MindGraphExtensionSecurity.parseBoundedToken = parseBoundedToken;
  MindGraphExtensionSecurity.parseSmartEduToken = parseSmartEduToken;
  MindGraphExtensionSecurity.SMARTEDU_TOKEN_MAX_LEN = SMARTEDU_TOKEN_MAX_LEN;
  global.MindGraphExtensionSecurity = MindGraphExtensionSecurity;
})(typeof self !== "undefined" ? self : globalThis);
