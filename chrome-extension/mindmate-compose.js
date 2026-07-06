/**
 * Compose MindMate first message with optional web page markdown context.
 * Structured for Dify MindMate workflow (teacher + thinking-development teaching).
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
   * @param {string[]} parts
   * @param {string} userText
   * @returns {number}
   */
  function computeMarkdownBudgetFromParts(parts, userText) {
    const overhead = parts.join("").length + userText.length + 12;
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

  const SOURCE_ALIASES = {
    "page-pdfjs": "page-markdown",
    "pdf-text-layer": "page-markdown",
    "pdf-text-layer-paged": "page-markdown",
    "plain-text": "page-markdown",
    "dom-fallback": "dom-article",
    "dom-markdown": "dom-article",
  };

  /**
   * @param {string | undefined} source
   * @returns {string}
   */
  function normalizeSourceCode(source) {
    const code = (source || "page-markdown").trim();
    return SOURCE_ALIASES[code] || code;
  }

  /**
   * @param {(key: string, subs?: string[]) => string} t
   * @param {string | undefined} source
   * @returns {string}
   */
  function formatPageContextSourceLabel(t, source) {
    const code = normalizeSourceCode(source);
    const key = `mindmatePageContextSource_${code.replace(/-/g, "_")}`;
    const label = t(key);
    if (label && label !== key) {
      return label;
    }
    return t("mindmatePageContextSource_page_markdown");
  }

  /**
   * @param {(key: string, subs?: string[]) => string} t
   * @param {string} userText
   * @param {{ title?: string, url?: string, markdown?: string, source?: string }} pageCtx
   * @returns {string}
   */
  function buildFirstMessageWithPageContext(t, userText, pageCtx) {
    const title = (pageCtx && pageCtx.title) || "";
    const url = (pageCtx && pageCtx.url) || "";
    const intro = t("mindmatePageContextIntro");
    const routing = t("mindmatePageContextRouting");
    const guidance = t("mindmatePageContextGuidance");
    const materialHeader = t("mindmatePageContextMaterialHeader");
    const questionLine = t("mindmatePageContextQuestion", [userText]);
    const sourceLabel = formatPageContextSourceLabel(t, pageCtx && pageCtx.source);
    const meta = t("mindmatePageContextMeta", [title, url, sourceLabel]);

    const budget = computeMarkdownBudgetFromParts(
      [intro, routing, guidance, meta, materialHeader, questionLine],
      userText,
    );
    const markdown = truncateMarkdownForBudget(pageCtx && pageCtx.markdown, budget);

    const parts = [
      intro,
      "",
      questionLine,
      "",
      routing,
      "",
      guidance,
      "",
      meta,
      "",
      materialHeader,
      "",
      markdown,
    ];
    const composed = parts.join("\n").trim();
    if (composed.length <= API_MESSAGE_MAX_LEN) {
      return composed;
    }
    return composed.slice(0, API_MESSAGE_MAX_LEN);
  }

  const MATERIAL_HEADER_MARKERS = [
    "**【参考材料：网页正文】**",
    "**【參考材料：網頁正文】**",
    "**[Reference material: page body]**",
  ];

  const PAGE_CONTEXT_INTRO_MARKERS = [
    "MindGraph extension · page context",
    "MindGraph 浏览器扩展 · 网页上下文",
    "MindGraph 瀏覽器擴充 · 網頁上下文",
  ];

  const USER_QUESTION_LINE_RES = [
    /^\*\*用户问题[^*]*\*\*\s*(.*)$/m,
    /^\*\*使用者問題[^*]*\*\*\s*(.*)$/m,
    /^\*\*User question[^*]*\*\*\s*(.*)$/im,
  ];

  /**
   * @param {string} text
   * @returns {boolean}
   */
  function isExtensionPageContextMessage(text) {
    if (MATERIAL_HEADER_MARKERS.some((marker) => text.includes(marker))) {
      return true;
    }
    return PAGE_CONTEXT_INTRO_MARKERS.some((marker) => text.includes(marker));
  }

  /**
   * @param {string} text
   * @returns {string | null}
   */
  function extractUserQuestionFromPageContext(text) {
    for (const pattern of USER_QUESTION_LINE_RES) {
      const match = pattern.exec(text);
      if (match && match[1]) {
        const question = match[1].trim();
        if (question) {
          return question;
        }
      }
    }
    return null;
  }

  /**
   * @param {string | null | undefined} query
   * @returns {string}
   */
  function displayUserMessageFromDifyQuery(query) {
    const text = (query || "").trim();
    if (!text || !isExtensionPageContextMessage(text)) {
      return query || "";
    }
    const question = extractUserQuestionFromPageContext(text);
    return question || text;
  }

  MindGraphMindMate.API_MESSAGE_MAX_LEN = API_MESSAGE_MAX_LEN;
  MindGraphMindMate.shouldAttachPageContext = shouldAttachPageContext;
  MindGraphMindMate.truncateMarkdownForBudget = truncateMarkdownForBudget;
  MindGraphMindMate.normalizeSourceCode = normalizeSourceCode;
  MindGraphMindMate.formatPageContextSourceLabel = formatPageContextSourceLabel;
  MindGraphMindMate.buildFirstMessageWithPageContext = buildFirstMessageWithPageContext;
  MindGraphMindMate.displayUserMessageFromDifyQuery = displayUserMessageFromDifyQuery;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
