/**
 * Capture active tab markdown for MindMate (runs in the service worker).
 * Uses doc-extract prep + engines on CNKI, Wenku, and other supported hosts.
 */
(function (global) {
  "use strict";

  const MindGraphShared = global.MindGraphShared;
  const MindGraphMindMate = global.MindGraphMindMate || {};
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const DEFAULT_MAX_MARKDOWN_CHARS = 8000;

  /**
   * @param {number} tabId
   * @param {number} [maxMarkdownChars]
   * @param {{ smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection: boolean } | { ok: false, error: string }>}
   */
  async function captureMindMatePageContext(tabId, maxMarkdownChars, options) {
    if (!tabId || tabId < 1) {
      return { ok: false, error: "errMindMatePageCaptureFailed" };
    }
    const maxChars =
      typeof maxMarkdownChars === "number" && maxMarkdownChars > 0
        ? maxMarkdownChars
        : DEFAULT_MAX_MARKDOWN_CHARS;

    if (typeof MindGraphDocExtract.runDocumentExtractToMarkdown === "function") {
      return MindGraphDocExtract.runDocumentExtractToMarkdown(tabId, maxChars, options || {});
    }

    try {
      const tab = await chrome.tabs.get(tabId);
      const pageUrl = tab.url || "";
      if (MindGraphShared.isRestrictedTabUrl(pageUrl)) {
        return { ok: false, error: "errRestrictedPage" };
      }
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["mindmate-page-markdown.js"],
      });
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: async (limit) => {
          if (
            globalThis.__MGMindMatePageMarkdown &&
            typeof globalThis.__MGMindMatePageMarkdown.extractPageMarkdownAsync === "function"
          ) {
            return globalThis.__MGMindMatePageMarkdown.extractPageMarkdownAsync(limit);
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
