/**
 * Lazy-load autoscroll — 437609 ~500 ms scroll steps until bottom.
 * Injected into the page before extract.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractPrep = global.__MGDocExtractPrep || {};

  /**
   * @param {number} stepMs
   * @param {number} maxSteps
   * @returns {Promise<{ steps: number, height: number }>}
   */
  global.__MGDocExtractPrep.autoScrollToBottom = function autoScrollToBottom(stepMs, maxSteps) {
    const delay = typeof stepMs === "number" ? stepMs : 500;
    const limit = typeof maxSteps === "number" ? maxSteps : 120;
    return new Promise((resolve) => {
      let steps = 0;
      const tick = () => {
        steps += 1;
        window.scrollTo(0, document.body.scrollHeight);
        if (steps >= limit) {
          resolve({ steps, height: document.body.scrollHeight });
          return;
        }
        setTimeout(tick, delay);
      };
      tick();
    });
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
