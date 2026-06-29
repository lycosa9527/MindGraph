/**
 * html2canvas-pdf engine config — page capture via inject + SW PDF assembly.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @returns {Promise<{ images: string[], title: string, pageCount: number }>}
   */
  async function collectHtml2CanvasFromTab(tabId, hostEntry) {
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["vendor/html2canvas.min.js"],
    });
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["doc-extract/inject/page-collect.js"],
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: (config) => {
        if (!globalThis.__MGDocExtractCollect) {
          throw new Error("COLLECT_NOT_LOADED");
        }
        return globalThis.__MGDocExtractCollect.collectHtml2CanvasImages(config);
      },
      args: [
        {
          pageSelectors: hostEntry.pageSelectors || [".page"],
        },
      ],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || !payload.images || !payload.images.length) {
      throw new Error("HTML2CANVAS_EMPTY");
    }
    return payload;
  }

  /**
   * @param {number} tabId
   * @param {object} hostEntry
   * @param {(stage: string) => void} postProgress
   * @returns {Promise<{ blob: Blob, filename: string }>}
   */
  async function runHtml2CanvasPdfEngine(tabId, hostEntry, postProgress) {
    postProgress("collecting");
    let payload;
    try {
      payload = await collectHtml2CanvasFromTab(tabId, hostEntry);
    } catch (e) {
      if (MindGraphDocExtract.imagesToZipBlob) {
        throw e;
      }
      throw e;
    }
    postProgress("assembling");
    let blob;
    try {
      blob = await MindGraphDocExtract.imagesToPdfBlob(payload.images, payload.title, {
        pageWidth: payload.pageWidth,
        pageHeight: payload.pageHeight,
      });
    } catch {
      blob = await MindGraphDocExtract.imagesToZipBlob(payload.images);
      const base = MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ".zip");
      return { blob, filename: base };
    }
    const filename = MindGraphDocExtract.sanitizeDownloadBasename(payload.title, ".pdf");
    return { blob, filename };
  }

  MindGraphDocExtract.collectHtml2CanvasFromTab = collectHtml2CanvasFromTab;
  MindGraphDocExtract.runHtml2CanvasPdfEngine = runHtml2CanvasPdfEngine;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
