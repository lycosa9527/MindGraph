/**
 * Blob / buffer format detection and text extraction helpers (MindMate markdown).
 */
(function (global) {
  "use strict";

  const MindGraphDocExtract = global.MindGraphDocExtract || {};

  /**
   * @param {ArrayBuffer | Uint8Array} buffer
   * @returns {boolean}
   */
  function isPdfBytes(buffer) {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
    return (
      bytes.length >= 4 &&
      bytes[0] === 0x25 &&
      bytes[1] === 0x50 &&
      bytes[2] === 0x44 &&
      bytes[3] === 0x46
    );
  }

  /**
   * @param {Blob} blob
   * @returns {boolean}
   */
  function isPdfBlob(blob) {
    const type = (blob && blob.type ? blob.type : "").toLowerCase();
    if (type.includes("pdf")) {
      return true;
    }
    return false;
  }

  /**
   * @param {string} html
   * @returns {string}
   */
  function stripHtmlToPlainText(html) {
    return (html || "")
      .replace(/<script[\s\S]*?<\/script>/gi, " ")
      .replace(/<style[\s\S]*?<\/style>/gi, " ")
      .replace(/<br\s*\/?>/gi, "\n")
      .replace(/<\/p>/gi, "\n")
      .replace(/<[^>]+>/g, " ")
      .replace(/&nbsp;/gi, " ")
      .replace(/&amp;/gi, "&")
      .replace(/&lt;/gi, "<")
      .replace(/&gt;/gi, ">")
      .replace(/\s+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .replace(/[ \t]+/g, " ")
      .trim();
  }

  /**
   * @param {ArrayBuffer} buffer
   * @param {string} mimeType
   * @param {number} maxChars
   * @returns {string}
   */
  function decodeTextBuffer(buffer, mimeType, maxChars) {
    const type = (mimeType || "").toLowerCase();
    let raw = "";
    try {
      raw = new TextDecoder("utf-8", { fatal: false }).decode(buffer);
    } catch {
      return "";
    }
    if (!raw.trim()) {
      return "";
    }
    let text = raw;
    if (type.includes("html") || /<\/?[a-z][\s\S]*>/i.test(raw)) {
      text = stripHtmlToPlainText(raw);
    }
    text = text.trim();
    if (!maxChars || text.length <= maxChars) {
      return text;
    }
    return `${text.slice(0, Math.max(0, maxChars - 20)).trim()}\n\n…`;
  }

  /**
   * @param {Blob} blob
   * @returns {"pdf"|"text"|"unknown"}
   */
  function classifyDownloadBlob(blob) {
    if (!blob) {
      return "unknown";
    }
    const type = (blob.type || "").toLowerCase();
    if (isPdfBlob(blob)) {
      return "pdf";
    }
    if (
      type.includes("text") ||
      type.includes("html") ||
      type.includes("json") ||
      type.includes("xml")
    ) {
      return "text";
    }
    return "unknown";
  }

  /**
   * @param {number} tabId
   * @param {Blob} blob
   * @param {number} maxPages
   * @param {number} maxChars
   * @returns {Promise<string>}
   */
  async function extractBlobTextInTab(tabId, blob, maxPages, maxChars) {
    if (!blob || blob.size < 8) {
      return "";
    }
    const buffer = await blob.arrayBuffer();
    const kind =
      isPdfBytes(buffer) || classifyDownloadBlob(blob) === "pdf" ? "pdf" : classifyDownloadBlob(blob);

    if (kind === "pdf") {
      if (typeof MindGraphDocExtract.extractPdfBlobTextOffscreen === "function") {
        try {
          const offscreenText = await MindGraphDocExtract.extractPdfBlobTextOffscreen(
            blob,
            maxPages,
            maxChars,
          );
          if (offscreenText && offscreenText.trim()) {
            return offscreenText.trim();
          }
        } catch (err) {
          const root = global.MindGraphMindMate;
          if (root && root.captureDebug) {
            root.captureDebug.log("pdf.offscreen", "offscreen PDF extract failed", {
              message: err instanceof Error ? err.message : "unknown",
            });
          }
        }
      }
      if (typeof MindGraphDocExtract.extractPdfBlobTextWithFallback === "function") {
        return MindGraphDocExtract.extractPdfBlobTextWithFallback(tabId, blob, maxPages, maxChars);
      }
      if (typeof MindGraphDocExtract.extractPdfBlobTextInTab === "function") {
        return MindGraphDocExtract.extractPdfBlobTextInTab(tabId, blob, maxPages, maxChars);
      }
      return "";
    }

    if (kind === "text") {
      return decodeTextBuffer(buffer, blob.type || "text/plain", maxChars);
    }

    if (isPdfBytes(buffer) && typeof MindGraphDocExtract.extractPdfBlobTextInTab === "function") {
      return MindGraphDocExtract.extractPdfBlobTextInTab(tabId, blob, maxPages, maxChars);
    }

    return "";
  }

  MindGraphDocExtract.isPdfBytes = isPdfBytes;
  MindGraphDocExtract.isPdfBlob = isPdfBlob;
  MindGraphDocExtract.stripHtmlToPlainText = stripHtmlToPlainText;
  MindGraphDocExtract.decodeTextBuffer = decodeTextBuffer;
  MindGraphDocExtract.classifyDownloadBlob = classifyDownloadBlob;
  MindGraphDocExtract.extractBlobTextInTab = extractBlobTextInTab;
  global.MindGraphDocExtract = MindGraphDocExtract;
})(typeof self !== "undefined" ? self : globalThis);
