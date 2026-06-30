/**
 * In-tab PDF text extraction (pdf.js loaded via chrome.scripting.executeScript files).
 */
(function (global) {
  "use strict";

  /**
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractEmbeddedPdfViewerText(maxPages, maxChars) {
    const app = global.PDFViewerApplication;
    if (!app || !app.pdfDocument) {
      return "";
    }
    const pdf = app.pdfDocument;
    const limit = Math.min(pdf.numPages || 0, maxPages > 0 ? maxPages : 120);
    if (!limit) {
      return "";
    }
    const parts = [];
    for (let pageNum = 1; pageNum <= limit; pageNum += 1) {
      const page = await pdf.getPage(pageNum);
      const content = await page.getTextContent();
      const pageText = content.items
        .map((item) => (item && item.str ? item.str : ""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (pageText) {
        parts.push(pageText);
      }
    }
    let text = parts.join("\n\n").trim();
    if (maxChars > 0 && text.length > maxChars) {
      text = `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
    }
    return text;
  }

  /**
   * @param {ArrayBuffer} pdfBuffer
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractTextFromPdfBuffer(pdfBuffer, maxPages, maxChars) {
    const pdfjsLib = global.pdfjsLib;
    if (!pdfjsLib || typeof pdfjsLib.getDocument !== "function") {
      throw new Error("PDFJS_NOT_LOADED");
    }
    pdfjsLib.GlobalWorkerOptions.workerSrc = chrome.runtime.getURL("vendor/pdfjs/pdf.worker.min.js");
    const data = pdfBuffer instanceof ArrayBuffer ? new Uint8Array(pdfBuffer) : pdfBuffer;
    const loadingTask = pdfjsLib.getDocument({ data });
    const pdf = await loadingTask.promise;
    const limit = Math.min(pdf.numPages || 0, maxPages > 0 ? maxPages : 80);
    const parts = [];
    for (let pageNum = 1; pageNum <= limit; pageNum += 1) {
      const page = await pdf.getPage(pageNum);
      const content = await page.getTextContent();
      const pageText = content.items
        .map((item) => (item && item.str ? item.str : ""))
        .join(" ")
        .replace(/\s+/g, " ")
        .trim();
      if (pageText) {
        parts.push(pageText);
      }
    }
    let text = parts.join("\n\n").trim();
    if (maxChars > 0 && text.length > maxChars) {
      text = `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
    }
    return text;
  }

  global.__MGDocExtractPdf = {
    extractEmbeddedPdfViewerText,
    extractTextFromPdfBuffer,
  };
})(typeof globalThis !== "undefined" ? globalThis : window);
