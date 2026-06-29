/**
 * Per-host element hide lists — 437609 bdwk_ele, docin_ele, book118_ele.
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
