/**
 * Classify a PDF blob: embedded text, or image pages that need server vision OCR.
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};
  const PDF_EXTRACT_FILES = [
    "vendor/pdfjs/pdf.worker.min.js",
    "vendor/pdfjs/pdf.min.js",
    "doc-extract/text/pdf-extract-in-tab.js",
  ];

  /**
   * @param {ArrayBuffer} buffer
   * @returns {string}
   */
  function pdfBufferToBase64Arg(buffer) {
    if (
      typeof MindGraphOffscreenBlobs !== "undefined" &&
      MindGraphOffscreenBlobs &&
      typeof MindGraphOffscreenBlobs.arrayBufferToBase64 === "function"
    ) {
      return MindGraphOffscreenBlobs.arrayBufferToBase64(buffer);
    }
    const bytes = new Uint8Array(buffer);
    const chunkSize = 8192;
    let binary = "";
    for (let i = 0; i < bytes.length; i += chunkSize) {
      binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunkSize));
    }
    return btoa(binary);
  }

  /**
   * @param {number} tabId
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<{ text: string, imageBased: boolean, pageCount: number }>}
   */
  async function classifyPdfBlobInTab(tabId, blob, maxPages, maxChars) {
    const empty = { text: "", imageBased: false, pageCount: 0 };
    const buffer = await blob.arrayBuffer();
    if (!buffer || buffer.byteLength < 64) {
      return empty;
    }
    const base64 = pdfBufferToBase64Arg(buffer);
    await chrome.scripting.executeScript({
      target: { tabId },
      files: PDF_EXTRACT_FILES,
    });
    const results = await chrome.scripting.executeScript({
      target: { tabId },
      func: async (pdfBase64, pages, chars) => {
        if (
          !globalThis.__MGDocExtractPdf ||
          typeof globalThis.__MGDocExtractPdf.classifyPdfBuffer !== "function"
        ) {
          throw new Error("PDFJS_NOT_LOADED");
        }
        const binaryStr = atob(pdfBase64);
        const bytes = new Uint8Array(binaryStr.length);
        for (let i = 0; i < binaryStr.length; i += 1) {
          bytes[i] = binaryStr.charCodeAt(i);
        }
        return globalThis.__MGDocExtractPdf.classifyPdfBuffer(bytes.buffer, pages, chars);
      },
      args: [base64, maxPages, maxChars],
    });
    const payload = results && results[0] && results[0].result;
    if (!payload || typeof payload !== "object") {
      return empty;
    }
    return {
      text: typeof payload.text === "string" ? payload.text.trim() : "",
      imageBased: Boolean(payload.imageBased),
      pageCount: typeof payload.pageCount === "number" ? payload.pageCount : 0,
    };
  }

  /**
   * @param {number} tabId
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<{ text: string, imageBased: boolean, pageCount: number }>}
   */
  async function classifyPdfBlobWithFallback(tabId, blob, maxPages, maxChars) {
    if (typeof MindGraphDocExtract.classifyPdfBlobOffscreen === "function") {
      try {
        const offscreen = await MindGraphDocExtract.classifyPdfBlobOffscreen(blob, maxPages, maxChars);
        if (offscreen && (offscreen.text || offscreen.imageBased || offscreen.pageCount)) {
          return offscreen;
        }
      } catch {
        /* fall through to the lesson tab */
      }
    }
    return classifyPdfBlobInTab(tabId, blob, maxPages, maxChars);
  }

  MindGraphDocExtract.classifyPdfBlobInTab = classifyPdfBlobInTab;
  MindGraphDocExtract.classifyPdfBlobWithFallback = classifyPdfBlobWithFallback;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
