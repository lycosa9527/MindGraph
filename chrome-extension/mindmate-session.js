/**
 * MindMate thread persistence for chrome.storage.session (survives popup close).
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};
  const SESSION_THREAD_KEY = "mindmateThread";
  const SESSION_PAGE_CONTEXT_KEY = "mindmatePageContext";

  /**
   * @param {unknown} raw
   * @returns {{ authKey: string, conversationId: string | null, userMessageCount: number, messages: Array<{ id: string, role: "user" | "assistant", text: string }> }}
   */
  function parseStoredThread(raw) {
    if (!raw || typeof raw !== "object") {
      return { authKey: "", conversationId: null, userMessageCount: 0, messages: [] };
    }
    const obj = raw;
    const authKey = typeof obj.authKey === "string" ? obj.authKey : "";
    const conversationId = typeof obj.conversationId === "string" ? obj.conversationId : null;
    const userMessageCount = typeof obj.userMessageCount === "number" ? obj.userMessageCount : 0;
    const messages = Array.isArray(obj.messages)
      ? obj.messages.filter(
          (m) =>
            m &&
            typeof m === "object" &&
            typeof m.id === "string" &&
            (m.role === "user" || m.role === "assistant") &&
            typeof m.text === "string",
        )
      : [];
    return { authKey, conversationId, userMessageCount, messages };
  }

  /**
   * @param {string} authKey
   * @param {string | null} conversationId
   * @param {number} userMessageCount
   * @param {Array<{ id: string, role: "user" | "assistant", text: string }>} messages
   * @returns {object}
   */
  function buildStoredThread(authKey, conversationId, userMessageCount, messages) {
    return {
      authKey: authKey || "",
      conversationId: conversationId || null,
      userMessageCount,
      messages: messages.map((m) => ({
        id: m.id,
        role: m.role,
        text: m.text,
      })),
    };
  }

  /**
   * @param {string | undefined} expectedAuthKey
   * @returns {Promise<{ authKey: string, conversationId: string | null, userMessageCount: number, messages: Array<{ id: string, role: "user" | "assistant", text: string }> }>}
   */
  async function loadThreadFromSession(expectedAuthKey) {
    const data = await chrome.storage.session.get(SESSION_THREAD_KEY);
    const thread = parseStoredThread(data[SESSION_THREAD_KEY]);
    if (
      expectedAuthKey &&
      thread.authKey &&
      thread.authKey !== expectedAuthKey
    ) {
      await clearThreadSession();
      return parseStoredThread(null);
    }
    if (
      expectedAuthKey &&
      !thread.authKey &&
      (thread.messages.length > 0 || thread.conversationId)
    ) {
      await clearThreadSession();
      return parseStoredThread(null);
    }
    return thread;
  }

  /**
   * @param {string} authKey
   * @param {string | null} conversationId
   * @param {number} userMessageCount
   * @param {Array<{ id: string, role: "user" | "assistant", text: string }>} messages
   * @returns {Promise<void>}
   */
  async function saveThreadToSession(authKey, conversationId, userMessageCount, messages) {
    await chrome.storage.session.set({
      [SESSION_THREAD_KEY]: buildStoredThread(authKey, conversationId, userMessageCount, messages),
    });
  }

  /**
   * @returns {Promise<void>}
   */
  async function clearThreadSession() {
    await chrome.storage.session.remove(SESSION_THREAD_KEY);
  }

  /**
   * @param {unknown} raw
   * @param {string | undefined} expectedAuthKey
   * @returns {{ authKey: string, tabId: number, url: string, title: string, markdown: string, fromSelection?: boolean, source?: string, hostId?: string, assetTotal?: number } | null}
   */
  function parseStoredPageContext(raw, expectedAuthKey) {
    if (!raw || typeof raw !== "object") {
      return null;
    }
    const obj = raw;
    const authKey = typeof obj.authKey === "string" ? obj.authKey : "";
    if (expectedAuthKey && authKey && authKey !== expectedAuthKey) {
      return null;
    }
    if (expectedAuthKey && !authKey) {
      return null;
    }
    const url = typeof obj.url === "string" ? obj.url : "";
    const markdown = typeof obj.markdown === "string" ? obj.markdown : "";
    if (!url || !markdown.trim()) {
      return null;
    }
    return {
      authKey,
      tabId: typeof obj.tabId === "number" ? obj.tabId : 0,
      url,
      title: typeof obj.title === "string" ? obj.title : "",
      markdown,
      fromSelection: Boolean(obj.fromSelection),
      source: typeof obj.source === "string" ? obj.source : "",
      hostId: typeof obj.hostId === "string" ? obj.hostId : "",
      assetTotal: typeof obj.assetTotal === "number" ? obj.assetTotal : 0,
    };
  }

  /**
   * @param {string | undefined} expectedAuthKey
   * @returns {Promise<{ authKey: string, tabId: number, url: string, title: string, markdown: string, fromSelection?: boolean, source?: string, hostId?: string, assetTotal?: number } | null>}
   */
  async function loadPageContextFromSession(expectedAuthKey) {
    const data = await chrome.storage.session.get(SESSION_PAGE_CONTEXT_KEY);
    return parseStoredPageContext(data[SESSION_PAGE_CONTEXT_KEY], expectedAuthKey);
  }

  /**
   * @param {string} authKey
   * @param {{ tabId: number, url: string, title: string, markdown: string, fromSelection?: boolean, source?: string, hostId?: string, assetTotal?: number }} ctx
   * @returns {Promise<void>}
   */
  async function savePageContextToSession(authKey, ctx) {
    await chrome.storage.session.set({
      [SESSION_PAGE_CONTEXT_KEY]: {
        authKey: authKey || "",
        tabId: ctx.tabId,
        url: ctx.url,
        title: ctx.title,
        markdown: ctx.markdown,
        fromSelection: Boolean(ctx.fromSelection),
        source: typeof ctx.source === "string" ? ctx.source : "",
        hostId: typeof ctx.hostId === "string" ? ctx.hostId : "",
        assetTotal: typeof ctx.assetTotal === "number" ? ctx.assetTotal : 0,
      },
    });
  }

  /**
   * @returns {Promise<void>}
   */
  async function clearPageContextSession() {
    await chrome.storage.session.remove(SESSION_PAGE_CONTEXT_KEY);
  }

  MindGraphMindMate.SESSION_THREAD_KEY = SESSION_THREAD_KEY;
  MindGraphMindMate.SESSION_PAGE_CONTEXT_KEY = SESSION_PAGE_CONTEXT_KEY;
  MindGraphMindMate.parseStoredThread = parseStoredThread;
  MindGraphMindMate.buildStoredThread = buildStoredThread;
  MindGraphMindMate.loadThreadFromSession = loadThreadFromSession;
  MindGraphMindMate.saveThreadToSession = saveThreadToSession;
  MindGraphMindMate.clearThreadSession = clearThreadSession;
  MindGraphMindMate.parseStoredPageContext = parseStoredPageContext;
  MindGraphMindMate.loadPageContextFromSession = loadPageContextFromSession;
  MindGraphMindMate.savePageContextToSession = savePageContextToSession;
  MindGraphMindMate.clearPageContextSession = clearPageContextSession;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
