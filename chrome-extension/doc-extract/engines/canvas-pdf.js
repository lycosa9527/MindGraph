/**
 * canvas-pdf tab runner — collect canvases in page, assemble in SW.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @returns {Promise<{ images: string[], title: string, pageCount: number }>}
   */
  async function collectCanvasFromTab(tabId, hostEntry) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["doc-extract/wenku/preview-notice.js", "doc-extract/inject/page-collect.js"],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (hideSelectors) => {
        if (!globalThis.__MGDocExtractCollect) {
          throw new Error("COLLECT_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCollect.collectCanvasImages(hideSelectors);
      },
      args: [hostEntry.hideSelectors || []],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || !payload.images || !payload.images.length) {
      throw new Error("CANVAS_EMPTY");
    }
    return payload;
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {(stage: string) => void} postProgress
   * @returns {Promise<{ blob: Blob, filename: string }>}
   */
  async function runCanvasPdfEngine(tabId, hostEntry, postProgress) {
    postProgress("collecting");
    const payload = await collectCanvasFromTab(tabId, hostEntry);
    postProgress("assembling");
    let blob;
    try {
      blob = await MindGraphDocExtract.imagesToPdfBlob(payload.images, payload.title, {
        pageWidth: payload.pageWidth,
        pageHeight: payload.pageHeight,
      });
    } catch {
      blob = await MindGraphDocExtract.imagesToZipBlob(payload.images);
      return {
        blob,
        filename: MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ".zip"),
        extractNotice: payload.extractNotice || null,
      };
    }
    return {
      blob,
      filename: MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ".pdf"),
      extractNotice: payload.extractNotice || null,
    };
  }

  MindGraphDocExtract.collectCanvasFromTab = collectCanvasFromTab;
  MindGraphDocExtract.runCanvasPdfEngine = runCanvasPdfEngine;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
