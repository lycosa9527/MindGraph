/**
 * Prep orchestrator — runs enabled prep steps from hosts.js config.
 */
(function (global) {
  "use strict";

  global.__MGDocExtractPrep = global.__MGDocExtractPrep || {};
  const prepApi = global.__MGDocExtractPrep;

  /**
   * @param {object} config
   * @returns {Promise<object>}
   */
  prepApi.runPrep = async function runPrep(config) {
    const steps = (config && config.prep) || [];
    if (steps.includes("unblock-copy") && prepApi.unblockCopyRestrictions) {
      prepApi.unblockCopyRestrictions();
    }
    if (steps.includes("hide-chrome") && prepApi.hideElements) {
      prepApi.hideElements((config && config.hideSelectors) || []);
    }
    if (steps.includes("expand-all") && prepApi.clickExpandAll) {
      prepApi.clickExpandAll();
    }
    if (steps.includes("autoscroll") && prepApi.autoScrollToBottom) {
      const stepMs = config && typeof config.autoscrollStepMs === "number" ? config.autoscrollStepMs : 500;
      const maxSteps =
        config && typeof config.autoscrollMaxSteps === "number" ? config.autoscrollMaxSteps : 120;
      await prepApi.autoScrollToBottom(stepMs, maxSteps);
    }
    return { ok: true };
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
