/**
 * User-facing MindMate page capture progress (popup reads via session storage).
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};
  const SESSION_KEY = "mindmateCaptureProgress";

  /** @type {object | null} */
  let memoryProgress = null;

  /**
   * @returns {Promise<object>}
   */
  async function getCaptureProgress() {
    if (memoryProgress) {
      return memoryProgress;
    }
    try {
      const data = await chrome.storage.session.get(SESSION_KEY);
      const stored = data[SESSION_KEY];
      if (stored && typeof stored === "object") {
        memoryProgress = stored;
        return stored;
      }
    } catch {
      return { phase: "idle" };
    }
    return { phase: "idle" };
  }

  /**
   * @param {Record<string, unknown>} patch
   * @returns {Promise<object>}
   */
  async function publishCaptureProgress(patch) {
    const prev = await getCaptureProgress();
    const next = {
      ...prev,
      ...patch,
      updatedAt: Date.now(),
    };
    memoryProgress = next;
    try {
      await chrome.storage.session.set({ [SESSION_KEY]: next });
    } catch {
      /* session unavailable in tests */
    }
    return next;
  }

  /**
   * @returns {Promise<void>}
   */
  async function clearCaptureProgress() {
    memoryProgress = { phase: "idle", updatedAt: Date.now() };
    try {
      await chrome.storage.session.remove(SESSION_KEY);
    } catch {
      /* ignore */
    }
  }

  /**
   * @param {{ hostId?: string, pageUrl?: string, tabId?: number }} context
   * @returns {Promise<object>}
   */
  async function beginCaptureProgress(context) {
    return publishCaptureProgress({
      phase: "reading",
      hostId: context.hostId || "",
      pageUrl: context.pageUrl || "",
      tabId: context.tabId || 0,
      messageKey: "mindmatePageContextReading",
      messageSubs: [],
      errorKey: "",
      source: "",
      title: "",
      markdownLen: 0,
      assetTotal: 0,
      assetDone: 0,
      assetTitle: "",
    });
  }

  /**
   * @param {{ ok: boolean, error?: string, source?: string, title?: string, markdownLen?: number, fromSelection?: boolean, hostId?: string, pageUrl?: string, assetTotal?: number }} result
   * @returns {Promise<object>}
   */
  async function finishCaptureProgress(result) {
    if (result.ok) {
      let messageKey = "mindmatePageContextReady";
      /** @type {string[]} */
      let messageSubs = [String(result.title || ""), String(result.markdownLen || 0)];
      if (result.source === "smartedu-pdf") {
        messageKey = "mindmatePageContextSmarteduReady";
        messageSubs = [
          String(result.assetTotal || 0),
          String(result.markdownLen || 0),
          String(result.title || ""),
        ];
      } else if (result.fromSelection) {
        messageKey = "mindmatePageContextReadySelection";
        messageSubs = [String(result.title || ""), String(result.markdownLen || 0)];
      } else if (result.source === "wenku-pdf") {
        messageKey = "mindmatePageContextReadyWenku";
      } else if (result.source === "cnki-pdf") {
        messageKey = "mindmatePageContextReadyCnki";
      }
      return publishCaptureProgress({
        phase: "ready",
        ok: true,
        hostId: result.hostId || "",
        pageUrl: result.pageUrl || "",
        errorKey: "",
        source: result.source || "",
        title: result.title || "",
        markdownLen: result.markdownLen || 0,
        assetTotal: result.assetTotal || 0,
        assetDone: result.assetTotal || 0,
        messageKey,
        messageSubs,
      });
    }
    return publishCaptureProgress({
      phase: "error",
      ok: false,
      hostId: result.hostId || "",
      pageUrl: result.pageUrl || "",
      errorKey: result.error || "errMindMatePageEmpty",
      messageKey: result.error || "errMindMatePageEmpty",
      messageSubs: [],
      markdownLen: 0,
    });
  }

  /**
   * @param {(key: string, substitutions?: string[]) => string} t
   * @param {object | null | undefined} progress
   * @returns {string}
   */
  function formatCaptureProgressMessage(t, progress) {
    if (!progress || progress.phase === "idle") {
      return "";
    }
    if (progress.messageKey && typeof t === "function") {
      const subs = progress.messageSubs;
      if (Array.isArray(subs) && subs.length > 0) {
        return t(progress.messageKey, subs);
      }
      return t(progress.messageKey);
    }
    if (progress.errorKey && typeof t === "function") {
      return t(progress.errorKey);
    }
    return "";
  }

  /**
   * @param {(key: string, substitutions?: string[]) => string} t
   * @param {{ title?: string, markdown?: string, source?: string, fromSelection?: boolean, assetTotal?: number }} ctx
   * @returns {string}
   */
  function formatCachedPageContextNotice(t, ctx) {
    if (!ctx || !ctx.markdown) {
      return "";
    }
    const markdownLen = ctx.markdown.length;
    if (ctx.source === "smartedu-pdf") {
      return t("mindmatePageContextSmarteduReady", [
        String(ctx.assetTotal || 0),
        String(markdownLen),
        String(ctx.title || ""),
      ]);
    }
    if (ctx.fromSelection) {
      return t("mindmatePageContextReadySelection", [
        String(ctx.title || ""),
        String(markdownLen),
      ]);
    }
    if (ctx.source === "wenku-pdf") {
      return t("mindmatePageContextReadyWenku", [String(ctx.title || ""), String(markdownLen)]);
    }
    if (ctx.source === "cnki-pdf") {
      return t("mindmatePageContextReadyCnki", [String(ctx.title || ""), String(markdownLen)]);
    }
    return t("mindmatePageContextReady", [String(ctx.title || ""), String(markdownLen)]);
  }

  MindGraphMindMate.captureProgress = {
    getCaptureProgress,
    publishCaptureProgress,
    clearCaptureProgress,
    beginCaptureProgress,
    finishCaptureProgress,
    formatCaptureProgressMessage,
    formatCachedPageContextNotice,
  };
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
