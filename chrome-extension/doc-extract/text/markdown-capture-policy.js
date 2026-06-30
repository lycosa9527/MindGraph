/**
 * MindMate capture limits and preview notices per host / format.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const WENKU_CAP = MindGraphDocExtract.WENKU_PREVIEW_PAGE_CAP || 8;

  /** @type {Record<string, { pdfMaxPages?: number, previewNotice?: string }>} */
  const HOST_MARKDOWN_LIMITS = {
    wenku: { pdfMaxPages: WENKU_CAP, previewNotice: "mindmateNoticeWenkuPreview" },
    doc88: { previewNotice: "mindmateNoticeCanvasHost" },
    docin: { previewNotice: "mindmateNoticeCanvasHost" },
    taodocs: { previewNotice: "mindmateNoticeCanvasHost" },
    book118: { previewNotice: "mindmateNoticeCanvasHost" },
    deliwenku: { previewNotice: "mindmateNoticeCanvasHost" },
    mbalib: { previewNotice: "mindmateNoticeCanvasHost" },
    iask: { previewNotice: "mindmateNoticeCanvasHost" },
    dugen: { previewNotice: "mindmateNoticeCanvasHost" },
    gb688: { previewNotice: "mindmateNoticeCanvasHost" },
    safewk: { previewNotice: "mindmateNoticeCanvasHost" },
    renrendoc: { previewNotice: "mindmateNoticeCanvasHost" },
    yunzhan365: { previewNotice: "mindmateNoticeCanvasHost" },
    wenku_so: { previewNotice: "mindmateNoticeCanvasHost" },
    wenkub: { previewNotice: "mindmateNoticeCanvasHost" },
    jinchutou: { previewNotice: "mindmateNoticeCanvasHost" },
    nrsis: { previewNotice: "mindmateNoticeCanvasHost" },
    ssap: { previewNotice: "mindmateNoticeCanvasHost" },
    jg_class: { previewNotice: "mindmateNoticeCanvasHost" },
    sdlib: { previewNotice: "mindmateNoticeCanvasHost" },
  };

  /**
   * @param {object} hostEntry
   * @returns {{ pdfMaxPages: number, previewNotice: string | null }}
   */
  function markdownLimitsForHost(hostEntry) {
    const id = hostEntry && hostEntry.id ? hostEntry.id : "";
    const row = HOST_MARKDOWN_LIMITS[id] || {};
    return {
      pdfMaxPages: typeof row.pdfMaxPages === "number" ? row.pdfMaxPages : 120,
      previewNotice: row.previewNotice || null,
    };
  }

  /**
   * @param {string} markdown
   * @param {string} noticeLine
   * @param {number} maxChars
   * @returns {string}
   */
  function prependCaptureNotice(markdown, noticeLine, maxChars) {
    const body = (markdown || "").trim();
    const notice = (noticeLine || "").trim();
    if (!notice) {
      return body;
    }
    const prefix = `> ${notice}\n\n`;
    const combined = prefix + body;
    if (!maxChars || combined.length <= maxChars) {
      return combined;
    }
    const budget = Math.max(0, maxChars - prefix.length - 10);
    if (budget <= 0) {
      return prefix.trim();
    }
    return `${prefix}${body.slice(0, budget).trim()}\n\n…`;
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @returns {Promise<number|null>}
   */
  async function countCanvasPagesInTab(tabId, hostEntry) {
    if (!tabId || tabId < 1) {
      return null;
    }
    try {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["doc-extract/wenku/preview-notice.js", "doc-extract/inject/page-collect.js"],
      });
      const hideSelectors = hostEntry && hostEntry.hideSelectors ? hostEntry.hideSelectors : [];
      const results = await chrome.scripting.executeScript({
        target: { tabId },
        func: (selectors) => {
          if (globalThis.__MGDocExtractCollect && globalThis.__MGDocExtractCollect.collectCanvasImages) {
            return globalThis.__MGDocExtractCollect.collectCanvasImages(selectors);
          }
          return { pageCount: document.querySelectorAll("canvas").length };
        },
        args: [hideSelectors],
      });
      const payload = results && results[0] && results[0].result;
      if (!payload) {
        return null;
      }
      if (typeof payload.pageCount === "number") {
        return payload.pageCount;
      }
      if (Array.isArray(payload.images)) {
        return payload.images.length;
      }
      return null;
    } catch {
      return null;
    }
  }

  /**
   * @param {object} hostEntry
   * @returns {boolean}
   */
  function isCanvasRenderHost(hostEntry) {
    if (!hostEntry || !hostEntry.engine) {
      return false;
    }
    return hostEntry.engine === "canvas-pdf" || hostEntry.engine === "html2canvas-pdf";
  }

  /**
   * Hosts where MindMate must download PDFs/binaries first — DOM-only capture is not enough.
   * @param {object} hostEntry
   * @returns {boolean}
   */
  function hostRequiresFileExtract(hostEntry) {
    if (!hostEntry || !hostEntry.id) {
      return false;
    }
    return hostEntry.id === "smartedu" || hostEntry.id === "wenku" || hostEntry.id === "cnki";
  }

  MindGraphDocExtract.HOST_MARKDOWN_LIMITS = HOST_MARKDOWN_LIMITS;
  MindGraphDocExtract.hostRequiresFileExtract = hostRequiresFileExtract;
  MindGraphDocExtract.markdownLimitsForHost = markdownLimitsForHost;
  MindGraphDocExtract.prependCaptureNotice = prependCaptureNotice;
  MindGraphDocExtract.countCanvasPagesInTab = countCanvasPagesInTab;
  MindGraphDocExtract.isCanvasRenderHost = isCanvasRenderHost;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
