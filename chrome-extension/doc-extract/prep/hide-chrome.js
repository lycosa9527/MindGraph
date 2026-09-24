/**
 * Per-host element hide lists for canvas-pdf readers.
 * Injected into the page before extract.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractPrep = global.__MGDocExtractPrep || {};

  /**
   * @param {string[]} selectors
   */
  global.__MGDocExtractPrep.hideElements = function hideElements(selectors) {
    (selectors || []).forEach((sel) => {
      try {
        document.querySelectorAll(sel).forEach((el) => {
          el.style.setProperty("display", "none", "important");
        });
      } catch {
        /* invalid selector */
      }
    });
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
