/**
 * Capture active tab markdown for MindMate (runs in the service worker).
 * Delegates to the shared page-content capture pipeline (file-first + DOM text).
 */
(function (global) {
  "use strict";

  const MindGraphMindMate = global.MindGraphMindMate || {};
  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MindGraphShared = global.MindGraphShared;
  const DEFAULT_MAX_MARKDOWN_CHARS = MindGraphShared.DEFAULT_MINDMATE_CAPTURE_CHARS;

  /**
   * @param {number} tabId
   * @param {number} [maxMarkdownChars]
   * @param {{ smarteduAssets?: Array<object>, smarteduToken?: string }} [options]
   * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection: boolean } | { ok: false, error: string }>}
   */
  async function captureMindMatePageContext(tabId, maxMarkdownChars, options) {
    const maxChars =
      typeof maxMarkdownChars === "number" && maxMarkdownChars > 0
        ? maxMarkdownChars
        : DEFAULT_MAX_MARKDOWN_CHARS;

    if (typeof MindGraphDocExtract.capturePageContentMarkdown === "function") {
      return MindGraphDocExtract.capturePageContentMarkdown(tabId, maxChars, options || {});
    }

    if (typeof MindGraphDocExtract.runDocumentExtractToMarkdown === "function") {
      return MindGraphDocExtract.runDocumentExtractToMarkdown(tabId, maxChars, options || {});
    }

    return { ok: false, error: "errMindMatePageCaptureFailed" };
  }

  MindGraphMindMate.captureMindMatePageContext = captureMindMatePageContext;
  global.MindGraphMindMate = MindGraphMindMate;
})(typeof self !== "undefined" ? self : globalThis);
