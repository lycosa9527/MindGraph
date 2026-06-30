/**
 * MindMate page-capture debug trace (service worker + popup).
 * Logs to console and keeps the last capture in chrome.storage.session.
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};
  const LOG_PREFIX = "[MindMate capture]";
  const SESSION_KEY = "mindmateCaptureDebug";
  const MAX_STEPS = 60;

  /** @type {{ id: string, startedAt: number, tabId?: number, pageUrl?: string, hostId?: string, steps: Array<{ at: number, step: string, message: string, data?: object }> } | null} */
  let activeCapture = null;

  /** @type {object | null} */
  let lastFinishedCapture = null;

  /**
   * @param {unknown} value
   * @returns {unknown}
   */
  function sanitizeDebugValue(value) {
    if (value == null || typeof value === "boolean" || typeof value === "number") {
      return value;
    }
    if (typeof value === "string") {
      if (/token|authorization|bearer|password|secret/i.test(value) && value.length > 12) {
        return `[redacted len=${value.length}]`;
      }
      return value.length > 240 ? `${value.slice(0, 240)}…` : value;
    }
    if (Array.isArray(value)) {
      return value.slice(0, 12).map((item) => sanitizeDebugValue(item));
    }
    if (typeof value === "object") {
      /** @type {Record<string, unknown>} */
      const out = {};
      for (const [key, raw] of Object.entries(value)) {
        if (/token|authorization|password|secret/i.test(key)) {
          out[key] = raw ? "[redacted]" : null;
          continue;
        }
        out[key] = sanitizeDebugValue(raw);
      }
      return out;
    }
    return String(value);
  }

  /**
   * @param {{ tabId?: number, pageUrl?: string, hostId?: string, fileFirst?: boolean }} context
   * @returns {string}
   */
  function beginCapture(context) {
    const id = `cap-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    activeCapture = {
      id,
      startedAt: Date.now(),
      tabId: context.tabId,
      pageUrl: context.pageUrl,
      hostId: context.hostId,
      steps: [],
    };
    log("begin", "capture started", {
      tabId: context.tabId,
      pageUrl: context.pageUrl,
      hostId: context.hostId,
      fileFirst: Boolean(context.fileFirst),
    });
    return id;
  }

  /**
   * @param {string} step
   * @param {string} message
   * @param {Record<string, unknown>} [data]
   */
  function log(step, message, data) {
    const entry = {
      at: Date.now(),
      step,
      message,
      data: data ? sanitizeDebugValue(data) : undefined,
    };
    if (activeCapture) {
      activeCapture.steps.push(entry);
      if (activeCapture.steps.length > MAX_STEPS) {
        activeCapture.steps.shift();
      }
    }
    if (data) {
      console.log(LOG_PREFIX, step, message, sanitizeDebugValue(data));
    } else {
      console.log(LOG_PREFIX, step, message);
    }
  }

  /**
   * @param {{ ok: boolean, error?: string, source?: string, markdownLen?: number, fromSelection?: boolean, hostId?: string, pageUrl?: string }} result
   * @returns {Promise<object>}
   */
  async function finishCapture(result) {
    const base = activeCapture || { id: "unknown", startedAt: Date.now(), steps: [] };
    const payload = {
      id: base.id,
      startedAt: base.startedAt,
      finishedAt: Date.now(),
      durationMs: Date.now() - base.startedAt,
      tabId: base.tabId,
      pageUrl: result.pageUrl || base.pageUrl || "",
      hostId: result.hostId || base.hostId || "",
      ok: Boolean(result.ok),
      error: result.error || "",
      source: result.source || "",
      markdownLen: typeof result.markdownLen === "number" ? result.markdownLen : 0,
      fromSelection: Boolean(result.fromSelection),
      steps: base.steps,
    };
    activeCapture = null;
    lastFinishedCapture = payload;
    try {
      await chrome.storage.session.set({ [SESSION_KEY]: payload });
    } catch {
      /* session may be unavailable in tests */
    }
    log("finish", result.ok ? "capture ok" : "capture failed", {
      error: payload.error,
      source: payload.source,
      markdownLen: payload.markdownLen,
      durationMs: payload.durationMs,
    });
    return payload;
  }

  /**
   * @returns {Promise<object | null>}
   */
  async function getLastCaptureDebug() {
    if (lastFinishedCapture) {
      return lastFinishedCapture;
    }
    try {
      const data = await chrome.storage.session.get(SESSION_KEY);
      const stored = data[SESSION_KEY];
      if (stored && typeof stored === "object") {
        lastFinishedCapture = stored;
        return stored;
      }
    } catch {
      return null;
    }
    return null;
  }

  /**
   * @returns {Promise<string>}
   */
  async function formatLastCaptureHint() {
    const payload = await getLastCaptureDebug();
    if (!payload || !Array.isArray(payload.steps) || payload.steps.length === 0) {
      return "";
    }
    const tail = payload.steps.slice(-4).map((entry) => {
      const step = entry && entry.step ? entry.step : "?";
      const message = entry && entry.message ? entry.message : "";
      return `${step}: ${message}`;
    });
    const meta = [];
    if (payload.hostId) {
      meta.push(`host=${payload.hostId}`);
    }
    if (payload.error) {
      meta.push(`err=${payload.error}`);
    }
    if (typeof payload.markdownLen === "number") {
      meta.push(`md=${payload.markdownLen}`);
    }
    const trace = tail.join(" → ");
    if (meta.length === 0) {
      return trace;
    }
    return `${meta.join(", ")} | ${trace}`;
  }

  /**
   * @returns {Promise<string>}
   */
  async function copyLastCaptureDebugJson() {
    const payload = await getLastCaptureDebug();
    if (!payload) {
      return "";
    }
    return JSON.stringify(payload, null, 2);
  }

  MindGraphMindMate.captureDebug = {
    beginCapture,
    log,
    finishCapture,
    getLastCaptureDebug,
    formatLastCaptureHint,
    copyLastCaptureDebugJson,
    sanitizeDebugValue,
  };
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
