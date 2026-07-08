/**
 * Shared page text capture for MindMate, mind map generation, and File Center ingest.
 * File-first hosts (SmartEdu, CNKI, Wenku) download/extract documents; others use DOM text.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const MindGraphShared = global.MindGraphShared;
  const MindGraphExtensionStorage = global.MindGraphExtensionStorage;

  const PAGE_CONTENT_INJECT_SCRIPT = "doc-extract/text/page-content.js";

  MindGraphDocExtract.PAGE_CONTENT_INJECT_SCRIPT = PAGE_CONTENT_INJECT_SCRIPT;

  /**
   * @param {{ smarteduToken?: string, suppressMindMateUi?: boolean }} [extraOptions]
   * @returns {Promise<{ smarteduToken?: string, suppressMindMateUi?: boolean }>}
   */
  async function buildPageCaptureOptions(extraOptions) {
    const options = { ...(extraOptions || {}) };
    if (
      MindGraphExtensionStorage &&
      typeof MindGraphExtensionStorage.getSmartEduTokenIfFresh === "function" &&
      !options.smarteduToken
    ) {
      const token = await MindGraphExtensionStorage.getSmartEduTokenIfFresh();
      if (token) {
        options.smarteduToken = token;
      }
    }
    return options;
  }

  /**
   * Capture page body as markdown (file download/extract when the host supports it).
   * @param {number} tabId
   * @param {number} maxChars
   * @param {{ smarteduToken?: string, smarteduAssets?: Array<object>, suppressMindMateUi?: boolean }} [extraOptions]
   * @returns {Promise<{ ok: true, title: string, url: string, markdown: string, fromSelection?: boolean, source?: string, hostId?: string, assetTotal?: number } | { ok: false, error: string }>}
   */
  async function capturePageContentMarkdown(tabId, maxChars, extraOptions) {
    if (!tabId || tabId < 1) {
      return { ok: false, error: "errMindMatePageCaptureFailed" };
    }
    const limit =
      typeof maxChars === "number" && maxChars > 0 ? maxChars : MindGraphShared.DEFAULT_MINDMATE_CAPTURE_CHARS;
    const options = await buildPageCaptureOptions(extraOptions);

    if (typeof MindGraphDocExtract.runDocumentExtractToMarkdown === "function") {
      return MindGraphDocExtract.runDocumentExtractToMarkdown(tabId, limit, options);
    }

    try {
      const tab = await chrome.tabs.get(tabId);
      const pageUrl = tab.url || "";
      if (MindGraphShared.isRestrictedTabUrl(pageUrl)) {
        return { ok: false, error: "errRestrictedPage" };
      }
      await chrome.scripting.executeScript({
        target: { tabId },
        files: [PAGE_CONTENT_INJECT_SCRIPT],
      });
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: async (charLimit) => {
          if (
            globalThis.__MGPageContent &&
            typeof globalThis.__MGPageContent.extractPageMarkdownAsync === "function"
          ) {
            return globalThis.__MGPageContent.extractPageMarkdownAsync(charLimit);
          }
          return { title: document.title || "", url: location.href || "", markdown: "", fromSelection: false };
        },
        args: [limit],
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
        source: (payload && payload.source) || "page-markdown",
      };
    } catch {
      return { ok: false, error: "errMindMatePageCaptureFailed" };
    }
  }

  /**
   * @param {{ ok: boolean, title?: string, url?: string, markdown?: string }} captureResult
   * @param {string} language
   * @returns {{ page_content: string, content_format: string, page_title: string | null, page_url: string | null, language: string } | null}
   */
  function captureResultToWebContentPayload(captureResult, language) {
    if (!captureResult || !captureResult.ok) {
      return null;
    }
    const markdown = typeof captureResult.markdown === "string" ? captureResult.markdown.trim() : "";
    if (!markdown) {
      return null;
    }
    return {
      page_content: markdown,
      content_format: "text/markdown",
      page_title: captureResult.title || null,
      page_url: captureResult.url || null,
      language,
    };
  }

  /**
   * @param {{ ok?: boolean, error?: string }} captureResult
   * @returns {string}
   */
  function localizedCaptureErrorKey(captureResult) {
    const key = captureResult && captureResult.error;
    if (key && key.startsWith("err")) {
      return key;
    }
    return "errNoPageText";
  }

  /**
   * @param {{ ok?: boolean, error?: string }} captureResult
   * @returns {string}
   */
  function localizedCaptureErrorMessage(captureResult) {
    const key = localizedCaptureErrorKey(captureResult);
    if (typeof chrome !== "undefined" && chrome.i18n) {
      return chrome.i18n.getMessage(key) || key;
    }
    return key;
  }

  MindGraphDocExtract.capturePageContentMarkdown = capturePageContentMarkdown;
  MindGraphDocExtract.captureResultToWebContentPayload = captureResultToWebContentPayload;
  MindGraphDocExtract.localizedCaptureErrorKey = localizedCaptureErrorKey;
  MindGraphDocExtract.localizedCaptureErrorMessage = localizedCaptureErrorMessage;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
