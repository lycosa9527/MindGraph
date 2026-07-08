/**
 * Per-tab job lock for MV3 service worker — prevents overlapping capture/download work.
 */
(function (global) {
  "use strict";

  const MindGraphExtensionJobs = global.MindGraphExtensionJobs || {};

  /** @type {Map<string, true>} */
  const tabLocks = new Map();

  /**
   * @param {number} tabId
   * @returns {boolean}
   */
  function isTabJobLocked(tabId) {
    if (!Number.isInteger(tabId) || tabId < 1) {
      return false;
    }
    return tabLocks.has(String(tabId));
  }

  /**
   * Run one async job per tab. Returns `{ ok: false, error: "errJobAlreadyRunning" }` when busy.
   * @template T
   * @param {number} tabId
   * @param {() => Promise<T>} fn
   * @returns {Promise<T | { ok: false, error: string }>}
   */
  async function withTabJobLock(tabId, fn) {
    if (!Number.isInteger(tabId) || tabId < 1) {
      return fn();
    }
    const key = String(tabId);
    if (tabLocks.has(key)) {
      return { ok: false, error: "errJobAlreadyRunning" };
    }
    tabLocks.set(key, true);
    try {
      return await fn();
    } finally {
      tabLocks.delete(key);
    }
  }

  /**
   * Test-only reset.
   * @returns {void}
   */
  function resetTabLocksForTests() {
    tabLocks.clear();
  }

  MindGraphExtensionJobs.isTabJobLocked = isTabJobLocked;
  MindGraphExtensionJobs.withTabJobLock = withTabJobLock;
  MindGraphExtensionJobs.resetTabLocksForTests = resetTabLocksForTests;
  global.MindGraphExtensionJobs = MindGraphExtensionJobs;
})(typeof self !== "undefined" ? self : globalThis);
