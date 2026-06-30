/**
 * MindMate chat panel for the extension popup.
 */
(function (global) {
  "use strict";

  const MindGraphShared = global.MindGraphShared;
  const MindGraphMindMate = global.MindGraphMindMate;
  const MindGraphExtensionStorage = global.MindGraphExtensionStorage;

  /**
   * @param {object} deps
   * @param {(key: string, substitutions?: string[]) => string} deps.t
   * @param {() => string} deps.newRequestId
   * @param {() => Promise<{ baseUrl: string, account: string, token: string }>} deps.getCredentials
   * @param {(disabled: boolean) => void} deps.setMainTabsDisabled
   * @param {(tab: string) => void} deps.switchMainTab
   * @param {() => Promise<number | null>} deps.getActiveTabId
   * @param {HTMLElement} deps.view
   * @param {HTMLElement} deps.setupHint
   * @param {HTMLElement} deps.chatWrap
   * @param {HTMLElement} deps.messagesEl
   * @param {HTMLTextAreaElement} deps.inputEl
   * @param {HTMLButtonElement} deps.btnSend
   * @param {HTMLButtonElement} deps.btnStop
   * @param {HTMLButtonElement} deps.btnNew
   * @param {HTMLAnchorElement} deps.linkWeb
   * @param {HTMLElement} deps.statusEl
   * @param {HTMLButtonElement} deps.btnGoSettings
   * @param {HTMLInputElement} [deps.includePageCheckbox]
   * @param {HTMLElement} [deps.pageContextNoticeEl]
   */
  function initMindMatePanel(deps) {
    if (
      !deps.view ||
      !deps.setupHint ||
      !deps.chatWrap ||
      !deps.messagesEl ||
      !deps.inputEl ||
      !deps.btnSend ||
      !deps.btnStop ||
      !deps.btnNew
    ) {
      return { onTabShown: () => {} };
    }
    /** @type {string | null} */
    let difyUserId = null;
    /** @type {string | null} */
    let conversationId = null;
    /** @type {AbortController | null} */
    let abortController = null;
    /** @type {boolean} */
    let streaming = false;
    /** @type {number} */
    let userMessageCount = 0;
    /** @type {string | null} */
    let streamingBubbleId = null;
    /** @type {string} */
    let authKey = "";
    /** @type {Array<{ id: string, role: "user" | "assistant", text: string }>} */
    let messages = [];
    /** @type {ReturnType<typeof setTimeout> | null} */
    let saveTimer = null;
    /** @type {{ tabId: number, url: string, title: string, markdown: string, fromSelection?: boolean, source?: string, assetTotal?: number } | null} */
    let cachedPageContext = null;
    /** @type {ReturnType<typeof setTimeout> | null} */
    let pagePrefetchTimer = null;
    /** @type {number} */
    let pagePrefetchGeneration = 0;

    function isIncludePageEnabled() {
      return Boolean(deps.includePageCheckbox && deps.includePageCheckbox.checked);
    }

    function updateIncludePageControl() {
      if (!deps.includePageCheckbox) {
        return;
      }
      const allowPageContext = MindGraphMindMate.shouldAttachPageContext(conversationId, userMessageCount);
      deps.includePageCheckbox.disabled = !allowPageContext || streaming;
      const label = deps.includePageCheckbox.closest(".mindmate-include-page");
      if (label) {
        label.classList.toggle("is-disabled", deps.includePageCheckbox.disabled);
      }
      updatePageContextNotice();
    }

    /**
     * @param {object | null | undefined} progress
     */
    function applyCaptureProgressToNotice(progress) {
      if (!deps.pageContextNoticeEl) {
        return;
      }
      const el = deps.pageContextNoticeEl;
      const prog = MindGraphMindMate.captureProgress;
      if (!isIncludePageEnabled()) {
        el.hidden = true;
        el.textContent = "";
        el.className = "mindmate-page-context-notice";
        return;
      }
      if (!MindGraphMindMate.shouldAttachPageContext(conversationId, userMessageCount)) {
        el.hidden = false;
        el.textContent = deps.t("mindmatePageContextNotFirstMessage");
        el.className = "mindmate-page-context-notice is-disabled";
        return;
      }
      let text = "";
      let phase = progress && progress.phase ? progress.phase : "idle";
      if (prog && progress) {
        text = prog.formatCaptureProgressMessage(deps.t, progress);
      }
      if (!text && cachedPageContext && cachedPageContext.markdown && prog) {
        text = prog.formatCachedPageContextNotice(deps.t, cachedPageContext);
        phase = "ready";
      }
      if (!text) {
        el.hidden = true;
        el.textContent = "";
        el.className = "mindmate-page-context-notice";
        return;
      }
      el.hidden = false;
      el.textContent = text;
      el.className = "mindmate-page-context-notice";
      if (
        phase === "reading" ||
        phase === "smartedu_detected" ||
        phase === "smartedu_download" ||
        phase === "smartedu_extract"
      ) {
        el.classList.add("is-loading");
      } else if (phase === "ready") {
        el.classList.add("is-ready");
      } else if (phase === "error") {
        el.classList.add("is-error");
      }
    }

    async function refreshPageContextNotice() {
      const prog = MindGraphMindMate.captureProgress;
      if (!prog) {
        applyCaptureProgressToNotice(null);
        return;
      }
      const progress = await prog.getCaptureProgress();
      applyCaptureProgressToNotice(progress);
    }

    function updatePageContextNotice() {
      void refreshPageContextNotice();
    }

    /**
     * @param {string} cachedUrl
     * @param {string} tabUrl
     * @returns {boolean}
     */
    function pageContextUrlsMatch(cachedUrl, tabUrl) {
      if (!cachedUrl || !tabUrl) {
        return false;
      }
      if (cachedUrl === tabUrl) {
        return true;
      }
      try {
        const left = new URL(cachedUrl);
        const right = new URL(tabUrl);
        if (left.hostname.toLowerCase() !== right.hostname.toLowerCase()) {
          return false;
        }
        const activityParam = ["activityId", "contentId", "resourceId"];
        for (const key of activityParam) {
          const leftId = left.searchParams.get(key);
          const rightId = right.searchParams.get(key);
          if (leftId && rightId && leftId === rightId) {
            return true;
          }
        }
      } catch {
        return false;
      }
      return false;
    }

    /**
     * @returns {Promise<{ smarteduToken?: string, maxMarkdownChars: number }>}
     */
    async function buildMindMateCaptureOptions() {
      const maxMarkdownChars =
        typeof MindGraphMindMate.API_MESSAGE_MAX_LEN === "number"
          ? MindGraphMindMate.API_MESSAGE_MAX_LEN
          : 5000;
      const options = { maxMarkdownChars };
      if (
        MindGraphExtensionStorage &&
        typeof MindGraphExtensionStorage.getSmartEduTokenIfFresh === "function"
      ) {
        const token = await MindGraphExtensionStorage.getSmartEduTokenIfFresh();
        if (token) {
          options.smarteduToken = token;
        }
      }
      return options;
    }

    /**
     * @param {number} tabId
     * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection?: boolean, source?: string } | { ok: false, error?: string }>}
     */
    function capturePageFromTab(tabId) {
      return new Promise((resolve) => {
        void buildMindMateCaptureOptions().then((captureOptions) => {
          chrome.runtime.sendMessage(
            {
              type: "CAPTURE_MINDMATE_PAGE",
              tabId,
              maxMarkdownChars: captureOptions.maxMarkdownChars,
              smarteduToken: captureOptions.smarteduToken,
            },
            (res) => {
              void chrome.runtime.lastError;
              resolve(res || { ok: false, error: "errMindMatePageCaptureFailed" });
            },
          );
        });
      });
    }

    async function prefetchPageContext() {
      if (!isIncludePageEnabled()) {
        return;
      }
      if (!MindGraphMindMate.shouldAttachPageContext(conversationId, userMessageCount)) {
        return;
      }
      if (deps.view.hidden) {
        return;
      }
      const tabId = deps.getActiveTabId ? await deps.getActiveTabId() : null;
      if (!tabId) {
        return;
      }
      const generation = pagePrefetchGeneration + 1;
      pagePrefetchGeneration = generation;
      const result = await capturePageFromTab(tabId);
      if (generation !== pagePrefetchGeneration) {
        return;
      }
      if (result.ok) {
        cachedPageContext = {
          tabId,
          url: result.url,
          title: result.title,
          markdown: result.markdown,
          fromSelection: result.fromSelection,
          source: result.source,
          assetTotal: result.assetTotal,
        };
        await MindGraphMindMate.savePageContextToSession(authKey, cachedPageContext);
        updatePageContextNotice();
        return;
      }
      cachedPageContext = null;
      await MindGraphMindMate.clearPageContextSession();
      updatePageContextNotice();
    }

    function schedulePagePrefetch() {
      if (deps.view.hidden || streaming) {
        return;
      }
      if (!isIncludePageEnabled()) {
        return;
      }
      if (!MindGraphMindMate.shouldAttachPageContext(conversationId, userMessageCount)) {
        return;
      }
      if (pagePrefetchTimer) {
        clearTimeout(pagePrefetchTimer);
      }
      pagePrefetchTimer = setTimeout(() => {
        pagePrefetchTimer = null;
        void prefetchPageContext();
      }, 150);
    }

    /**
     * @param {{ baseUrl: string, account: string }} creds
     * @returns {string}
     */
    function buildAuthKey(creds) {
      return MindGraphExtensionStorage.buildMindGraphAuthKey(creds.baseUrl, creds.account);
    }

    /**
     * @param {HTMLElement} bubble
     * @param {string} text
     * @param {"user" | "assistant"} role
     */
    function setBubbleContent(bubble, text, role) {
      if (MindGraphMindMate.applyMessageBubbleContent) {
        MindGraphMindMate.applyMessageBubbleContent(bubble, text, role);
        return;
      }
      bubble.textContent = text;
    }

    /**
     * @param {{ id: string, role: "user" | "assistant", text: string }} entry
     */
    function renderMessageRow(entry) {
      const row = document.createElement("div");
      row.className = `mindmate-msg mindmate-msg-${entry.role}`;
      row.dataset.msgId = entry.id;
      const bubble = document.createElement("div");
      bubble.className = "mindmate-msg-bubble";
      setBubbleContent(bubble, entry.text, entry.role);
      row.appendChild(bubble);
      deps.messagesEl.appendChild(row);
    }

    function renderAllMessages() {
      deps.messagesEl.textContent = "";
      for (const entry of messages) {
        renderMessageRow(entry);
      }
      deps.messagesEl.scrollTop = deps.messagesEl.scrollHeight;
    }

    /**
     * @param {string} text
     * @param {"user" | "assistant"} role
     * @returns {string}
     */
    function appendMessage(text, role) {
      const id = `mm-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const entry = { id, role, text };
      messages.push(entry);
      renderMessageRow(entry);
      deps.messagesEl.scrollTop = deps.messagesEl.scrollHeight;
      scheduleSaveThread();
      return id;
    }

    /**
     * @param {string} id
     * @param {string} text
     */
    function updateMessage(id, text) {
      const entry = messages.find((m) => m.id === id);
      if (entry) {
        entry.text = text;
      }
      const bubble = deps.messagesEl.querySelector(`[data-msg-id="${id}"] .mindmate-msg-bubble`);
      if (bubble && entry) {
        setBubbleContent(bubble, text, entry.role);
        deps.messagesEl.scrollTop = deps.messagesEl.scrollHeight;
      }
      scheduleSaveThread();
    }

    function clearMessages() {
      messages = [];
      deps.messagesEl.textContent = "";
    }

    function scheduleSaveThread() {
      if (saveTimer) {
        clearTimeout(saveTimer);
      }
      saveTimer = setTimeout(() => {
        saveTimer = null;
        void MindGraphMindMate.saveThreadToSession(authKey, conversationId, userMessageCount, messages);
      }, 200);
    }

    function flushSaveThread() {
      if (saveTimer) {
        clearTimeout(saveTimer);
        saveTimer = null;
      }
      return MindGraphMindMate.saveThreadToSession(authKey, conversationId, userMessageCount, messages);
    }

    function setStreamingUi(active) {
      streaming = active;
      deps.btnSend.hidden = active;
      deps.btnStop.hidden = !active;
      deps.inputEl.disabled = active;
      deps.btnNew.disabled = active;
      deps.setMainTabsDisabled(active);
      updateIncludePageControl();
    }

    function setStatus(text, kind) {
      if (!deps.statusEl) {
        return;
      }
      deps.statusEl.textContent = text || "";
      deps.statusEl.classList.remove("ok", "err", "is-loading");
      if (kind) {
        deps.statusEl.classList.add(kind);
      }
    }

    /**
     * @param {string} errorKey
     * @returns {Promise<void>}
     */
    async function setCaptureErrorStatus(errorKey) {
      const base = deps.t(errorKey);
      if (MindGraphMindMate.captureProgress) {
        await MindGraphMindMate.captureProgress.finishCaptureProgress({
          ok: false,
          error: errorKey,
        });
        updatePageContextNotice();
      }
      const dbg = MindGraphMindMate.captureDebug;
      if (!dbg) {
        setStatus(base, "err");
        return;
      }
      const hint = await dbg.formatLastCaptureHint();
      const payload = await dbg.getLastCaptureDebug();
      console.warn("[MindMate capture debug]", payload);
      if (hint) {
        setStatus(`${base}\n${deps.t("mindmateCaptureDebugHint")}: ${hint}`, "err");
        return;
      }
      setStatus(base, "err");
    }

    /**
     * @returns {Promise<{ baseUrl: string, account: string, token: string, requestId: string } | null>}
     */
    async function loadCredentials() {
      const creds = await deps.getCredentials();
      const baseUrl = (creds.baseUrl || "").trim();
      const account = (creds.account || "").trim();
      const token = (creds.token || "").trim();
      if (!baseUrl || !account || !token) {
        return null;
      }
      return {
        baseUrl,
        account,
        token,
        requestId: deps.newRequestId(),
      };
    }

    /** @type {boolean} */
    let authOk = false;

    function setChatEnabled(enabled) {
      authOk = enabled;
      deps.chatWrap.hidden = !enabled;
    }

    /**
     * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
     * @param {{ silent?: boolean }} [options]
     * @returns {Promise<boolean>}
     */
    async function ensureAuth(creds, options) {
      const silent = Boolean(options && options.silent);
      if (!silent) {
        setStatus(deps.t("statusVerifying"), "is-loading");
      }
      const auth = await MindGraphMindMate.verifyAuth(creds);
      if (!auth.ok) {
        difyUserId = null;
        setChatEnabled(false);
        setStatus(deps.t(auth.error), "err");
        return false;
      }
      if (silent && deps.statusEl && deps.statusEl.classList.contains("is-loading")) {
        setStatus("", "");
      }
      return true;
    }

    async function ensureDifyUser(creds) {
      const result = await MindGraphMindMate.fetchDifyUserId(creds);
      if (!result.ok) {
        difyUserId = null;
        setChatEnabled(false);
        setStatus(deps.t(result.error), "err");
        return false;
      }
      difyUserId = result.userId;
      setChatEnabled(true);
      setStatus("", "");
      return true;
    }

    async function restoreThreadFromSession(creds) {
      authKey = buildAuthKey(creds);
      await MindGraphExtensionStorage.removeLegacySessionKeys();
      const thread = await MindGraphMindMate.loadThreadFromSession(authKey);
      conversationId = thread.conversationId;
      userMessageCount = thread.userMessageCount;
      messages = thread.messages;
      renderAllMessages();
      cachedPageContext = await MindGraphMindMate.loadPageContextFromSession(authKey);
      updateIncludePageControl();
    }

    async function refreshPanelState() {
      const prefs = await chrome.storage.local.get("mindmateIncludePage");
      if (deps.includePageCheckbox) {
        deps.includePageCheckbox.checked = prefs.mindmateIncludePage !== false;
      }

      const creds = await loadCredentials();
      const configured = Boolean(creds);
      deps.setupHint.hidden = configured;
      setChatEnabled(false);
      if (creds && deps.linkWeb) {
        deps.linkWeb.href = MindGraphShared.resolveMindGraphBaseUrl(creds.baseUrl);
      }
      if (!configured) {
        difyUserId = null;
        authOk = false;
        setStatus("", "");
        return;
      }
      await restoreThreadFromSession(creds);
      if (!(await ensureAuth(creds, { silent: true }))) {
        return;
      }
      await ensureDifyUser(creds);
      updateIncludePageControl();
      if (isIncludePageEnabled()) {
        schedulePagePrefetch();
      }
    }

    /**
     * @param {string | null} id
     */
    async function persistConversationId(id) {
      conversationId = id;
      await flushSaveThread();
    }

    async function startNewChat() {
      if (streaming) {
        return;
      }
      const creds = await loadCredentials();
      if (!creds || !(await ensureAuth(creds))) {
        return;
      }
      if (!difyUserId && !(await ensureDifyUser(creds))) {
        return;
      }
      conversationId = null;
      userMessageCount = 0;
      authKey = buildAuthKey(creds);
      clearMessages();
      cachedPageContext = null;
      pagePrefetchGeneration += 1;
      if (MindGraphMindMate.captureProgress) {
        void MindGraphMindMate.captureProgress.clearCaptureProgress();
      }
      await MindGraphMindMate.clearThreadSession();
      await MindGraphMindMate.clearPageContextSession();
      await MindGraphExtensionStorage.removeLegacySessionKeys();
      setStatus(deps.t("mindmateNewChatStarted"), "ok");
      updateIncludePageControl();
      if (isIncludePageEnabled()) {
        schedulePagePrefetch();
      }
    }

    /**
     * @param {string} userText
     * @returns {Promise<{ ok: true, message: string } | { ok: false }>}
     */
    async function resolveApiMessage(userText) {
      if (!isIncludePageEnabled() || !MindGraphMindMate.shouldAttachPageContext(conversationId, userMessageCount)) {
        return { ok: true, message: userText };
      }
      let pageCtx = cachedPageContext;
      if (!pageCtx) {
        pageCtx = await MindGraphMindMate.loadPageContextFromSession(authKey);
      }
      const tabId = deps.getActiveTabId ? await deps.getActiveTabId() : null;
      if (tabId) {
        try {
          const tab = await chrome.tabs.get(tabId);
          const tabUrl = tab.url || "";
          if (pageCtx && pageContextUrlsMatch(pageCtx.url, tabUrl) && pageCtx.markdown) {
            return {
              ok: true,
              message: MindGraphMindMate.buildFirstMessageWithPageContext(deps.t, userText, pageCtx),
            };
          }
          const fresh = await capturePageFromTab(tabId);
          if (fresh.ok) {
            cachedPageContext = {
              tabId,
              url: fresh.url,
              title: fresh.title,
              markdown: fresh.markdown,
              fromSelection: fresh.fromSelection,
              source: fresh.source,
              assetTotal: fresh.assetTotal,
            };
            await MindGraphMindMate.savePageContextToSession(authKey, cachedPageContext);
            updatePageContextNotice();
            return {
              ok: true,
              message: MindGraphMindMate.buildFirstMessageWithPageContext(deps.t, userText, cachedPageContext),
            };
          }
          if (fresh.error) {
            await setCaptureErrorStatus(fresh.error);
            return { ok: false };
          }
        } catch {
          /* fall through */
        }
      }
      if (pageCtx && pageCtx.markdown) {
        return {
          ok: true,
          message: MindGraphMindMate.buildFirstMessageWithPageContext(deps.t, userText, pageCtx),
        };
      }
      await setCaptureErrorStatus("errMindMatePageEmpty");
      return { ok: false };
    }

    /**
     * @returns {Promise<void>}
     */
    async function revertFailedFirstSend() {
      if (conversationId || userMessageCount < 1) {
        return;
      }
      userMessageCount = 0;
      trimEmptyTailAssistant();
      while (messages.length > 0 && messages[messages.length - 1].role !== "user") {
        messages.pop();
      }
      if (messages.length > 0 && messages[messages.length - 1].role === "user") {
        messages.pop();
        const lastRow = deps.messagesEl.querySelector(".mindmate-msg:last-child");
        if (lastRow) {
          lastRow.remove();
        }
      }
      updateIncludePageControl();
      await flushSaveThread();
    }

    async function sendCurrentMessage() {
      const text = (deps.inputEl.value || "").trim();
      if (!text || streaming) {
        return;
      }
      const creds = await loadCredentials();
      if (!creds) {
        setStatus(deps.t("errMindMateNotConfigured"), "err");
        return;
      }
      if (!(await ensureAuth(creds))) {
        return;
      }
      if (!difyUserId && !(await ensureDifyUser(creds))) {
        return;
      }
      if (!authOk || !difyUserId) {
        setStatus(deps.t("errMindMateLoginExpired"), "err");
        return;
      }

      deps.inputEl.value = "";
      const resolved = await resolveApiMessage(text);
      if (!resolved.ok) {
        deps.inputEl.value = text;
        return;
      }

      appendMessage(text, "user");
      userMessageCount += 1;
      await flushSaveThread();
      updateIncludePageControl();

      abortController = new AbortController();
      setStreamingUi(true);
      setStatus(deps.t("mindmateStreaming"), "is-loading");

      let buffer = "";
      streamingBubbleId = appendMessage("", "assistant");

      const result = await MindGraphMindMate.streamMessage(creds, {
        message: resolved.message,
        userId: difyUserId,
        conversationId,
        signal: abortController.signal,
        onConversationId: (id) => {
          void persistConversationId(id);
        },
        onChunk: (chunk) => {
          buffer += chunk;
          if (streamingBubbleId) {
            updateMessage(streamingBubbleId, buffer);
          }
        },
        onReplace: (next) => {
          buffer = next;
          if (streamingBubbleId) {
            updateMessage(streamingBubbleId, buffer);
          }
        },
        onError: (message) => {
          const errText = message.startsWith("err") ? deps.t(message) : message;
          setStatus(errText, "err");
        },
      });

      streamingBubbleId = null;
      abortController = null;
      setStreamingUi(false);
      await flushSaveThread();

      if (!result.ok) {
        if (result.error === "errMindMateLoginExpired") {
          setChatEnabled(false);
          difyUserId = null;
        }
        await revertFailedFirstSend();
        setStatus(deps.t(result.error), "err");
        return;
      }

      if (result.conversationId && userMessageCount === 2) {
        const titleCreds = await loadCredentials();
        if (titleCreds) {
          setTimeout(() => {
            void MindGraphMindMate.autoGenerateConversationTitle(titleCreds, result.conversationId);
          }, 1000);
        }
      }

      setStatus("", "");
    }

    function trimEmptyTailAssistant() {
      while (messages.length > 0) {
        const last = messages[messages.length - 1];
        if (last.role === "assistant" && !last.text.trim()) {
          messages.pop();
          const row = deps.messagesEl.querySelector(`[data-msg-id="${last.id}"]`);
          if (row) {
            row.remove();
          }
        } else {
          break;
        }
      }
    }

    function stopStreaming() {
      if (abortController) {
        abortController.abort();
        abortController = null;
      }
      streamingBubbleId = null;
      trimEmptyTailAssistant();
      setStreamingUi(false);
      void flushSaveThread();
      setStatus(deps.t("mindmateStopped"), "");
    }

    deps.btnSend.addEventListener("click", () => {
      void sendCurrentMessage();
    });

    deps.btnStop.addEventListener("click", () => {
      stopStreaming();
    });

    deps.btnNew.addEventListener("click", () => {
      void startNewChat();
    });

    deps.inputEl.addEventListener("keydown", (ev) => {
      if (ev.key === "Enter" && !ev.shiftKey) {
        ev.preventDefault();
        void sendCurrentMessage();
      }
    });

    if (deps.btnGoSettings) {
      deps.btnGoSettings.addEventListener("click", () => {
        deps.switchMainTab("settings");
      });
    }

    if (deps.includePageCheckbox) {
      deps.includePageCheckbox.addEventListener("change", () => {
        void chrome.storage.local.set({ mindmateIncludePage: deps.includePageCheckbox.checked });
        if (deps.includePageCheckbox.checked) {
          schedulePagePrefetch();
          return;
        }
        pagePrefetchGeneration += 1;
        cachedPageContext = null;
        if (MindGraphMindMate.captureProgress) {
          void MindGraphMindMate.captureProgress.clearCaptureProgress();
        }
        void MindGraphMindMate.clearPageContextSession();
        updatePageContextNotice();
      });
    }

    if (typeof chrome !== "undefined" && chrome.storage && chrome.storage.onChanged) {
      chrome.storage.onChanged.addListener((changes, areaName) => {
        if (areaName !== "session" || !changes.mindmateCaptureProgress) {
          return;
        }
        if (!isIncludePageEnabled()) {
          return;
        }
        applyCaptureProgressToNotice(changes.mindmateCaptureProgress.newValue);
      });
    }

    chrome.tabs.onActivated.addListener(schedulePagePrefetch);
    chrome.tabs.onUpdated.addListener((_tabId, changeInfo) => {
      if (changeInfo.url || changeInfo.status === "complete") {
        schedulePagePrefetch();
      }
    });

    window.addEventListener("pagehide", () => {
      void flushSaveThread();
    });

    return {
      onTabShown: () => {
        void refreshPanelState();
      },
    };
  }

  MindGraphMindMate.initMindMatePanel = initMindMatePanel;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
