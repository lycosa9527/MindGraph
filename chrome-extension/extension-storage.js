/**
 * Extension storage hygiene — stale keys, auth fingerprints, install cleanup.
 */
(function (global) {
  "use strict";

  const MindGraphShared = global.MindGraphShared;
  const MindGraphExtensionStorage = global.MindGraphExtensionStorage || {};

  /** @type {string[]} */
  const LEGACY_SESSION_KEYS = ["mindmateConversationId"];

  /** @type {string} */
  const SMARTEDU_TOKEN_KEY = "smarteduAccessToken";

  /** @type {string} */
  const SMARTEDU_TOKEN_SYNCED_AT_KEY = "smarteduAccessTokenSyncedAt";

  /** SmartEdu ND_UC_AUTH tokens typically expire within ~7 days. */
  const SMARTEDU_TOKEN_MAX_AGE_MS = 8 * 24 * 60 * 60 * 1000;

  /**
   * @param {string | undefined} baseUrl
   * @param {string | undefined} account
   * @returns {string}
   */
  function buildMindGraphAuthKey(baseUrl, account) {
    const origin = MindGraphShared.normalizeBaseUrl(baseUrl || "");
    const acc = (account || "").trim();
    return `${origin}|${acc}`;
  }

  /**
   * @returns {Promise<void>}
   */
  async function removeLegacySessionKeys() {
    await chrome.storage.session.remove(LEGACY_SESSION_KEYS);
  }

  /** @type {string} */
  const MINDMATE_THREAD_KEY = "mindmateThread";

  /** @type {string} */
  const MINDMATE_PAGE_CONTEXT_KEY = "mindmatePageContext";

  /**
   * @returns {Promise<void>}
   */
  async function clearMindMateThread() {
    await chrome.storage.session.remove([MINDMATE_THREAD_KEY, MINDMATE_PAGE_CONTEXT_KEY, ...LEGACY_SESSION_KEYS]);
  }

  /**
   * Drop orphaned keys from older extension builds.
   * @returns {Promise<void>}
   */
  async function pruneStaleExtensionStorage() {
    await removeLegacySessionKeys();
  }

  /**
   * @param {number} status
   * @returns {boolean}
   */
  function isUnauthorizedHttpStatus(status) {
    return status === 401 || status === 403;
  }

  /**
   * @returns {Promise<void>}
   */
  async function clearSmartEduToken() {
    await chrome.storage.local.remove([SMARTEDU_TOKEN_KEY, SMARTEDU_TOKEN_SYNCED_AT_KEY]);
  }

  /**
   * @returns {Promise<string | null>}
   */
  async function getSmartEduTokenIfFresh() {
    const stored = await chrome.storage.local.get([SMARTEDU_TOKEN_KEY, SMARTEDU_TOKEN_SYNCED_AT_KEY]);
    const token = stored[SMARTEDU_TOKEN_KEY];
    if (!token || typeof token !== "string" || !token.trim()) {
      return null;
    }
    const syncedAt = stored[SMARTEDU_TOKEN_SYNCED_AT_KEY];
    if (typeof syncedAt === "number" && Date.now() - syncedAt > SMARTEDU_TOKEN_MAX_AGE_MS) {
      await clearSmartEduToken();
      return null;
    }
    return token.trim();
  }

  /**
   * @param {number} status
   * @returns {Promise<void>}
   */
  async function clearSmartEduTokenIfUnauthorized(status) {
    if (isUnauthorizedHttpStatus(status)) {
      await clearSmartEduToken();
    }
  }

  MindGraphExtensionStorage.buildMindGraphAuthKey = buildMindGraphAuthKey;
  MindGraphExtensionStorage.removeLegacySessionKeys = removeLegacySessionKeys;
  MindGraphExtensionStorage.clearMindMateThread = clearMindMateThread;
  MindGraphExtensionStorage.pruneStaleExtensionStorage = pruneStaleExtensionStorage;
  MindGraphExtensionStorage.isUnauthorizedHttpStatus = isUnauthorizedHttpStatus;
  MindGraphExtensionStorage.clearSmartEduToken = clearSmartEduToken;
  MindGraphExtensionStorage.getSmartEduTokenIfFresh = getSmartEduTokenIfFresh;
  MindGraphExtensionStorage.clearSmartEduTokenIfUnauthorized = clearSmartEduTokenIfUnauthorized;
  global.MindGraphExtensionStorage = MindGraphExtensionStorage;
})(typeof self !== "undefined" ? self : globalThis);
