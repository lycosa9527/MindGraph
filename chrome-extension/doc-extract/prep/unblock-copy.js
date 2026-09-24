/**
 * Copy-guard removal — unblock user-select before extract (prep step).
 * Injected into the page before extract.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractPrep = global.__MGDocExtractPrep || {};

  global.__MGDocExtractPrep.unblockCopyRestrictions = function unblockCopyRestrictions() {
    const style = document.createElement("style");
    style.textContent =
      "*{user-select:text !important;-webkit-user-select:text !important;" +
      "-moz-user-select:text !important;}body{user-select:text !important;}";
    document.documentElement.appendChild(style);
    document.oncopy = null;
    document.onselectstart = null;
    document.oncontextmenu = null;
    document.querySelectorAll("*").forEach((el) => {
      if (el instanceof HTMLElement) {
        el.oncopy = null;
        el.onselectstart = null;
        el.oncontextmenu = null;
        el.style.removeProperty("user-select");
      }
    });
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
