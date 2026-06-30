/**
 * Capture active tab markdown for MindMate (runs in the service worker).
 */
(function (global) {
  "use strict";

  const MindGraphShared = global.MindGraphShared;
  const MindGraphMindMate = global.MindGraphMindMate || {};
  const PAGE_MARKDOWN_SCRIPT = "mindmate-page-markdown.js";
  const DEFAULT_MAX_MARKDOWN_CHARS = 3200;

  /**
   * @param {number} tabId
   * @param {number} [maxMarkdownChars]
   * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection: boolean } | { ok: false, error: string }>}
   */
  async function captureMindMatePageContext(tabId, maxMarkdownChars) {
    if (!tabId || tabId < 1) {
      return { ok: false, error: "errMindMatePageCaptureFailed" };
    }
    const maxChars =
      typeof maxMarkdownChars === "number" && maxMarkdownChars > 0
        ? maxMarkdownChars
        : DEFAULT_MAX_MARKDOWN_CHARS;
    try {
      const tab = await chrome.tabs.get(tabId);
      const pageUrl = tab.url || "";
      if (MindGraphShared.isRestrictedTabUrl(pageUrl)) {
        return { ok: false, error: "errRestrictedPage" };
      }
      await chrome.scripting.executeScript({
        target: { tabId },
        files: [PAGE_MARKDOWN_SCRIPT],
      });
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: (limit) => {
          if (
            globalThis.__MGMindMatePageMarkdown &&
            typeof globalThis.__MGMindMatePageMarkdown.extractPageMarkdown === "function"
          ) {
            return globalThis.__MGMindMatePageMarkdown.extractPageMarkdown(limit);
          }
          return { title: document.title || "", url: location.href || "", markdown: "", fromSelection: false };
        },
        args: [maxChars],
      });
      const payload = results && results[0] && results[0].result;
      const markdown = payload && typeof payload.markdown === "string" ? payload.markdown.trim() : "";
      if (!markdown) {
        return { ok: false, error: "errMindMatePageEmpty" };
      }
      return {
        ok: true,
        title: (payload && payload.title) || tab.title || "",
        url: (payload && payload.url) || pageUrl,
        markdown,
        fromSelection: Boolean(payload && payload.fromSelection),
      };
    } catch {
      return { ok: false, error: "errMindMatePageCaptureFailed" };
    }
  }

  MindGraphMindMate.captureMindMatePageContext = captureMindMatePageContext;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
