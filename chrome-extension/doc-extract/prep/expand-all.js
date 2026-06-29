/**
 * Expand-all clicks — 437609 bdwk() 展开全文 / read-all pattern.
 * Injected into the page before extract.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractPrep = global.__MGDocExtractPrep || {};

  /**
   * @returns {number}
   */
  global.__MGDocExtractPrep.clickExpandAll = function clickExpandAll() {
    const patterns = [
      "展开全文",
      "阅读全文",
      "read all",
      "read more",
      "model-fold-show",
      "continue-read",
    ];
    let clicked = 0;
    document.querySelectorAll("a,button,span,div").forEach((el) => {
      const text = (el.textContent || "").trim().toLowerCase();
      if (!text) {
        return;
      }
      const hit = patterns.some((p) => text.includes(p.toLowerCase()));
      if (hit && el instanceof HTMLElement) {
        try {
          el.click();
          clicked += 1;
        } catch {
          /* ignore */
        }
      }
    });
    return clicked;
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
