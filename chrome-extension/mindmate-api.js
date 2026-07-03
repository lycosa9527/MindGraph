/**
 * MindMate API client for the extension popup (Bearer auth, SSE streaming).
 */
(function (global) {
  "use strict";

  const MindGraphShared = global.MindGraphShared;
  const MindGraphMindMate = global.MindGraphMindMate || {};

  /**
   * @param {string} account
   * @param {string} token
   * @param {string} requestId
   * @returns {Record<string, string>}
   */
  function buildAuthHeaders(account, token, requestId) {
    return {
      Authorization: `Bearer ${token}`,
      "X-MG-Account": account,
      "X-MG-Client": MindGraphShared.mgClientHeader(),
      "X-Request-Id": requestId,
      "Content-Type": "application/json",
    };
  }

  /**
   * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
   * @returns {Promise<{ ok: true } | { ok: false, error: string }>}
   */
  async function verifyAuth(creds) {
    const origin = MindGraphShared.normalizeBaseUrl(creds.baseUrl);
    if (!origin || !creds.account || !creds.token) {
      return { ok: false, error: "errMindMateNotConfigured" };
    }
    const url = `${origin}/api/auth/me`;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), MindGraphShared.VERIFY_TIMEOUT_MS);
    try {
      const res = await fetch(url, MindGraphShared.mgatFetchInit({
        method: "GET",
        signal: controller.signal,
        headers: {
          Authorization: `Bearer ${creds.token}`,
          "X-MG-Account": creds.account,
          "X-MG-Client": MindGraphShared.mgClientHeader(),
          "X-Request-Id": creds.requestId,
        },
      }));
      clearTimeout(timeoutId);
      if (res.status === 401 || res.status === 403) {
        return { ok: false, error: "errMindMateLoginExpired" };
      }
      if (!res.ok) {
        return { ok: false, error: "errMindMateConnectFailed" };
      }
      return { ok: true };
    } catch (err) {
      clearTimeout(timeoutId);
      if (err && err.name === "AbortError") {
        return { ok: false, error: "errVerifyTimeout" };
      }
      return { ok: false, error: "errNetwork" };
    }
  }

  /**
   * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
   * @returns {Promise<{ ok: true, userId: string } | { ok: false, error: string }>}
   */
  async function fetchDifyUserId(creds) {
    const origin = MindGraphShared.normalizeBaseUrl(creds.baseUrl);
    if (!origin || !creds.account || !creds.token) {
      return { ok: false, error: "errMindMateNotConfigured" };
    }
    const url = `${origin}/api/dify/user-id`;
    try {
      const res = await fetch(url, MindGraphShared.mgatFetchInit({
        method: "GET",
        headers: {
          Authorization: `Bearer ${creds.token}`,
          "X-MG-Account": creds.account,
          "X-MG-Client": MindGraphShared.mgClientHeader(),
          "X-Request-Id": creds.requestId,
        },
      }));
      if (res.status === 401) {
        return { ok: false, error: "errMindMateLoginExpired" };
      }
      if (!res.ok) {
        return { ok: false, error: "errMindMateConnectFailed" };
      }
      const body = await res.json();
      const userId = body && typeof body.dify_user_id === "string" ? body.dify_user_id : "";
      if (!userId) {
        return { ok: false, error: "errMindMateConnectFailed" };
      }
      return { ok: true, userId };
    } catch {
      return { ok: false, error: "errNetwork" };
    }
  }

  /**
   * @param {Record<string, unknown>} payload
   * @returns {string}
   */
  function mapStreamErrorFromPayload(payload) {
    const errorType = typeof payload.error_type === "string" ? payload.error_type : "";
    if (errorType === "daily_token_cap") {
      return "errMindMateDailyTokenCap";
    }
    if (errorType === "thinking_coin_insufficient") {
      return "errMindMateThinkingCoins";
    }
    const serverText =
      (typeof payload.error === "string" && payload.error) ||
      (typeof payload.message === "string" && payload.message) ||
      "";
    if (serverText.startsWith("err")) {
      return serverText;
    }
    return "errMindMateStreamFailed";
  }

  /**
   * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
   * @param {{
   *   message: string,
   *   userId: string,
   *   conversationId: string | null,
   *   signal: AbortSignal,
   *   onConversationId?: (id: string) => void,
   *   onChunk?: (chunk: string) => void,
   *   onReplace?: (text: string) => void,
   *   onEnd?: (payload: Record<string, unknown>) => void,
   *   onError?: (message: string) => void,
   * }} options
   * @returns {Promise<{ ok: true, conversationId: string | null } | { ok: false, error: string }>}
   */
  async function streamMessage(creds, options) {
    const origin = MindGraphShared.normalizeBaseUrl(creds.baseUrl);
    const url = `${origin}/api/ai_assistant/stream`;
    let conversationId = options.conversationId;

    try {
      const res = await fetch(url, MindGraphShared.mgatFetchInit({
        method: "POST",
        headers: buildAuthHeaders(creds.account, creds.token, creds.requestId),
        body: JSON.stringify({
          message: options.message,
          user_id: options.userId,
          conversation_id: options.conversationId,
          auto_generate_name: true,
        }),
        signal: options.signal,
      }));

      if (res.status === 401) {
        return { ok: false, error: "errMindMateLoginExpired" };
      }
      if (res.status === 422) {
        return { ok: false, error: "errMindMateStreamFailed" };
      }
      if (!res.ok) {
        return { ok: false, error: "errMindMateStreamFailed" };
      }

      const reader = res.body && res.body.getReader ? res.body.getReader() : null;
      if (!reader) {
        return { ok: false, error: "errMindMateStreamFailed" };
      }

      let streamError = "";
      await MindGraphMindMate.consumeSseDataLines(
        reader,
        (payload) => {
          const event = payload.event;
          if (event === "message") {
            if (typeof payload.conversation_id === "string" && payload.conversation_id) {
              conversationId = payload.conversation_id;
              if (options.onConversationId) {
                options.onConversationId(payload.conversation_id);
              }
            }
            if (typeof payload.answer === "string" && payload.answer && options.onChunk) {
              options.onChunk(payload.answer);
            }
          } else if (event === "message_replace" && typeof payload.answer === "string") {
            if (options.onReplace) {
              options.onReplace(payload.answer);
            }
          } else if (event === "message_end") {
            if (typeof payload.conversation_id === "string" && payload.conversation_id) {
              conversationId = payload.conversation_id;
              if (options.onConversationId) {
                options.onConversationId(payload.conversation_id);
              }
            }
            if (options.onEnd) {
              options.onEnd(payload);
            }
          } else if (event === "error") {
            streamError = mapStreamErrorFromPayload(payload);
            if (options.onError) {
              options.onError(streamError);
            }
            return false;
          }
          return true;
        },
        options.signal,
      );

      if (streamError) {
        return { ok: false, error: streamError };
      }

      return { ok: true, conversationId };
    } catch (err) {
      if (err && err.name === "AbortError") {
        return { ok: true, conversationId };
      }
      return { ok: false, error: "errNetwork" };
    }
  }

  /**
   * @param {{ difyUser?: string, server?: number, mindbotConfigId?: number | null }} route
   * @returns {string}
   */
  function conversationRouteQuerySuffix(route) {
    const params = new URLSearchParams();
    const difyUser = route && typeof route.difyUser === "string" ? route.difyUser.trim() : "";
    if (difyUser) {
      params.set("dify_user", difyUser);
    }
    if (route && typeof route.server === "number" && route.server >= 1) {
      params.set("server", String(route.server));
    }
    if (route && typeof route.mindbotConfigId === "number" && route.mindbotConfigId >= 1) {
      params.set("mindbot_config_id", String(route.mindbotConfigId));
    }
    const query = params.toString();
    return query ? `&${query}` : "";
  }

  /**
   * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
   * @param {{ limit?: number }} [options]
   * @returns {Promise<{ ok: true, conversations: Array<object> } | { ok: false, error: string }>}
   */
  async function fetchConversations(creds, options) {
    const origin = MindGraphShared.normalizeBaseUrl(creds.baseUrl);
    if (!origin || !creds.account || !creds.token) {
      return { ok: false, error: "errMindMateNotConfigured" };
    }
    const limit = options && typeof options.limit === "number" ? options.limit : 50;
    const url = `${origin}/api/dify/conversations?limit=${limit}`;
    try {
      const res = await fetch(url, MindGraphShared.mgatFetchInit({
        method: "GET",
        headers: {
          Authorization: `Bearer ${creds.token}`,
          "X-MG-Account": creds.account,
          "X-MG-Client": MindGraphShared.mgClientHeader(),
          "X-Request-Id": creds.requestId,
        },
      }));
      if (res.status === 401) {
        return { ok: false, error: "errMindMateLoginExpired" };
      }
      if (!res.ok) {
        return { ok: false, error: "errMindMateConnectFailed" };
      }
      const body = await res.json();
      const rows = body && Array.isArray(body.data) ? body.data : [];
      return { ok: true, conversations: rows };
    } catch {
      return { ok: false, error: "errNetwork" };
    }
  }

  /**
   * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
   * @param {string} conversationId
   * @param {{ difyUser?: string, server?: number, mindbotConfigId?: number | null }} route
   * @returns {Promise<{ ok: true, messages: Array<object> } | { ok: false, error: string }>}
   */
  async function fetchConversationMessages(creds, conversationId, route) {
    const origin = MindGraphShared.normalizeBaseUrl(creds.baseUrl);
    if (!origin || !creds.account || !creds.token || !conversationId) {
      return { ok: false, error: "errMindMateNotConfigured" };
    }
    const suffix = conversationRouteQuerySuffix(route || {});
    const url = `${origin}/api/dify/conversations/${encodeURIComponent(conversationId)}/messages?limit=100${suffix}`;
    try {
      const res = await fetch(url, MindGraphShared.mgatFetchInit({
        method: "GET",
        headers: {
          Authorization: `Bearer ${creds.token}`,
          "X-MG-Account": creds.account,
          "X-MG-Client": MindGraphShared.mgClientHeader(),
          "X-Request-Id": creds.requestId,
        },
      }));
      if (res.status === 401) {
        return { ok: false, error: "errMindMateLoginExpired" };
      }
      if (!res.ok) {
        return { ok: false, error: "errMindMateConnectFailed" };
      }
      const body = await res.json();
      const rows = body && Array.isArray(body.data) ? body.data : [];
      return { ok: true, messages: rows };
    } catch {
      return { ok: false, error: "errNetwork" };
    }
  }

  /**
   * @param {Array<object>} apiMessages
   * @returns {Array<{ id: string, role: "user" | "assistant", text: string }>}
   */
  function panelMessagesFromApi(apiMessages) {
    /** @type {Array<{ id: string, role: "user" | "assistant", text: string }>} */
    const out = [];
    for (const row of apiMessages) {
      if (!row || typeof row !== "object") {
        continue;
      }
      const baseId = typeof row.id === "string" ? row.id : String(out.length);
      const query = typeof row.query === "string" ? row.query : "";
      const answer = typeof row.answer === "string" ? row.answer : typeof row.content === "string" ? row.content : "";
      if (query.trim()) {
        out.push({ id: `${baseId}-q`, role: "user", text: query });
      }
      if (answer.trim()) {
        out.push({ id: `${baseId}-a`, role: "assistant", text: answer });
      }
    }
    return out;
  }

  /**
   * @param {{ baseUrl: string, account: string, token: string, requestId: string }} creds
   * @param {string} conversationId
   * @returns {Promise<void>}
   */
  async function autoGenerateConversationTitle(creds, conversationId) {
    const origin = MindGraphShared.normalizeBaseUrl(creds.baseUrl);
    const url = `${origin}/api/dify/conversations/${encodeURIComponent(conversationId)}/name`;
    try {
      await fetch(url, MindGraphShared.mgatFetchInit({
        method: "POST",
        headers: buildAuthHeaders(creds.account, creds.token, creds.requestId),
        body: JSON.stringify({ auto_generate: true }),
      }));
    } catch {
      /* title generation is best-effort */
    }
  }

  MindGraphMindMate.buildAuthHeaders = buildAuthHeaders;
  MindGraphMindMate.verifyAuth = verifyAuth;
  MindGraphMindMate.fetchDifyUserId = fetchDifyUserId;
  MindGraphMindMate.conversationRouteQuerySuffix = conversationRouteQuerySuffix;
  MindGraphMindMate.fetchConversations = fetchConversations;
  MindGraphMindMate.fetchConversationMessages = fetchConversationMessages;
  MindGraphMindMate.panelMessagesFromApi = panelMessagesFromApi;
  MindGraphMindMate.mapStreamErrorFromPayload = mapStreamErrorFromPayload;
  MindGraphMindMate.streamMessage = streamMessage;
  MindGraphMindMate.autoGenerateConversationTitle = autoGenerateConversationTitle;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
