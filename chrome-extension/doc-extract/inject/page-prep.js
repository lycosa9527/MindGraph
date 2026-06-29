/**
 * @deprecated Use doc-extract/prep/*.js injected in sequence (see extract-core.js).
 * Kept for manual debugging — aggregates all prep helpers in one file.
 */
(function (global) {
  "use strict";

  function hideElements(selectors) {
    (selectors || []).forEach((sel) => {
      try {
        document.querySelectorAll(sel).forEach((el) => {
          el.style.setProperty("display", "none", "important");
        });
      } catch {
        /* invalid selector */
      }
    });
  }

  function unblockCopyRestrictions() {
    const style = document.createElement("style");
    style.textContent =
      "*{user-select:text !important;-webkit-user-select:text !important;" +
      "-moz-user-select:text !important;}body{user-select:text !important;}";
    document.documentElement.appendChild(style);
    document.oncopy = null;
    document.onselectstart = null;
    document.oncontextmenu = null;
  }

  function clickExpandAll() {
    const patterns = ["展开全文", "阅读全文", "read all", "read more"];
    document.querySelectorAll("a,button,span,div").forEach((el) => {
      const text = (el.textContent || "").trim().toLowerCase();
      if (patterns.some((p) => text.includes(p)) && el instanceof HTMLElement) {
        try {
          el.click();
        } catch {
          /* ignore */
        }
      }
    });
  }

  function autoScrollToBottom(stepMs, maxSteps) {
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
  }

  async function runPrep(config) {
    const prep = (config && config.prep) || [];
    if (prep.includes("unblock-copy")) {
      unblockCopyRestrictions();
    }
    if (prep.includes("hide-chrome")) {
      hideElements((config && config.hideSelectors) || []);
    }
    if (prep.includes("expand-all")) {
      clickExpandAll();
    }
    if (prep.includes("autoscroll")) {
      await autoScrollToBottom(500, 120);
    }
    return { ok: true };
  }

  global.__MGDocExtractPrep = {
    runPrep,
    hideElements,
    unblockCopyRestrictions,
    clickExpandAll,
    autoScrollToBottom,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
