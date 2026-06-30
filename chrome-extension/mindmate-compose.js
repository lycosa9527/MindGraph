/**
 * Compose MindMate first message with optional web page markdown context.
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};
  const API_MESSAGE_MAX_LEN = 5000;

  /**
   * @param {string | null} conversationId
   * @param {number} userMessageCount
   * @returns {boolean}
   */
  function shouldAttachPageContext(conversationId, userMessageCount) {
    return !conversationId && userMessageCount === 0;
  }

  /**
   * @param {string} intro
   * @param {string} meta
   * @param {string} questionLine
   * @param {string} userText
   * @returns {number}
   */
  function computeMarkdownBudget(intro, meta, questionLine, userText) {
    const overhead = intro.length + meta.length + questionLine.length + userText.length + 12;
    return Math.max(400, API_MESSAGE_MAX_LEN - overhead);
  }

  /**
   * @param {string} markdown
   * @param {number} maxLen
   * @returns {string}
   */
  function truncateMarkdownForBudget(markdown, maxLen) {
    const text = (markdown || "").trim();
    if (!text || text.length <= maxLen) {
      return text;
    }
    return `${text.slice(0, Math.max(0, maxLen - 20)).trim()}\n\n…`;
  }

  /**
   * @param {(key: string, subs?: string[]) => string} t
   * @param {string} userText
   * @param {{ title?: string, url?: string, markdown?: string }} pageCtx
   * @returns {string}
   */
  function buildFirstMessageWithPageContext(t, userText, pageCtx) {
    const title = (pageCtx && pageCtx.title) || "";
    const url = (pageCtx && pageCtx.url) || "";
    const intro = t("mindmatePageContextIntro");
    const meta = t("mindmatePageContextMeta", [title, url]);
    const questionLine = t("mindmatePageContextQuestion", [userText]);
    const budget = computeMarkdownBudget(intro, meta, questionLine, userText);
    const markdown = truncateMarkdownForBudget(pageCtx && pageCtx.markdown, budget);
    const parts = [intro, "", meta, "", "---", "", markdown, "", "---", "", questionLine];
    const composed = parts.join("\n").trim();
    if (composed.length <= API_MESSAGE_MAX_LEN) {
      return composed;
    }
    return composed.slice(0, API_MESSAGE_MAX_LEN);
  }

  MindGraphMindMate.API_MESSAGE_MAX_LEN = API_MESSAGE_MAX_LEN;
  MindGraphMindMate.shouldAttachPageContext = shouldAttachPageContext;
  MindGraphMindMate.computeMarkdownBudget = computeMarkdownBudget;
  MindGraphMindMate.truncateMarkdownForBudget = truncateMarkdownForBudget;
  MindGraphMindMate.buildFirstMessageWithPageContext = buildFirstMessageWithPageContext;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
